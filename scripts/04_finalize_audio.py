from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

from common import path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build final_audio.wav. Default uses song.wav from ACE-Step "
            "(best when reference voice is set at generation time)."
        )
    )
    parser.add_argument("--song", default="output/song.wav")
    parser.add_argument("--vocal", default="output/vocals.wav")
    parser.add_argument("--converted-vocal", default="output/converted_vocal.wav")
    parser.add_argument("--instrumental", default="output/instrumental.wav")
    parser.add_argument("--out", default="output/final_audio.wav")
    parser.add_argument(
        "--mode",
        choices=("song", "remix-raw", "remix-converted"),
        default="song",
        help=(
            "song: ACE-Step mix as-is; "
            "remix-raw: Demucs vocals + instrumental; "
            "remix-converted: Seed-VC vocal + instrumental"
        ),
    )
    parser.add_argument("--vocal-volume", type=float, default=1.35)
    parser.add_argument("--instrumental-volume", type=float, default=0.75)
    args = parser.parse_args()

    out = path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    song = path(args.song)

    if args.mode == "song":
        if not song.exists():
            raise FileNotFoundError(f"song not found: {song}")
        shutil.copy2(song, out)
        print(f"{out} (from {song})")
        return

    vocal = path(args.vocal if args.mode == "remix-raw" else args.converted_vocal)
    if not vocal.exists():
        raise FileNotFoundError(f"vocal not found: {vocal}")

    subprocess.run(
        [
            sys.executable,
            str(path("scripts/04_mix_audio.py")),
            "--vocal",
            str(vocal),
            "--instrumental",
            str(path(args.instrumental)),
            "--out",
            str(out),
            "--vocal-volume",
            str(args.vocal_volume),
            "--instrumental-volume",
            str(args.instrumental_volume),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
