# Lo-Fi Daily YouTube Pipeline — Design

Date: 2026-08-04  
Status: approved  
Scope: extend `lofi_batch` from audio-only playlists to LLM-prompted daily packages (audio + cover + video) with a 1-video-per-day YouTube publish queue.

## Problem

`lofi_batch` today:

- Reads static `prompts/*.txt`
- Generates N short instrumental tracks via ACE-Step
- Concatenates to `playlist.wav`
- Does **not** generate cover art, assemble video, or upload to YouTube

We want a closed loop: each run invents a Lo-Fi music prompt from fixed rules, generates the playlist, makes a matching still cover, builds a long static-image MP4, enqueues a publish package, and uploads **at most one video per calendar day**.

## Goals

1. Local LLM (Qwen-style, same pattern as `scripts/00_generate_lyrics.py`) writes the music prompt from Lo-Fi rules every run.
2. Reuse existing ACE-Step track generation + ffmpeg concat.
3. Local image model already in the stack (Wan / Diffusers) produces a 1280×720 cover matching the music mood.
4. Classic Lo-Fi YouTube format: **static cover + playlist audio → one long MP4**.
5. YouTube Data API OAuth: first-time manual consent; thereafter refresh-token automation.
6. Two operator modes on one codebase:
   - **daily**: generate one package; publish if none published today
   - **burst**: generate N packages into the queue only; publish still max 1/day
7. Optional daemon: keep a container alive and start a job only when a chosen GPU is free.

## Non-goals

- Animated / Ken Burns / Wan video loops for the YouTube main file
- Multi-channel or multi-account YouTube
- Changing ACE-Step model training or DiT internals
- Replacing the virtual-singer lip-sync pipeline (`scripts/07_*`, MuseTalk, etc.)

## Chosen approach

Single orchestrator inside `lofi_batch` with an on-disk queue. One pipeline, two entry scripts/modes, one publisher that enforces the daily cap.

Rejected alternatives:

- Separate generator + publisher containers (more ops for little gain)
- Monolithic cron that diverges for burst vs daily

## Architecture

```text
rules/lofi_rules.md
        │
        ▼
generate_prompt.py  (Qwen local)
  → slug, music_prompt, image_prompt, title, description, tags
        │
        ▼
run_batch audio path (ACE-Step × N → playlist.wav)
        │
        ▼
generate_cover.py   (Wan/Diffusers T2I → cover.png)
        │
        ▼
make_video.py       (ffmpeg still + audio → video.mp4)
        │
        ▼
queue/<run_id>_<slug>/   (ready package + meta.json)
        │
        ▼
youtube_upload.py   (≤1 publish / local calendar day)
        │
        ▼
published/<id>/ + state.json
```

### Run modes

| Mode | Generation | Publish |
|------|------------|---------|
| `daily` | 1 package | After generation, upload oldest `ready` package if none published today |
| `burst --count N` | N packages | Queue only; never bypass daily cap |
| `daemon` | Waits for free GPU, then runs `daily` (or configured job) | Same as daily |

Publish is always: **at most one successful upload per calendar day in timezone `TZ` (default: host local time)**, regardless of how many packages sit in the queue. A separate upload-only invocation is allowed (e.g. cron) and uses the same cap.

## Components

### 1. `lofi_batch/rules/lofi_rules.md`

Authoritative system/rules text for the LLM. Mix of:

- Classic Lo-Fi constraints (instrumental, soft textures, chill atmospheres, vinyl/room tone optional, no hype drops, no vocals)
- Restrictive structure inspired by `prompts/odisseu.txt`: short positive brief, explicit instrumentation limits, long **NEGATIVE PROMPT** block

Editable without code changes.

### 2. `lofi_batch/generate_prompt.py`

- Loads `rules/lofi_rules.md`
- Calls local instruct model (default: same family as lyrics script, e.g. `Qwen/Qwen3-4B-Instruct-2507`, overridable via env)
- Asks for **JSON only** with fields:
  - `slug` (filesystem-safe)
  - `music_prompt` (full ACE-Step prompt including negative section)
  - `image_prompt` (still cover, 16:9 Lo-Fi scene, no text/logos)
  - `title`, `description`, `tags` (YouTube metadata)
- Validates JSON; on parse failure, retries once with a repair prompt; then fails the run
- Writes `prompt.json` into the package working dir and optionally a timestamped copy under `lofi_batch/prompts/generated/`

### 3. Audio generation (existing `run_batch.py` extended)

- Keep track loop, resume skips, concat, `manifest.json`
- New path: accept a single generated prompt (from `prompt.json` / CLI) instead of only scanning `prompts/*.txt`
- Static `.txt` prompts remain supported for manual/debug runs
- Defaults stay configurable via `config.env` (`TRACKS`, `DURATION`, `CONFIG_PATH`, `LM_MODEL`, `BACKEND`, `GPU`)

### 4. `lofi_batch/generate_cover.py`

- Input: `image_prompt` (+ optional negative defaults: text, watermark, logo, blurry)
- Model path (v1): reuse Wan Diffusers as in `scripts/06a_generate_avatar.py` — generate a **short** clip at 1280×720, extract one frame to `cover.png` (no animated YouTube main file)
- Output: `cover.png` in the package dir
- Resume: skip if `cover.png` exists and is non-empty unless `--force`

### 5. `lofi_batch/make_video.py`

- `ffmpeg`: loop/still `cover.png` + `playlist.wav` → `video.mp4`
- No video re-encode of motion; prefer efficient still+audio mux (e.g. `-loop 1 -framerate 1` + audio copy/re-encode as needed for YouTube)
- Resume: skip if `video.mp4` exists and is non-empty unless `--force`

### 6. Queue layout

```text
output/lofi_batch/
  queue/<run_id>_<slug>/
    prompt.json
    lyrics.txt
    tracks/
    playlist.wav
    cover.png
    video.mp4
    meta.json          # title, description, tags, status=ready
    manifest.json
  published/<run_id>_<slug>/
    ...                # moved or copied after successful upload
    youtube.json       # video id, published_at, url
  state.json           # last_publish_date (YYYY-MM-DD), last_video_id
  cron.log / docker_batch.log
```

`meta.json` statuses: `generating` → `ready` → `uploading` → `published`. Upload errors do **not** use a terminal `failed` status for the package (see upload retry policy below).

### 7. YouTube OAuth + upload

- `lofi_batch/youtube_auth.py`: one-time OAuth installed-app flow; stores `client_secret.json` + `token.json` under `lofi_batch/secrets/` (**gitignored**)
- `lofi_batch/youtube_upload.py`:
  - Reads `state.json`; if `last_publish_date == today` (`TZ`), exit 0 with “already published today”
  - Picks oldest `queue/*/meta.json` with `status=ready` and required files present
  - Uploads `video.mp4` with title/description/tags; sets thumbnail to `cover.png` when API allows
  - On success: write `youtube.json`, set status `published`, update `state.json`, move package to `published/`
  - On failure: keep `status=ready`, write `last_error` + `last_error_at` on `meta.json`, exit non-zero so the next eligible day retries the same package

Privacy default: `public` (configurable via env `YOUTUBE_PRIVACY=public|unlisted|private`).

### 8. Entry points

- `run_docker.sh` — extend to accept `MODE=daily|burst`, `COUNT`, and optional `--skip-upload`
- `run_daily.sh` — `MODE=daily` then upload
- `run_burst.sh` — `MODE=burst COUNT=N` (no upload bypass)
- `run_daemon.sh` — loop: poll GPU free (e.g. memory/util thresholds via `nvidia-smi`) → run daily job → sleep
- `crontab.example` — daily schedule (e.g. 03:00) calling daily entry; separate note for optional upload-only cron if generation and publish are split in time

### 9. Config

Extend `config.env.example`:

- Existing: `GPU`, `IMAGE`, `TRACKS`, `DURATION`, `CONFIG_PATH`, `LM_MODEL`, `BACKEND`
- New: `MODE`, `COUNT`, `PROMPT_LLM_MODEL`, `COVER_MODEL`, `YOUTUBE_PRIVACY`, `SKIP_UPLOAD`, `TZ`, `GPU_FREE_UTIL_MAX`, `GPU_FREE_MEM_MIB_MIN`, `DAEMON_POLL_SECONDS`

## Error handling

| Stage | Behavior |
|-------|----------|
| Prompt LLM JSON invalid | One repair retry; then fail run |
| Track failure | Same as today (`fail_fast` optional; resume skips good tracks) |
| Cover / video missing | Regenerate only missing artifacts |
| Upload API error | Leave package in queue with `last_error`; try again next eligible day |
| GPU busy (daemon) | Sleep and repoll; do not preempt other jobs |
| Partial package | Never mark `ready` until `playlist.wav`, `cover.png`, `video.mp4`, and `meta.json` exist |

## Testing

1. **Smoke (no YouTube):** `TRACKS=2 DURATION=30 SKIP_UPLOAD=1` → package with wav + cover + mp4 + `status=ready`
2. **Auth dry-run:** complete OAuth; `youtube_upload.py --dry-run` validates token and package selection without inserting a video
3. **Daily cap:** two ready packages in queue; run uploader twice same day → only one publish; second exits “already published”
4. **Burst:** `COUNT=2` → two ready packages; no extra uploads
5. **Resume:** kill mid-cover; rerun → skips audio, finishes cover/video

## Security

- Never commit `lofi_batch/secrets/` or real `token.json` / `client_secret.json`
- Document Google Cloud Console steps: enable YouTube Data API v3, create OAuth desktop client, download client secret
- Uploads only to the authorized channel account

## Rollout

1. Implement prompt + cover + video + queue without upload; smoke on GPU
2. Add OAuth setup + dry-run upload
3. Enable daily cron with `unlisted` first, then switch to `public`
4. Add daemon mode after daily path is stable

## Success criteria

- One command produces a ready YouTube package from rules alone (no hand-written prompt required)
- Burst can pre-generate many days of content without publishing more than one video per day
- Operator can leave a daemon waiting for a free GPU or pin a GPU for an immediate burst
- Secrets stay out of git; resume works across interrupted runs
