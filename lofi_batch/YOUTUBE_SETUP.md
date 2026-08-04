# YouTube OAuth setup (lofi_batch)

1. Open [Google Cloud Console](https://console.cloud.google.com/) and create/select a project.
2. Enable **YouTube Data API v3**.
3. Configure OAuth consent screen (External or Internal). Add your Google account as a test user if the app is in testing.
4. Create credentials → **OAuth client ID** → Application type **Desktop app**.
5. Download the JSON and save it as:

```text
lofi_batch/secrets/client_secret.json
```

6. Install deps and run the one-time auth flow (needs a browser):

```bash
pip install -r lofi_batch/requirements-youtube.txt
python lofi_batch/youtube_auth.py
```

7. A `lofi_batch/secrets/token.json` refresh token is written. Keep `secrets/` out of git.

8. Prefer first real uploads with:

```bash
YOUTUBE_PRIVACY=unlisted python lofi_batch/youtube_upload.py
```

Then switch to `public` when ready.
