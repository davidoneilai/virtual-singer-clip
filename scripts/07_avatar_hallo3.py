from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from common import backend_python, backend_repo, copy, path, run


def main() -> None:
    parser = argparse.ArgumentParser(description="Hallo3 cinematic avatar performance.")
    parser.add_argument("--reference", default="assets/avatar/reference.png")
    parser.add_argument("--audio", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--prompt",
        default="A virtual singer performing on a dynamic concert stage with cinematic lighting and expressive motion.",
    )
    args = parser.parse_args()

    repo = backend_repo("hallo3")
    if not (repo / "scripts" / "inference_long_batch.sh").exists():
        raise FileNotFoundError(f"Hallo3 repo incomplete: {repo}\nRun: bash scripts/setup_hallo3.sh")

    reference = path(args.reference)
    if not reference.exists():
        for alt in ("assets/avatar.png", "assets/avatar/reference.png"):
            candidate = path(alt)
            if candidate.exists():
                reference = candidate
                break
    if not reference.exists():
        raise FileNotFoundError(f"Reference image not found: {args.reference}")

    audio = path(args.audio)
    if not audio.exists():
        raise FileNotFoundError(f"Audio not found: {audio}")

    out = path(args.out)
    work = path("output/hallo3_tmp")
    work.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="vsc_hallo3_") as tmp:
        tmp_dir = Path(tmp)
        img = tmp_dir / "reference.jpg"
        aud = tmp_dir / "speech.wav"
        shutil.copy2(reference, img)
        shutil.copy2(audio, aud)
        input_txt = tmp_dir / "input.txt"
        write_text(input_txt, f"{args.prompt}@@{img.resolve()}@@{aud.resolve()}\n")

        py = backend_python("hallo3")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(repo.resolve()) + os.pathsep + env.get("PYTHONPATH", "")

        run(
            ["bash", "scripts/inference_long_batch.sh", str(input_txt), str(work.resolve())],
            cwd=repo,
            env=env,
        )

    produced = sorted(work.glob("**/*.mp4"), key=os.path.getmtime)
    if not produced:
        raise FileNotFoundError(f"Hallo3 produced no mp4 in {work}")
    copy(produced[-1], out)
    print(out)


if __name__ == "__main__":
    main()
