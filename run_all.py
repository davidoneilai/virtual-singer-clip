from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import common  # noqa: F401  — configure HF/torch cache before child scripts run

ROOT = Path(__file__).resolve().parent


def run(script: str, *args: str) -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / script), *args], check=True)


def main() -> None:
    run("00_generate_lyrics.py")
    run("01_generate_song_acestep.py")
    run("02_split_stems_demucs.py")
    run("04_finalize_audio.py", "--mode", "song")
    run("05_make_scene_prompts.py")
    run("06_generate_video_wan.py")
    run("08_assemble_clip.py")


if __name__ == "__main__":
    main()
