#!/usr/bin/env python3
"""Orchestrate Lo-Fi package generation (daily / burst)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lofi_batch.generate_prompt import generate_prompt_dict, _qwen_complete  # noqa: E402
from lofi_batch.make_video import make_still_video  # noqa: E402
from lofi_batch.package import DEFAULT_OUT_ROOT, mark_ready, new_package_dir, write_meta  # noqa: E402
from lofi_batch.run_batch import process_package_audio  # noqa: E402

DEFAULT_RULES = Path(__file__).resolve().parent / "rules" / "lofi_rules.md"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes")


def build_one_package(
    *,
    out_root: Path,
    run_id: str,
    *,
    tracks: int,
    duration: int,
    config_path: str,
    lm_model: str,
    backend: str,
    fail_fast: bool,
    skip_cover: bool,
    skip_video: bool,
    rules_path: Path,
    prompt_model: str,
    force: bool,
) -> Path:
    complete_fn = _qwen_complete(prompt_model)
    data = generate_prompt_dict(rules_path=rules_path, complete_fn=complete_fn)
    package_dir = new_package_dir(out_root, run_id, data["slug"])
    (package_dir / "prompt.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_meta(
        package_dir,
        status="generating",
        title=data["title"],
        description=data["description"],
        tags=data["tags"],
        slug=data["slug"],
    )

    process_package_audio(
        package_dir,
        data["music_prompt"],
        slug=data["slug"],
        tracks=tracks,
        duration=duration,
        config_path=config_path,
        lm_model=lm_model,
        backend=backend,
        fail_fast=fail_fast,
    )

    cover = package_dir / "cover.png"
    if not skip_cover:
        from lofi_batch.generate_cover import generate_cover

        generate_cover(data["image_prompt"], cover, force=force)
    elif not cover.exists():
        raise SystemExit("--skip-cover set but cover.png missing")

    video = package_dir / "video.mp4"
    if not skip_video:
        make_still_video(cover, package_dir / "playlist.wav", video, force=force)
    elif not video.exists():
        raise SystemExit("--skip-video set but video.mp4 missing")

    mark_ready(package_dir)
    print(f"Ready package: {package_dir}", flush=True)
    return package_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["daily", "burst"], default=os.environ.get("MODE", "daily"))
    parser.add_argument("--count", type=int, default=int(os.environ.get("COUNT", "1")))
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument(
        "--run-id",
        default=os.environ.get("RUN_ID") or datetime.now().strftime("%Y-%m-%d_%H%M"),
    )
    parser.add_argument("--tracks", type=int, default=int(os.environ.get("TRACKS", "20")))
    parser.add_argument("--duration", type=int, default=int(os.environ.get("DURATION", "180")))
    parser.add_argument("--config-path", default=os.environ.get("CONFIG_PATH", "acestep-v15-xl-turbo"))
    parser.add_argument("--lm-model", default=os.environ.get("LM_MODEL", "acestep-5Hz-lm-1.7B"))
    parser.add_argument("--backend", default=os.environ.get("BACKEND", "pt"), choices=["pt", "vllm", "mlx"])
    parser.add_argument("--fail-fast", action="store_true", default=_env_bool("FAIL_FAST"))
    parser.add_argument("--skip-upload", action="store_true", default=_env_bool("SKIP_UPLOAD", True))
    parser.add_argument("--skip-cover", action="store_true", default=_env_bool("SKIP_COVER"))
    parser.add_argument("--skip-video", action="store_true", default=_env_bool("SKIP_VIDEO"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument(
        "--prompt-model",
        default=os.environ.get("PROMPT_LLM_MODEL", "Qwen/Qwen3-4B-Instruct-2507"),
    )
    args = parser.parse_args()

    n = 1 if args.mode == "daily" else max(1, args.count)
    for i in range(n):
        run_id = args.run_id if n == 1 else f"{args.run_id}_{i + 1:02d}"
        build_one_package(
            out_root=args.out_root,
            run_id=run_id,
            tracks=args.tracks,
            duration=args.duration,
            config_path=args.config_path,
            lm_model=args.lm_model,
            backend=args.backend,
            fail_fast=args.fail_fast,
            skip_cover=args.skip_cover,
            skip_video=args.skip_video,
            rules_path=args.rules,
            prompt_model=args.prompt_model,
            force=args.force,
        )

    # Burst never uploads here; daily may try unless skip_upload.
    if args.mode == "burst":
        print("Burst complete — packages queued (upload skipped by design).", flush=True)
        return

    if args.skip_upload:
        print("SKIP_UPLOAD set — not publishing.", flush=True)
        return

    from lofi_batch.youtube_upload import upload_one_if_allowed

    result = upload_one_if_allowed(args.out_root)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
