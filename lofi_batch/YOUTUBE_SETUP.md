# YouTube OAuth setup (lofi_batch)

1. Open [Google Cloud Console](https://console.cloud.google.com/) and create/select a project.
2. Enable **YouTube Data API v3**.
3. Configure OAuth consent screen (External or Internal). Add your Google account as a test user if the app is in testing.
4. Create credentials → **OAuth client ID** → Application type **Desktop app**.
5. Download the JSON and save it as:

```text
lofi_batch/secrets/client_secret.json
```

## Auth on a GPU server (no browser)

**Option A — manual paste (recommended, no SSH tunnel)**

Inside the container / on the server:

```bash
pip install -r lofi_batch/requirements-youtube.txt
python lofi_batch/youtube_auth.py --manual
```

1. Copy the printed URL into your **laptop browser**.
2. Log in and click Allow.
3. The page will fail to load `127.0.0.1` — that is expected.
4. From the browser address bar, copy the **full URL** (it contains `code=`).
5. Paste it into the terminal and press Enter.

`lofi_batch/secrets/token.json` is written automatically.

**Option B — SSH tunnel**

On your **laptop**:

```bash
ssh -L 8090:127.0.0.1:8090 user@gpu-host
```

On the **host** (not inside Docker unless you published `-p 8090:8090`):

```bash
python lofi_batch/youtube_auth.py --no-browser --port 8090
```

**Option C — Auth on laptop, copy token**

On a machine with a browser (same `client_secret.json`):

```bash
python lofi_batch/youtube_auth.py
scp token.json user@gpu-host:/raid/user_davidoneil/virtual_singer_clip/lofi_batch/secrets/token.json
```

Validate on the server:

```bash
python lofi_batch/youtube_auth.py --validate-only
```

## After auth

```bash
YOUTUBE_PRIVACY=unlisted python lofi_batch/youtube_upload.py --dry-run
YOUTUBE_PRIVACY=unlisted python lofi_batch/youtube_upload.py
```

Keep `lofi_batch/secrets/` out of git.
