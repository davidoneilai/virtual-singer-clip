from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from common import copy, path, run
from select_video_backend import build_plan


def run_python(script: str, *args: str) -> None:
    run([sys.executable, f"scripts/{script}", *args])


def ensure_avatar_base(
    out_dir: Path,
    avatar_image: Path,
    avatar_video: Path,
    avatar_prompt: str,
) -> Path:
    if avatar_video.exists():
        return avatar_video
    if avatar_image.exists() and avatar_image.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        base_video = out_dir / "avatar_base.mp4"
        if not base_video.exists():
            run_python(
                "06a_generate_avatar.py",
                "--prompt",
                avatar_prompt,
                "--out-video",
                str(avatar_video),
                "--out-image",
                str(avatar_image),
            )
        if avatar_video.exists():
            return avatar_video
    if avatar_image.exists():
        return avatar_image
    run_python(
        "06a_generate_avatar.py",
        "--prompt",
        avatar_prompt,
        "--out-video",
        str(avatar_video),
        "--out-image",
        str(avatar_image),
    )
    if avatar_video.exists():
        return avatar_video
    if avatar_image.exists():
        return avatar_image
    raise FileNotFoundError("Could not prepare avatar base image/video.")


def run_lipsync(
    backend: str,
    base: Path,
    audio: Path,
    out: Path,
) -> None:
    if backend == "latentsync":
        run_python(
            "07_lipsync_latentsync.py",
            "--video",
            str(base),
            "--audio",
            str(audio),
            "--out",
            str(out),
        )
    elif backend == "musetalk":
        run_python(
            "07_lipsync_musetalk.py",
            "--video",
            str(base),
            "--audio",
            str(audio),
            "--out",
            str(out),
        )
    else:
        raise ValueError(f"Unknown lipsync backend: {backend}")


def run_avatar(
    backend: str,
    reference: Path,
    audio: Path,
    out: Path,
    prompt: str,
) -> None:
    if backend == "hallo3":
        run_python(
            "07_avatar_hallo3.py",
            "--reference",
            str(reference),
            "--audio",
            str(audio),
            "--out",
            str(out),
            "--prompt",
            prompt,
        )
    elif backend in {"echomimic_v2", "echomimic_v3"}:
        run_python(
            "07_avatar_echomimic.py",
            "--reference",
            str(reference),
            "--audio",
            str(audio),
            "--out",
            str(out),
            "--backend",
            backend,
            "--prompt",
            prompt,
        )
    else:
        raise ValueError(f"Unknown avatar backend: {backend}")


def assemble_wan(out_dir: Path, audio: Path, out_name: str) -> Path:
    out = out_dir / out_name
    run_python(
        "08_assemble_clip.py",
        "--scenes-dir",
        str(out_dir / "scenes"),
        "--audio",
        str(audio),
        "--out",
        str(out),
    )
    return out


def assemble_hybrid(
    out_dir: Path,
    performance: Path,
    audio: Path,
    out_name: str,
) -> Path:
    out = out_dir / out_name
    run_python(
        "09_assemble_hybrid_clip.py",
        "--lipsync",
        str(performance),
        "--scenes-dir",
        str(out_dir / "scenes"),
        "--audio",
        str(audio),
        "--out",
        str(out),
    )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Render final video for a variant output dir.")
    parser.add_argument("--out-dir", required=True, help="Variant output directory")
    parser.add_argument("--avatar-image", default="assets/avatar/reference.png")
    parser.add_argument("--avatar-video", default="assets/avatar.mp4")
    parser.add_argument(
        "--avatar-prompt",
        default="music video close-up portrait, virtual singer, confident expression, studio lighting, shoulders visible, cinematic 720p",
    )
    parser.add_argument(
        "--performance-prompt",
        default="A virtual singer performing passionately on a dynamic concert stage, cinematic lighting, expressive gestures.",
    )
    parser.add_argument("--skip-wan", action="store_true", help="Skip Wan scene generation")
    args = parser.parse_args()

    out_dir = path(args.out_dir)
    audio = out_dir / "final_audio.wav"
    scenes_json = out_dir / "scenes.json"
    if not audio.exists():
        raise FileNotFoundError(f"Missing final audio: {audio}")
    if not scenes_json.exists():
        raise FileNotFoundError(f"Missing scenes.json: {scenes_json}")

    plan = build_plan()
    for note in plan.notes:
        print(f"NOTE: {note}")

    avatar_image = path(args.avatar_image)
    avatar_video = path(args.avatar_video)
    (out_dir / "scenes").mkdir(parents=True, exist_ok=True)

    if not args.skip_wan and plan.clip_mode in {"wan", "hybrid", "avatar", "cinematic_avatar"}:
        run_python(
            "06_generate_video_wan.py",
            "--scenes",
            str(scenes_json),
            "--out-dir",
            str(out_dir / "scenes"),
        )

    final_out: Path | None = None

    if plan.clip_mode == "wan":
        final_out = assemble_wan(out_dir, audio, "final_video_wan.mp4")

    elif plan.clip_mode == "hybrid":
        if plan.lipsync_backend is None:
            print("Fallback: wan-only (no lipsync backend available).")
            final_out = assemble_wan(out_dir, audio, "final_video_wan.mp4")
        else:
            base = ensure_avatar_base(out_dir, avatar_image, avatar_video, args.avatar_prompt)
            lipsync_out = out_dir / "lipsync.mp4"
            run_lipsync(plan.lipsync_backend, base, audio, lipsync_out)
            final_out = assemble_hybrid(out_dir, lipsync_out, audio, "final_video_hybrid.mp4")

    elif plan.clip_mode == "avatar":
        if plan.avatar_backend is None:
            print("Fallback: wan-only (no avatar backend available).")
            final_out = assemble_wan(out_dir, audio, "final_video_wan.mp4")
        else:
            reference = avatar_image if avatar_image.exists() else avatar_video
            perf = out_dir / "avatar_performance.mp4"
            run_avatar(plan.avatar_backend, reference, audio, perf, args.performance_prompt)
            final_out = assemble_hybrid(out_dir, perf, audio, "final_video_avatar.mp4")

    elif plan.clip_mode == "cinematic_avatar":
        if plan.avatar_backend is None:
            print("Fallback: wan-only (no cinematic avatar backend available).")
            final_out = assemble_wan(out_dir, audio, "final_video_wan.mp4")
        else:
            reference = avatar_image if avatar_image.exists() else avatar_video
            perf = out_dir / "cinematic_avatar.mp4"
            run_avatar(plan.avatar_backend, reference, audio, perf, args.performance_prompt)
            final_out = assemble_hybrid(out_dir, perf, audio, "final_video_cinematic_avatar.mp4")

    else:
        raise ValueError(f"Unknown clip mode: {plan.clip_mode}")

    if final_out is None:
        raise RuntimeError("No final video produced.")

    legacy = out_dir / "final_videoclip.mp4"
    copy(final_out, legacy)
    print(final_out)
    print(legacy)


if __name__ == "__main__":
    main()
