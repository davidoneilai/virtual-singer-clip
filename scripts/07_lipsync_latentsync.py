from __future__ import annotations

import argparse
import os
import sys

from common import backend_python, backend_repo, copy, path, run


def main() -> None:
    parser = argparse.ArgumentParser(description="LatentSync 1.6 lip-sync on a base avatar video.")
    parser.add_argument("--video", required=True, help="Base avatar video (mp4) or image")
    parser.add_argument("--audio", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--inference-steps", type=int, default=30)
    parser.add_argument("--guidance-scale", type=float, default=1.5)
    args = parser.parse_args()

    repo = backend_repo("latentsync")
    ckpt = repo / "checkpoints" / "latentsync_unet.pt"
    if not ckpt.exists():
        raise FileNotFoundError(
            f"LatentSync checkpoint missing: {ckpt}\nRun: bash scripts/setup_latentsync.sh"
        )

    video = path(args.video)
    audio = path(args.audio)
    out = path(args.out)
    if not video.exists():
        raise FileNotFoundError(f"Video/image not found: {video}")
    if not audio.exists():
        raise FileNotFoundError(f"Audio not found: {audio}")

    py = backend_python("latentsync")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo.resolve()) + os.pathsep + env.get("PYTHONPATH", "")

    run(
        [
            str(py),
            "-m",
            "scripts.inference",
            "--unet_config_path",
            str((repo / "configs" / "unet" / "stage2_512.yaml").resolve()),
            "--inference_ckpt_path",
            str(ckpt.resolve()),
            "--inference_steps",
            str(args.inference_steps),
            "--guidance_scale",
            str(args.guidance_scale),
            "--enable_deepcache",
            "--video_path",
            str(video.resolve()),
            "--audio_path",
            str(audio.resolve()),
            "--video_out_path",
            str(out.resolve()),
        ],
        cwd=repo,
        env=env,
    )
    print(out)


if __name__ == "__main__":
    main()
