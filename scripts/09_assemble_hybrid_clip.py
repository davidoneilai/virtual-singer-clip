from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg

from common import path, write_text


def ffmpeg() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def probe_duration(file_path: Path) -> float:
    cmd = [
        ffmpeg(),
        "-hide_banner",
        "-i",
        str(file_path),
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    for line in proc.stderr.splitlines():
        if "Duration:" in line:
            h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError(f"Could not probe duration for {file_path}")


def extract_segment(src: Path, dst: Path, start: float, duration: float) -> None:
    cmd = [
        ffmpeg(),
        "-y",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(src),
        "-t",
        f"{duration:.3f}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-an",
        str(dst),
    ]
    subprocess.run(cmd, check=True)


def normalize_clip(src: Path, dst: Path, width: int, height: int, fps: int) -> None:
    cmd = [
        ffmpeg(),
        "-y",
        "-i",
        str(src),
        "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-an",
        str(dst),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hybrid clip: lip-sync performance segments interleaved with Wan B-roll."
    )
    parser.add_argument("--lipsync", default="output/lipsync.mp4")
    parser.add_argument("--scenes-dir", default="output/scenes")
    parser.add_argument("--audio", default="output/final_audio.wav")
    parser.add_argument("--out", default="output/final_videoclip.mp4")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=int, default=24)
    args = parser.parse_args()

    lipsync = path(args.lipsync)
    scenes_dir = path(args.scenes_dir)
    audio = path(args.audio)
    out = path(args.out)

    scene_files = sorted(scenes_dir.glob("scene_*.mp4"))
    if not scene_files:
        raise FileNotFoundError(f"No scene_*.mp4 in {scenes_dir}")
    if not lipsync.exists():
        raise FileNotFoundError(f"Lip-sync video not found: {lipsync}")

    duration = probe_duration(lipsync)
    segment = duration / len(scene_files)

    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vsc_hybrid_") as tmp:
        tmp_dir = Path(tmp)
        parts: list[Path] = []

        for index, scene in enumerate(scene_files):
            lip_part = tmp_dir / f"part_{index:02d}_lipsync.mp4"
            broll_part = tmp_dir / f"part_{index:02d}_broll.mp4"
            extract_segment(lipsync, lip_part, start=index * segment, duration=segment)
            normalize_clip(scene, broll_part, args.width, args.height, args.fps)
            parts.extend([lip_part, broll_part])

        concat_file = tmp_dir / "concat.txt"
        write_text(concat_file, "".join(f"file '{p.resolve()}'\n" for p in parts))

        video_only = tmp_dir / "video_only.mp4"
        subprocess.run(
            [
                ffmpeg(),
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(video_only),
            ],
            check=True,
        )

        subprocess.run(
            [
                ffmpeg(),
                "-y",
                "-i",
                str(video_only),
                "-i",
                str(audio),
                "-shortest",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(out),
            ],
            check=True,
        )

    print(out)


if __name__ == "__main__":
    main()
