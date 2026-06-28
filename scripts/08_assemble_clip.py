from __future__ import annotations

import argparse
import subprocess

import imageio_ffmpeg

from common import path, write_text


def ffmpeg() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes-dir", default="output/scenes")
    parser.add_argument("--audio", default="output/final_audio.wav")
    parser.add_argument("--out", default="output/final_videoclip.mp4")
    args = parser.parse_args()

    scene_files = sorted(path(args.scenes_dir).glob("scene_*.mp4"))
    if not scene_files:
        raise FileNotFoundError("No scene_*.mp4 files found")

    concat_file = path("output/concat.txt")
    write_text(concat_file, "".join(f"file '{p.resolve()}'\n" for p in scene_files))

    out = path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    audio = path(args.audio)

    cmd = [
        ffmpeg(),
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-i",
        str(audio),
        "-shortest",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(out),
    ]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    print(out)


if __name__ == "__main__":
    main()
