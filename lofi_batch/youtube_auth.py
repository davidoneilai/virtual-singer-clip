from __future__ import annotations

import argparse
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

DEFAULT_SECRETS = Path(__file__).resolve().parent / "secrets"


def get_youtube_service(secrets_dir: Path | None = None):
    secrets_dir = secrets_dir or DEFAULT_SECRETS
    client_secret = secrets_dir / "client_secret.json"
    token_path = secrets_dir / "token.json"
    if not client_secret.exists():
        raise FileNotFoundError(
            f"Missing {client_secret}. See lofi_batch/YOUTUBE_SETUP.md"
        )

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
            creds = flow.run_local_server(port=0)
        secrets_dir.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube OAuth setup for lofi_batch")
    parser.add_argument("--secrets-dir", type=Path, default=DEFAULT_SECRETS)
    args = parser.parse_args()
    service = get_youtube_service(args.secrets_dir)
    # Touch API to confirm token works
    service.channels().list(part="id", mine=True).execute()
    print(f"OK — token saved under {args.secrets_dir / 'token.json'}")


if __name__ == "__main__":
    main()
