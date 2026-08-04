# Lo-Fi Daily YouTube Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `lofi_batch` so each run invents a Lo-Fi prompt via local Qwen, builds playlist + still cover + static MP4, queues packages, and publishes at most one YouTube video per calendar day — with daily and burst operator modes.

**Architecture:** Single orchestrator under `lofi_batch/` with an on-disk queue (`output/lofi_batch/queue/` → `published/`). Prompt LLM → ACE-Step audio (existing) → Wan short clip → frame as cover → ffmpeg still+audio MP4 → YouTube uploader gated by `state.json`.

**Tech Stack:** Python 3.10+, ACE-Step, Qwen via transformers, Wan Diffusers, ffmpeg, Google YouTube Data API v3 (google-api-python-client + google-auth-oauthlib), Docker + cron.

## Global Constraints

- Publish cap: **at most one successful upload per calendar day** in timezone `TZ` (default host local).
- Cover path v1: Wan short clip → extract one frame → `cover.png` (1280×720); YouTube main file is **static** image + audio only.
- Secrets under `lofi_batch/secrets/` must be **gitignored**; never commit tokens.
- Burst mode **never** bypasses the daily publish cap.
- Resume: skip existing non-empty artifacts unless `--force`.
- Keep static `prompts/*.txt` path working for debug; generated path is the default for daily/burst.
- Spec: `docs/superpowers/specs/2026-08-04-lofi-daily-youtube-design.md`.

## File map

| File | Responsibility |
|------|----------------|
| `lofi_batch/rules/lofi_rules.md` | LLM rules (classic Lo-Fi + restrictive structure) |
| `lofi_batch/prompt_schema.py` | Parse/validate `prompt.json` fields |
| `lofi_batch/generate_prompt.py` | Qwen → validated prompt JSON |
| `lofi_batch/package.py` | Queue paths, `meta.json`, `state.json` helpers |
| `lofi_batch/run_batch.py` | Extend: single-prompt package audio generation |
| `lofi_batch/generate_cover.py` | Wan → frame → `cover.png` |
| `lofi_batch/make_video.py` | ffmpeg still + wav → `video.mp4` |
| `lofi_batch/run_pipeline.py` | Orchestrate one or N packages (daily/burst) |
| `lofi_batch/youtube_auth.py` | OAuth setup + credential load |
| `lofi_batch/youtube_upload.py` | Daily-capped upload |
| `lofi_batch/run_daily.sh` / `run_burst.sh` / `run_daemon.sh` | Operator entrypoints |
| `lofi_batch/run_docker.sh` | Extend for MODE/COUNT/SKIP_UPLOAD |
| `lofi_batch/config.env.example` | New env knobs |
| `lofi_batch/crontab.example` | Daily cron |
| `lofi_batch/tests/` | Unit tests (no GPU required) |
| `.gitignore` | Ignore `lofi_batch/secrets/` |

---

### Task 1: Prompt schema + Lo-Fi rules

**Files:**
- Create: `lofi_batch/rules/lofi_rules.md`
- Create: `lofi_batch/prompt_schema.py`
- Create: `lofi_batch/tests/test_prompt_schema.py`
- Modify: `.gitignore` (add `lofi_batch/secrets/`)

**Interfaces:**
- Produces: `REQUIRED_FIELDS: tuple[str, ...]`, `parse_prompt_payload(raw: str) -> dict`, `validate_prompt(data: dict) -> dict`, `slugify(text: str) -> str`

- [ ] **Step 1: Write the failing test**

```python
# lofi_batch/tests/test_prompt_schema.py
from lofi_batch.prompt_schema import parse_prompt_payload, validate_prompt, slugify


def test_slugify_filesystem_safe():
    assert slugify("Rainy Cafe #1!") == "rainy_cafe_1"


def test_parse_and_validate_ok():
    raw = """{
      "slug": "rainy_cafe",
      "music_prompt": "soft piano lo-fi\\n\\nNEGATIVE PROMPT\\nNO vocals",
      "image_prompt": "cozy rainy cafe window, night, 16:9, no text",
      "title": "Rainy Cafe Lo-Fi",
      "description": "Chill instrumental playlist.",
      "tags": ["lofi", "rain", "study"]
    }"""
    data = validate_prompt(parse_prompt_payload(raw))
    assert data["slug"] == "rainy_cafe"
    assert "NEGATIVE PROMPT" in data["music_prompt"]
    assert data["tags"] == ["lofi", "rain", "study"]


def test_parse_rejects_missing_field():
    import pytest
    with pytest.raises(ValueError):
        validate_prompt({"slug": "x"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /raid/user_davidoneil/virtual_singer_clip && python -m pytest lofi_batch/tests/test_prompt_schema.py -v`
Expected: FAIL (module not found / import error)

- [ ] **Step 3: Add `lofi_batch/__init__.py` (empty) and implement `prompt_schema.py`**

```python
# lofi_batch/prompt_schema.py
from __future__ import annotations

import json
import re
from typing import Any

REQUIRED_FIELDS = (
    "slug",
    "music_prompt",
    "image_prompt",
    "title",
    "description",
    "tags",
)


def slugify(text: str) -> str:
    s = text.strip().lower()
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        raise ValueError("slugify produced empty slug")
    return s[:80]


def parse_prompt_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop first fence and optional trailing fence
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    # tolerate leading prose: take first {...} block
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("No JSON object found in model output")
    return json.loads(text[start : end + 1])


def validate_prompt(data: dict[str, Any]) -> dict[str, Any]:
    missing = [k for k in REQUIRED_FIELDS if k not in data]
    if missing:
        raise ValueError(f"Missing fields: {missing}")
    out = dict(data)
    out["slug"] = slugify(str(out["slug"]))
    for key in ("music_prompt", "image_prompt", "title", "description"):
        val = str(out[key]).strip()
        if not val:
            raise ValueError(f"Empty field: {key}")
        out[key] = val
    tags = out["tags"]
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if not isinstance(tags, list) or not tags:
        raise ValueError("tags must be a non-empty list")
    out["tags"] = [str(t).strip() for t in tags if str(t).strip()]
    if "NEGATIVE PROMPT" not in out["music_prompt"].upper().replace(" ", " "):
        # accept either exact header casing variants
        if "negative prompt" not in out["music_prompt"].lower():
            raise ValueError("music_prompt must include a NEGATIVE PROMPT section")
    return out
```

Fix the NEGATIVE PROMPT check to a simple casefold:

```python
    if "negative prompt" not in out["music_prompt"].lower():
        raise ValueError("music_prompt must include a NEGATIVE PROMPT section")
```

- [ ] **Step 4: Write `lofi_batch/rules/lofi_rules.md`**

Content must include: instrumental only; soft chill atmospheres; limited instrumentation; optional vinyl/room tone; no vocals/hype drops/EDM; require output JSON schema fields; require music prompt structure with positive brief + instrumentation limits + `NEGATIVE PROMPT` block (odisseu-style). Keep under ~120 lines.

- [ ] **Step 5: Append to `.gitignore`**

```gitignore
# Lo-fi YouTube secrets
lofi_batch/secrets/
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest lofi_batch/tests/test_prompt_schema.py -v`
Expected: PASS (install pytest if missing: `pip install pytest`)

- [ ] **Step 7: Commit**

```bash
git add lofi_batch/__init__.py lofi_batch/prompt_schema.py lofi_batch/rules/lofi_rules.md \
  lofi_batch/tests/test_prompt_schema.py .gitignore
git commit -m "feat(lofi): add prompt schema, rules, and secrets gitignore"
```

---

### Task 2: Package / queue / state helpers

**Files:**
- Create: `lofi_batch/package.py`
- Create: `lofi_batch/tests/test_package.py`

**Interfaces:**
- Consumes: none from Task 1 required at runtime (slug already validated)
- Produces:
  - `OUT_ROOT = Path(...)`
  - `new_package_dir(out_root, run_id, slug) -> Path`
  - `write_meta(package_dir, **fields) -> Path`
  - `read_meta(package_dir) -> dict`
  - `mark_ready(package_dir) -> None` (asserts required files)
  - `list_ready_packages(queue_root) -> list[Path]` (oldest first)
  - `load_state(path) -> dict` / `save_state(path, data) -> None`
  - `already_published_today(state, today: str) -> bool`
  - Required ready files: `playlist.wav`, `cover.png`, `video.mp4`, `meta.json`, `prompt.json`

- [ ] **Step 1: Write failing tests**

```python
# lofi_batch/tests/test_package.py
from pathlib import Path
from lofi_batch.package import (
    already_published_today,
    list_ready_packages,
    load_state,
    mark_ready,
    new_package_dir,
    save_state,
    write_meta,
)


def _touch(p: Path, size: int = 10) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * size)


def test_mark_ready_and_list_order(tmp_path: Path):
    queue = tmp_path / "queue"
    a = new_package_dir(tmp_path, "2026-08-04_1000", "alpha")
    b = new_package_dir(tmp_path, "2026-08-04_1100", "beta")
    for d in (a, b):
        for name in ("playlist.wav", "cover.png", "video.mp4", "prompt.json"):
            _touch(d / name)
        write_meta(d, status="generating", title="t", description="d", tags=["x"])
        mark_ready(d)
    ready = list_ready_packages(queue)
    assert [p.name for p in ready] == ["2026-08-04_1000_alpha", "2026-08-04_1100_beta"]


def test_daily_cap_state(tmp_path: Path):
    state_path = tmp_path / "state.json"
    save_state(state_path, {"last_publish_date": "2026-08-04", "last_video_id": "abc"})
    st = load_state(state_path)
    assert already_published_today(st, "2026-08-04") is True
    assert already_published_today(st, "2026-08-05") is False
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `python -m pytest lofi_batch/tests/test_package.py -v`

- [ ] **Step 3: Implement `package.py`**

```python
# lofi_batch/package.py
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_ROOT = ROOT / "output" / "lofi_batch"
REQUIRED_READY = ("playlist.wav", "cover.png", "video.mp4", "prompt.json", "meta.json")


def new_package_dir(out_root: Path, run_id: str, slug: str) -> Path:
    d = out_root / "queue" / f"{run_id}_{slug}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_meta(package_dir: Path, **fields: Any) -> Path:
    path = package_dir / "meta.json"
    data = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    data.update(fields)
    data.setdefault("updated_at", datetime.now().isoformat())
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def read_meta(package_dir: Path) -> dict[str, Any]:
    return json.loads((package_dir / "meta.json").read_text(encoding="utf-8"))


def mark_ready(package_dir: Path) -> None:
    missing = [n for n in REQUIRED_READY if n != "meta.json" and not (package_dir / n).exists()]
    meta_path = package_dir / "meta.json"
    if not meta_path.exists():
        missing.append("meta.json")
    for n in ("playlist.wav", "cover.png", "video.mp4"):
        p = package_dir / n
        if p.exists() and p.stat().st_size <= 0:
            missing.append(f"{n}(empty)")
    if missing:
        raise FileNotFoundError(f"Cannot mark ready, missing: {missing}")
    write_meta(package_dir, status="ready")


def list_ready_packages(queue_root: Path) -> list[Path]:
    if not queue_root.exists():
        return []
    ready: list[Path] = []
    for d in sorted(queue_root.iterdir()):
        if not d.is_dir():
            continue
        meta = d / "meta.json"
        if not meta.exists():
            continue
        data = json.loads(meta.read_text(encoding="utf-8"))
        if data.get("status") != "ready":
            continue
        if all((d / n).exists() and (d / n).stat().st_size > 0 for n in ("playlist.wav", "cover.png", "video.mp4")):
            ready.append(d)
    return ready


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def already_published_today(state: dict[str, Any], today: str) -> bool:
    return state.get("last_publish_date") == today
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m pytest lofi_batch/tests/test_package.py -v`

- [ ] **Step 5: Commit**

```bash
git add lofi_batch/package.py lofi_batch/tests/test_package.py
git commit -m "feat(lofi): add queue package and publish-state helpers"
```

---

### Task 3: `make_video.py` (static cover + audio)

**Files:**
- Create: `lofi_batch/make_video.py`
- Create: `lofi_batch/tests/test_make_video.py`

**Interfaces:**
- Produces: `make_still_video(cover: Path, audio: Path, out_mp4: Path, *, force: bool = False) -> Path`

- [ ] **Step 1: Write failing test** (skip if no ffmpeg)

```python
# lofi_batch/tests/test_make_video.py
import shutil
import subprocess
from pathlib import Path
import pytest
from lofi_batch.make_video import make_still_video

ffmpeg = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(not ffmpeg, reason="ffmpeg not installed")


def test_make_still_video(tmp_path: Path):
    cover = tmp_path / "cover.png"
    audio = tmp_path / "a.wav"
    out = tmp_path / "video.mp4"
    # 1x1 png via ffmpeg
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=blue:s=1280x720:d=1", "-frames:v", "1", str(cover)], check=True)
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "sine=f=440:d=2", str(audio)], check=True)
    result = make_still_video(cover, audio, out)
    assert result.exists() and result.stat().st_size > 0
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```python
# lofi_batch/make_video.py
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def make_still_video(cover: Path, audio: Path, out_mp4: Path, *, force: bool = False) -> Path:
    if out_mp4.exists() and out_mp4.stat().st_size > 0 and not force:
        return out_mp4
    if not cover.exists() or cover.stat().st_size <= 0:
        raise FileNotFoundError(cover)
    if not audio.exists() or audio.stat().st_size <= 0:
        raise FileNotFoundError(audio)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-framerate", "1",
        "-i", str(cover),
        "-i", str(audio),
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-movflags", "+faststart",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True)
    return out_mp4


def main() -> None:
    p = argparse.ArgumentParser(description="Mux still cover + audio into YouTube MP4")
    p.add_argument("--cover", type=Path, required=True)
    p.add_argument("--audio", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    out = make_still_video(args.cover, args.audio, args.out, force=args.force)
    print(out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests — PASS**

- [ ] **Step 5: Commit**

```bash
git add lofi_batch/make_video.py lofi_batch/tests/test_make_video.py
git commit -m "feat(lofi): mux static cover and playlist into video.mp4"
```

---

### Task 4: Extend audio batch for single package prompt

**Files:**
- Modify: `lofi_batch/run_batch.py`
- Create: `lofi_batch/tests/test_run_batch_package.py` (unit-test helpers only; do not call ACE-Step)

**Interfaces:**
- Produces: `process_package_audio(package_dir: Path, prompt: str, *, tracks, duration, config_path, lm_model, backend, fail_fast) -> dict` writing under `package_dir` (tracks/, playlist.wav, lyrics.txt, manifest.json) using existing `_run_generate` / `_ffmpeg_concat` logic.
- CLI: `--package-dir PATH` mutually exclusive with scanning all prompts; reads `prompt.json` for `music_prompt` + `slug`.

- [ ] **Step 1: Refactor existing `_process_prompt` so `prompt_dir` can be an absolute package dir** (not only `run_dir / slug`). Extract:

```python
def _process_prompt_dir(
    *,
    slug: str,
    prompt: str,
    prompt_dir: Path,
    tracks: int,
    duration: int,
    config_path: str,
    lm_model: str,
    backend: str,
    fail_fast: bool,
) -> dict:
    # same body as current _process_prompt but uses prompt_dir directly
    ...
```

Keep `_process_prompt(..., run_dir)` as wrapper: `prompt_dir = run_dir / slug`.

- [ ] **Step 2: Add `process_package_audio` + CLI `--package-dir`**

When `--package-dir` set:
1. Load `prompt.json` via `prompt_schema.validate_prompt`
2. Call `_process_prompt_dir` with that directory
3. Do not write `batch_summary.json` multi-prompt loop (or write single-entry summary inside package)

- [ ] **Step 3: Unit test that resume skip works with temp fake wavs** (monkeypatch `_run_generate` to create empty-then-filled files, or only test “playlist exists → skipped” by creating playlist.wav)

```python
def test_skips_when_playlist_exists(tmp_path, monkeypatch):
    # create package with playlist.wav; ensure _run_generate not called
    ...
```

- [ ] **Step 4: Commit**

```bash
git add lofi_batch/run_batch.py lofi_batch/tests/test_run_batch_package.py
git commit -m "feat(lofi): generate playlist audio into a queue package dir"
```

---

### Task 5: `generate_prompt.py` (local Qwen)

**Files:**
- Create: `lofi_batch/generate_prompt.py`
- Create: `lofi_batch/tests/test_generate_prompt_parse.py` (no GPU: test repair path with fake `complete_fn`)

**Interfaces:**
- Produces: `generate_prompt_dict(*, rules_path: Path, complete_fn, repair: bool = True) -> dict`
- Produces CLI writing `prompt.json` to `--out`

- [ ] **Step 1: Implement core with injectable `complete_fn(system: str, user: str) -> str`** so tests avoid loading the model.

```python
def build_user_message(rules: str) -> str:
    return (
        "Using the rules below, invent ONE new Lo-Fi piece for today. "
        "Return ONLY a JSON object with keys: slug, music_prompt, image_prompt, "
        "title, description, tags.\n\nRULES:\n" + rules
    )


def generate_prompt_dict(*, rules_path: Path, complete_fn, repair: bool = True) -> dict:
    from lofi_batch.prompt_schema import parse_prompt_payload, validate_prompt
    rules = rules_path.read_text(encoding="utf-8")
    system = "You write Lo-Fi music and cover prompts. Output JSON only."
    raw = complete_fn(system, build_user_message(rules))
    try:
        return validate_prompt(parse_prompt_payload(raw))
    except Exception as first_err:
        if not repair:
            raise
        raw2 = complete_fn(
            system,
            "Fix this into valid JSON only with the required keys. Error: "
            f"{first_err}\n\nOUTPUT:\n{raw}",
        )
        return validate_prompt(parse_prompt_payload(raw2))
```

- [ ] **Step 2: CLI `main()` loads Qwen like `scripts/00_generate_lyrics.py`** (`PROMPT_LLM_MODEL` env, default `Qwen/Qwen3-4B-Instruct-2507`), wraps generate, writes `--out`.

- [ ] **Step 3: Test with fake complete_fn returning valid JSON / broken then fixed**

- [ ] **Step 4: Commit**

```bash
git add lofi_batch/generate_prompt.py lofi_batch/tests/test_generate_prompt_parse.py
git commit -m "feat(lofi): generate daily prompt JSON with local Qwen"
```

---

### Task 6: `generate_cover.py` (Wan → frame)

**Files:**
- Create: `lofi_batch/generate_cover.py`

**Interfaces:**
- Produces: `generate_cover(image_prompt: str, out_png: Path, *, force: bool = False, width=1280, height=720, frames=49, steps=30) -> Path`
- Follow `scripts/06a_generate_avatar.py`: WanPipeline → temp mp4 in package → extract frame → `cover.png`; delete temp mp4 optional.

- [ ] **Step 1: Implement script with CLI `--prompt` `--out` `--force`**

Reuse `extract_png` pattern from `06a_generate_avatar.py` (copy helper into this file to avoid cross-script import pain, or import via sys.path to `scripts/` — prefer local copy of `extract_png` + `ffmpeg()`).

- [ ] **Step 2: Manual smoke only (not CI):** document command in README:

```bash
python lofi_batch/generate_cover.py --prompt "cozy rainy cafe, night, 16:9, no text" --out /tmp/cover.png
```

- [ ] **Step 3: Commit**

```bash
git add lofi_batch/generate_cover.py
git commit -m "feat(lofi): generate still cover via Wan frame extract"
```

---

### Task 7: Orchestrator `run_pipeline.py` (daily / burst)

**Files:**
- Create: `lofi_batch/run_pipeline.py`
- Modify: `lofi_batch/run_docker.sh`
- Create: `lofi_batch/run_daily.sh`, `lofi_batch/run_burst.sh`
- Modify: `lofi_batch/config.env.example`, `lofi_batch/README.md`

**Interfaces:**
- CLI: `--mode daily|burst`, `--count N`, `--skip-upload`, `--skip-cover` (optional for audio-only debug), `--run-id`
- For each package:
  1. `generate_prompt` → write `prompt.json` + seed `meta.json` status=`generating`
  2. `process_package_audio` / `run_batch --package-dir`
  3. `generate_cover` from `image_prompt`
  4. `make_still_video`
  5. `mark_ready`
- After loop: if not `skip_upload` and mode is `daily` (or env `ALWAYS_TRY_UPLOAD=1`), call `youtube_upload.main` (Task 8 — until then, `--skip-upload` default when upload module missing). For this task, gate upload behind:

```python
if not args.skip_upload:
    from lofi_batch.youtube_upload import upload_one_if_allowed
    upload_one_if_allowed(out_root)
```

If upload not implemented yet, keep `--skip-upload` default `True` until Task 8; Task 8 flips default to `False` when credentials exist.

**Preferred for Task 7:** default `SKIP_UPLOAD=1` in example until Task 9 wires real upload; pipeline must accept `--skip-upload` / env.

- [ ] **Step 1: Implement `run_pipeline.py` end-to-end with `--skip-upload` and optional `--skip-cover` / `--skip-video` for staged bring-up**

- [ ] **Step 2: Wire `run_daily.sh` / `run_burst.sh` / extend `run_docker.sh`** with `MODE`, `COUNT`, `SKIP_UPLOAD`

- [ ] **Step 3: Update README** with smoke:

```bash
TRACKS=2 DURATION=30 SKIP_UPLOAD=1 MODE=daily bash lofi_batch/run_docker.sh
```

- [ ] **Step 4: Commit**

```bash
git add lofi_batch/run_pipeline.py lofi_batch/run_daily.sh lofi_batch/run_burst.sh \
  lofi_batch/run_docker.sh lofi_batch/config.env.example lofi_batch/README.md
git commit -m "feat(lofi): orchestrate daily/burst package pipeline"
```

---

### Task 8: YouTube OAuth

**Files:**
- Create: `lofi_batch/youtube_auth.py`
- Create: `lofi_batch/secrets/.gitkeep` (directory tracked empty; secrets gitignored — use `secrets/README.md` instead of keeping secrets path if gitignore blocks; prefer `lofi_batch/YOUTUBE_SETUP.md`)
- Create: `lofi_batch/YOUTUBE_SETUP.md`
- Modify: `requirements.txt` or add `lofi_batch/requirements-youtube.txt` with:

```text
google-api-python-client>=2.0.0
google-auth-oauthlib>=1.0.0
google-auth-httplib2>=0.2.0
```

**Interfaces:**
- Produces: `get_youtube_service(secrets_dir: Path) -> Resource`
- CLI: `python lofi_batch/youtube_auth.py` runs installed-app flow; expects `secrets/client_secret.json`; writes `secrets/token.json`

- [ ] **Step 1: Write `YOUTUBE_SETUP.md`** — enable YouTube Data API v3, OAuth Desktop client, download JSON to `lofi_batch/secrets/client_secret.json`, run auth script once (browser).

- [ ] **Step 2: Implement auth module** with scopes:

```python
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]
```

- [ ] **Step 3: Commit**

```bash
git add lofi_batch/youtube_auth.py lofi_batch/YOUTUBE_SETUP.md lofi_batch/requirements-youtube.txt
git commit -m "feat(lofi): add YouTube OAuth setup helper"
```

---

### Task 9: YouTube upload + daily cap

**Files:**
- Create: `lofi_batch/youtube_upload.py`
- Create: `lofi_batch/tests/test_youtube_upload_cap.py`

**Interfaces:**
- Produces: `today_str(tz_name: str | None) -> str`
- Produces: `upload_one_if_allowed(out_root: Path, *, dry_run: bool = False, privacy: str = "public") -> dict | None`
- Behavior per spec: if already published today → return `{"status": "skipped_daily_cap"}`; else oldest ready package; on failure keep `ready` + `last_error`; on success move to `published/` and update `state.json`.

- [ ] **Step 1: Unit-test daily cap without API** (monkeypatch upload function)

```python
def test_skips_when_already_published(tmp_path, monkeypatch):
    ...
def test_dry_run_selects_oldest(tmp_path, monkeypatch):
    ...
```

- [ ] **Step 2: Implement upload using resumable media upload** (`MediaFileUpload`), set snippet from `meta.json` / `prompt.json`, set thumbnail via `thumbnails().set`.

- [ ] **Step 3: Wire into `run_pipeline.py`** (call after generation when not skip_upload). Burst mode: still call upload once at end (cap enforces 1/day) **or** skip upload in burst scripts — **spec:** burst queues only; `run_burst.sh` must pass `--skip-upload`. Daily script does not.

- [ ] **Step 4: Commit**

```bash
git add lofi_batch/youtube_upload.py lofi_batch/tests/test_youtube_upload_cap.py lofi_batch/run_pipeline.py \
  lofi_batch/run_daily.sh lofi_batch/run_burst.sh
git commit -m "feat(lofi): upload at most one YouTube video per day"
```

---

### Task 10: Daemon + cron

**Files:**
- Create: `lofi_batch/run_daemon.sh`
- Create: `lofi_batch/gpu_free.py` (small helper)
- Create: `lofi_batch/tests/test_gpu_free.py` (parse fake nvidia-smi CSV)
- Modify: `lofi_batch/crontab.example`

**Interfaces:**
- `is_gpu_free(gpu_index: int, *, util_max: float, mem_free_min_mib: int) -> bool` parsing `nvidia-smi --query-gpu=index,utilization.gpu,memory.free --format=csv,noheader,nounits`

- [ ] **Step 1: Implement + test parser**

- [ ] **Step 2: `run_daemon.sh` loop** — while true; if GPU free, run `run_daily.sh`; sleep `DAEMON_POLL_SECONDS`

- [ ] **Step 3: Update crontab to daily 03:00 + comment for daemon alternative**

- [ ] **Step 4: Commit**

```bash
git add lofi_batch/gpu_free.py lofi_batch/run_daemon.sh lofi_batch/tests/test_gpu_free.py \
  lofi_batch/crontab.example lofi_batch/README.md
git commit -m "feat(lofi): add GPU-idle daemon and daily cron example"
```

---

### Task 11: End-to-end smoke checklist (manual)

**Files:**
- Modify: `lofi_batch/README.md` (checklist section)

- [ ] **Step 1: Document and run smoke (operator / agent with GPU)**

```bash
cd /raid/user_davidoneil/virtual_singer_clip
# 1) unit tests
python -m pytest lofi_batch/tests -v
# 2) audio+cover+video package, no upload
TRACKS=2 DURATION=30 SKIP_UPLOAD=1 MODE=daily GPU=1 bash lofi_batch/run_docker.sh
# 3) OAuth once (host with browser)
pip install -r lofi_batch/requirements-youtube.txt
# place client_secret.json then:
python lofi_batch/youtube_auth.py
# 4) dry-run upload
python lofi_batch/youtube_upload.py --dry-run
# 5) real upload with unlisted
YOUTUBE_PRIVACY=unlisted python lofi_batch/youtube_upload.py
```

- [ ] **Step 2: Commit README updates**

```bash
git add lofi_batch/README.md
git commit -m "docs(lofi): add end-to-end smoke and YouTube checklist"
```

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|------------------|------|
| LLM prompt from rules (classic + odisseu-style) | 1, 5 |
| ACE-Step playlist reuse | 4, 7 |
| Wan cover still 1280×720 | 6 |
| Static image + audio MP4 | 3 |
| Queue + ready/published + state | 2, 9 |
| OAuth first-time + token | 8 |
| ≤1 upload/day | 9 |
| daily vs burst | 7, 9 |
| daemon GPU free | 10 |
| secrets gitignored | 1, 8 |
| Smoke / dry-run / resume | 3, 4, 11 |

No TBD placeholders left. Upload failure keeps `ready` + `last_error` (Task 9). Burst uses `--skip-upload` (Task 9).
