from __future__ import annotations

import argparse
import os
import sys

from common import backend_python, copy, path, run, write_text


def main() -> None:
    parser = argparse.ArgumentParser(description="MuseTalk v1.5 lip-sync (legacy fallback).")
    parser.add_argument("--musetalk-repo", default="external/MuseTalk")
    parser.add_argument("--video", default="assets/avatar.png")
    parser.add_argument("--audio", default="output/final_audio.wav")
    parser.add_argument("--out", default="output/lipsync.mp4")
    parser.add_argument("--result-name", default="lipsync_output.mp4")
    args = parser.parse_args()

    repo = path(args.musetalk_repo)
    unet = repo / "models" / "musetalkV15" / "unet.pth"
    if not unet.exists():
        raise FileNotFoundError(
            f"MuseTalk weights missing: {unet}\nRun: bash scripts/download_musetalk_weights.sh"
        )

    avatar = path(args.video)
    if not avatar.exists():
        alt = path("assets/avatar.mp4")
        avatar = alt if alt.exists() else avatar
    if not avatar.exists():
        raise FileNotFoundError("No avatar found in assets/avatar.png or assets/avatar.mp4")

    audio = path(args.audio)
    if not audio.exists():
        raise FileNotFoundError(f"Audio not found: {audio}")

    config = path("output/musetalk_inference.yaml")
    write_text(
        config,
        f"""task_0:
  video_path: "{avatar.resolve()}"
  audio_path: "{audio.resolve()}"
  result_name: "{args.result_name}"
""",
    )

    result_dir = path("output/musetalk_results")
    result_dir.mkdir(parents=True, exist_ok=True)

    py = backend_python("musetalk")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo.resolve()) + os.pathsep + env.get("PYTHONPATH", "")

    run(
        [
            str(py),
            "-m",
            "scripts.inference",
            "--inference_config",
            str(config.resolve()),
            "--result_dir",
            str(result_dir.resolve()),
            "--version",
            "v15",
            "--use_float16",
            "--unet_model_path",
            str(unet),
            "--unet_config",
            str((repo / "models" / "musetalkV15" / "musetalk.json").resolve()),
            "--whisper_dir",
            str((repo / "models" / "whisper").resolve()),
        ],
        cwd=repo,
        env=env,
    )

    produced = result_dir / "v15" / args.result_name
    if not produced.exists():
        produced = result_dir / "v15" / f"{avatar.stem}_{audio.stem}.mp4"
    copy(produced, args.out)
    print(args.out)


if __name__ == "__main__":
    main()
