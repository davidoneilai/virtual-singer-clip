import shutil
import subprocess
from pathlib import Path

import pytest

from lofi_batch.make_video import make_still_video

ffmpeg = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(not ffmpeg, reason="ffmpeg not installed")


def test_make_still_video(tmp_path: Path):
    cover = tmp_path / "cover.png"
    audio = tmp_path / "a.wav"
    out = tmp_path / "video.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=1280x720:d=1",
            "-frames:v",
            "1",
            str(cover),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=f=440:d=2", str(audio)],
        check=True,
        capture_output=True,
    )
    result = make_still_video(cover, audio, out)
    assert result.exists() and result.stat().st_size > 0
