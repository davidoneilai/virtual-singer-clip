from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def make_still_video(
    cover: Path, audio: Path, out_mp4: Path, *, force: bool = False
) -> Path:
    if out_mp4.exists() and out_mp4.stat().st_size > 0 and not force:
        return out_mp4
    if not cover.exists() or cover.stat().st_size <= 0:
        raise FileNotFoundError(cover)
    if not audio.exists() or audio.stat().st_size <= 0:
        raise FileNotFoundError(audio)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-framerate",
        "1",
        "-i",
        str(cover),
        "-i",
        str(audio),
        "-c:v",
        "libx264",
        "-tune",
        "stillimage",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-pix_fmt",
        "yuv420p",
        "-shortest",
        "-movflags",
        "+faststart",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True)
    return out_mp4


def main() -> None:
    p = argparse.ArgumentParser(description="Mux still cover + audio into YouTube MP4")
    p.add_argument("--cover", type=Path, required=True)
    p.add_argument("--audio", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    out = make_still_video(args.cover, args.audio, args.out, force=args.force)
    print(out)


if __name__ == "__main__":
    main()
