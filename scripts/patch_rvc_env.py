"""Post-install fixes for rvc/conda-env (ffmpeg path + fairseq torch.load on PyTorch 2.6+)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from common import rvc_python


def _fairseq_checkpoint_utils() -> Path:
    import subprocess

    out = subprocess.check_output(
        [str(rvc_python()), "-c", "import fairseq.checkpoint_utils as m; print(m.__file__)"],
        text=True,
    ).strip()
    return Path(out)


def patch_fairseq_torch_load() -> None:
    path = _fairseq_checkpoint_utils()
    text = path.read_text(encoding="utf-8")
    marker = "weights_only=False"
    if marker in text:
        print(f"fairseq torch.load already patched: {path}")
        return

    updated, n = re.subn(
        r"torch\.load\(([^)]*map_location=torch\.device\(\"cpu\"\)[^)]*)\)",
        r"torch.load(\1, weights_only=False)",
        text,
    )
    if n == 0:
        old = 'state = torch.load(f, map_location=torch.device("cpu"))'
        new = 'state = torch.load(f, map_location=torch.device("cpu"), weights_only=False)'
        if old not in text:
            raise RuntimeError(f"Could not patch torch.load in {path}")
        updated = text.replace(old, new, 1)
        n = 1

    path.write_text(updated, encoding="utf-8")
    print(f"Patched fairseq torch.load ({n}x): {path}")


def check_ffmpeg() -> None:
    bin_dir = rvc_python().resolve().parent
    ffmpeg = bin_dir / "ffmpeg"
    if ffmpeg.exists():
        print(f"ffmpeg ok: {ffmpeg}")
        return
    raise FileNotFoundError(
        f"ffmpeg not found in RVC env ({bin_dir}).\n"
        "Run: conda install -y -p rvc/conda-env -c conda-forge ffmpeg"
    )


def main() -> None:
    patch_fairseq_torch_load()
    check_ffmpeg()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"patch_rvc_env failed: {exc}", file=sys.stderr)
        raise
