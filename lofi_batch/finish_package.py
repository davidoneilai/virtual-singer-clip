#!/usr/bin/env python3
"""Finish an existing queue package: cover → video → mark ready → optional upload."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lofi_batch.generate_cover import generate_cover  # noqa: E402
from lofi_batch.make_video import make_still_video  # noqa: E402
from lofi_batch.package import DEFAULT_OUT_ROOT, mark_ready, write_meta  # noqa: E402


def _free_cuda() -> None:
    import gc

    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:
        pass


def finish_package(package_dir: Path, *, force: bool = False) -> Path:
    package_dir = package_dir.resolve()
    prompt_path = package_dir / "prompt.json"
    playlist = package_dir / "playlist.wav"
    if not prompt_path.exists():
        raise FileNotFoundError(prompt_path)
    if not playlist.exists() or playlist.stat().st_size <= 0:
        raise FileNotFoundError(f"Missing playlist.wav in {package_dir}")

    data = json.loads(prompt_path.read_text(encoding="utf-8"))
    write_meta(
        package_dir,
        status="generating",
        title=data.get("title"),
        description=data.get("description"),
        tags=data.get("tags"),
        slug=data.get("slug"),
    )

    _free_cuda()
    cover = package_dir / "cover.png"
    generate_cover(data["image_prompt"], cover, force=force)
    _free_cuda()

    video = package_dir / "video.mp4"
    make_still_video(cover, playlist, video, force=force)
    mark_ready(package_dir)
    print(f"Ready package: {package_dir}", flush=True)
    return package_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package-dir",
        type=Path,
        required=True,
        help="Existing queue package with playlist.wav + prompt.json",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        default=os.environ.get("SKIP_UPLOAD", "1").strip() in ("1", "true", "yes"),
    )
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    args = parser.parse_args()

    finish_package(args.package_dir, force=args.force)

    if args.skip_upload:
        print("SKIP_UPLOAD set — not publishing.", flush=True)
        return

    from lofi_batch.youtube_upload import upload_one_if_allowed

    result = upload_one_if_allowed(args.out_root)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
