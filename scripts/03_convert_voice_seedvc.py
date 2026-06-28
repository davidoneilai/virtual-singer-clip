from __future__ import annotations

import argparse
import sys

from common import copy, newest_file, path, run


def resolve_reference_voice(target_arg: str) -> Path:
    explicit = path(target_arg)
    if explicit.exists():
        return explicit

    default = path("assets/reference_voice.wav")
    if default.exists():
        return default

    wavs = sorted(path("assets").glob("*.wav"))
    if wavs:
        print(f"Using reference voice: {wavs[0]} (pass --target to override)")
        return wavs[0]

    raise FileNotFoundError(
        "No reference voice found. Put a licensed voice at assets/reference_voice.wav "
        "or pass --target assets/your_voice.wav"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seedvc-repo", default="external/seed-vc")
    parser.add_argument("--source", default="output/vocals.wav")
    parser.add_argument("--target", default="assets/reference_voice.wav")
    parser.add_argument("--out", default="output/converted_vocal.wav")
    parser.add_argument("--steps", type=int, default=60)
    parser.add_argument("--cfg", type=float, default=0.7)
    parser.add_argument("--tmp-dir", default="output/voice_conversion")
    args = parser.parse_args()

    repo = path(args.seedvc_repo)
    if not (repo / "inference.py").exists():
        raise FileNotFoundError(f"Seed-VC inference.py not found in {repo}")

    target = resolve_reference_voice(args.target)

    tmp_out = path(args.tmp_dir)
    tmp_out.mkdir(parents=True, exist_ok=True)

    run(
        [
            sys.executable,
            str(path("scripts/seedvc_inference.py")),
            "--source",
            str(path(args.source)),
            "--target",
            str(target),
            "--output",
            str(tmp_out),
            "--diffusion-steps",
            str(args.steps),
            "--inference-cfg-rate",
            str(args.cfg),
            "--f0-condition",
            "True",
            "--auto-f0-adjust",
            "True",
            "--fp16",
            "True",
        ],
    )

    copy(newest_file(tmp_out, "vc_*.wav"), args.out)


if __name__ == "__main__":
    main()
