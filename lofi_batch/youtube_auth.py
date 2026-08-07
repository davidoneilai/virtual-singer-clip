from __future__ import annotations

import argparse
import urllib.parse
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


def _run_manual_flow(flow: InstalledAppFlow, port: int):
    """No local server needed: user pastes the final redirect URL from the browser."""
    redirect_uri = f"http://127.0.0.1:{port}/"
    flow.redirect_uri = redirect_uri
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    print(
        "\n=== Manual OAuth (sem browser/túnel no servidor) ===\n"
        "1) No laptop, abra esta URL no browser:\n"
        f"\n{auth_url}\n\n"
        "2) Faça login na conta do canal e clique em Permitir.\n"
        "3) O browser vai falhar ao abrir 127.0.0.1 "
        "(normal). Na barra de endereço, copie a URL INTEIRA "
        f"(começa com {redirect_uri}?code=... ou tem &code=).\n"
        "4) Cole abaixo e pressione Enter.\n",
        flush=True,
    )
    raw = input("Cole a URL de redirect (ou só o code=): ").strip()
    if not raw:
        raise SystemExit("Empty input")
    if raw.startswith("http://") or raw.startswith("https://"):
        # authorization_response must match redirect_uri host; normalize if needed
        parsed = urllib.parse.urlparse(raw)
        qs = urllib.parse.parse_qs(parsed.query)
        if "code" not in qs:
            raise SystemExit("URL sem parâmetro code=. Copie a URL completa da barra.")
        # Use fetch_token with code directly to avoid redirect_uri host mismatch
        code = qs["code"][0]
        flow.fetch_token(code=code)
    else:
        # pasted bare code
        code = raw
        if code.startswith("code="):
            code = code.split("=", 1)[1]
        code = code.split("&")[0]
        flow.fetch_token(code=code)
    return flow.credentials


def get_youtube_service(
    secrets_dir: Path | None = None,
    *,
    open_browser: bool = True,
    port: int = 8090,
    manual: bool = False,
):
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
            if manual:
                creds = _run_manual_flow(flow, port)
            elif open_browser:
                creds = flow.run_local_server(port=port)
            else:
                print(
                    "\n=== Headless OAuth (túnel SSH) ===\n"
                    f"No laptop: ssh -L {port}:127.0.0.1:{port} user@gpu-host\n"
                    "Depois abra a URL abaixo no browser do laptop.\n"
                    "Se falhar de novo, use: python lofi_batch/youtube_auth.py --manual\n",
                    flush=True,
                )
                creds = flow.run_local_server(port=port, open_browser=False)
        secrets_dir.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        print(f"Saved token → {token_path}", flush=True)
    return build("youtube", "v3", credentials=creds)


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube OAuth setup for lofi_batch")
    parser.add_argument("--secrets-dir", type=Path, default=DEFAULT_SECRETS)
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open a local browser (use SSH -L tunnel from your laptop)",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Print URL; after login, paste the redirect URL/code (best on GPU servers)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8090,
        help="OAuth callback port (default 8090)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only check that token.json works (no new OAuth flow)",
    )
    args = parser.parse_args()

    if args.validate_only:
        token_path = args.secrets_dir / "token.json"
        if not token_path.exists():
            raise SystemExit(f"Missing {token_path}. Auth elsewhere and copy it here.")
        service = get_youtube_service(args.secrets_dir, manual=False, open_browser=False)
    else:
        service = get_youtube_service(
            args.secrets_dir,
            open_browser=not args.no_browser and not args.manual,
            port=args.port,
            manual=args.manual,
        )

    resp = service.channels().list(part="snippet,id", mine=True).execute()
    items = resp.get("items") or []
    if not items:
        print("OK token, but no channel returned for this account.", flush=True)
    else:
        ch = items[0]
        title = ch.get("snippet", {}).get("title", "?")
        print(f"OK — authorized as channel: {title} ({ch.get('id')})", flush=True)
    print(f"Token file: {args.secrets_dir / 'token.json'}", flush=True)


if __name__ == "__main__":
    main()
