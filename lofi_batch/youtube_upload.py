from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from lofi_batch.package import (
    DEFAULT_OUT_ROOT,
    already_published_today,
    list_ready_packages,
    load_state,
    read_meta,
    save_state,
    write_meta,
)


def today_str(tz_name: str | None = None) -> str:
    tz_name = tz_name or os.environ.get("TZ") or None
    if tz_name:
        now = datetime.now(ZoneInfo(tz_name))
    else:
        now = datetime.now().astimezone()
    return now.strftime("%Y-%m-%d")


def _do_upload(service, package_dir: Path, privacy: str) -> dict[str, Any]:
    from googleapiclient.http import MediaFileUpload

    meta = read_meta(package_dir)
    prompt = json.loads((package_dir / "prompt.json").read_text(encoding="utf-8"))
    title = meta.get("title") or prompt.get("title") or package_dir.name
    description = meta.get("description") or prompt.get("description") or ""
    tags = meta.get("tags") or prompt.get("tags") or []
    video_path = package_dir / "video.mp4"
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags[:500] if isinstance(tags, list) else [],
            "categoryId": "10",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _status, response = request.next_chunk()
    video_id = response["id"]
    cover = package_dir / "cover.png"
    if cover.exists():
        try:
            service.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(cover)),
            ).execute()
        except Exception as exc:  # thumbnail optional
            print(f"Thumbnail set failed (non-fatal): {exc}", flush=True)
    return {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "published_at": datetime.now().isoformat(),
        "title": title,
    }


DEFAULT_SECRETS_DIR = Path(__file__).resolve().parent / "secrets"


def upload_one_if_allowed(
    out_root: Path,
    *,
    dry_run: bool = False,
    privacy: str | None = None,
    secrets_dir: Path | None = None,
    tz_name: str | None = None,
    _uploader=None,
) -> dict[str, Any] | None:
    privacy = privacy or os.environ.get("YOUTUBE_PRIVACY", "public")
    secrets_dir = secrets_dir or DEFAULT_SECRETS_DIR
    state_path = out_root / "state.json"
    state = load_state(state_path)
    today = today_str(tz_name)
    if already_published_today(state, today):
        return {"status": "skipped_daily_cap", "date": today}

    queue_root = out_root / "queue"
    ready = list_ready_packages(queue_root)
    if not ready:
        return {"status": "no_ready_packages"}

    package_dir = ready[0]
    write_meta(package_dir, status="uploading")
    if dry_run:
        write_meta(package_dir, status="ready")
        return {
            "status": "dry_run",
            "package": str(package_dir),
            "would_publish_date": today,
        }

    try:
        if _uploader is not None:
            yt = _uploader(package_dir, privacy)
        else:
            from lofi_batch.youtube_auth import get_youtube_service

            service = get_youtube_service(secrets_dir)
            yt = _do_upload(service, package_dir, privacy)
    except Exception as exc:
        write_meta(
            package_dir,
            status="ready",
            last_error=str(exc),
            last_error_at=datetime.now().isoformat(),
        )
        raise

    (package_dir / "youtube.json").write_text(
        json.dumps(yt, indent=2) + "\n", encoding="utf-8"
    )
    write_meta(package_dir, status="published")
    published_root = out_root / "published"
    published_root.mkdir(parents=True, exist_ok=True)
    dest = published_root / package_dir.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.move(str(package_dir), str(dest))
    save_state(
        state_path,
        {
            "last_publish_date": today,
            "last_video_id": yt.get("video_id"),
            "last_package": dest.name,
        },
    )
    return {"status": "published", "package": str(dest), **yt}


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload at most one Lo-Fi video per day")
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--privacy", default=os.environ.get("YOUTUBE_PRIVACY", "public"))
    parser.add_argument("--secrets-dir", type=Path, default=DEFAULT_SECRETS_DIR)
    args = parser.parse_args()
    result = upload_one_if_allowed(
        args.out_root,
        dry_run=args.dry_run,
        privacy=args.privacy,
        secrets_dir=args.secrets_dir,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
