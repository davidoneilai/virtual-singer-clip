from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from common import backend_python, backend_repo, copy, path, run


def ensure_pose_dir(repo: Path, pose_name: str) -> Path:
    custom = os.environ.get("VSC_ECHOMIMIC_POSE_DIR")
    if custom:
        pose_dir = path(custom)
        if (pose_dir / pose_name).exists():
            return pose_dir
    demo_pose = repo / "assets" / "halfbody_demo" / "pose" / pose_name
    if demo_pose.exists():
        return demo_pose.parent
    raise FileNotFoundError(
        "EchoMimicV2 needs a pose sequence directory. "
        "Set VSC_ECHOMIMIC_POSE_DIR or install demo assets in the repo."
    )


def run_v2(reference: Path, audio: Path, out: Path, version: str) -> None:
    repo = backend_repo("echomimic_v2")
    py = backend_python("echomimic")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo.resolve()) + os.pathsep + env.get("PYTHONPATH", "")

    pose_name = os.environ.get("VSC_ECHOMIMIC_POSE", "01")
    with tempfile.TemporaryDirectory(prefix="vsc_em_v2_") as tmp:
        tmp_dir = Path(tmp)
        ref_dir = tmp_dir / "ref"
        aud_dir = tmp_dir / "audio"
        ref_dir.mkdir()
        aud_dir.mkdir()
        ref_file = ref_dir / "reference.png"
        aud_file = aud_dir / "speech.wav"
        shutil.copy2(reference, ref_file)
        shutil.copy2(audio, aud_file)
        pose_dir = ensure_pose_dir(repo, pose_name)

        run(
            [
                str(py),
                "infer.py",
                "--config",
                "./configs/prompts/infer.yaml",
                "-W",
                os.environ.get("VSC_AVATAR_WIDTH", "768"),
                "-H",
                os.environ.get("VSC_AVATAR_HEIGHT", "768"),
                "-L",
                os.environ.get("VSC_AVATAR_FRAMES", "240"),
                "--steps",
                os.environ.get("VSC_AVATAR_STEPS", "30"),
                "--cfg",
                os.environ.get("VSC_AVATAR_CFG", "2.5"),
                "--fps",
                os.environ.get("VSC_AVATAR_FPS", "24"),
                "--ref_images_dir",
                str(ref_dir),
                "--audio_dir",
                str(aud_dir),
                "--pose_dir",
                str(pose_dir),
                "--refimg_name",
                ref_file.name,
                "--audio_name",
                aud_file.name,
                "--pose_name",
                pose_name,
            ],
            cwd=repo,
            env=env,
        )

        outputs = sorted((repo / "outputs").glob("**/*.mp4"), key=os.path.getmtime)
        if not outputs:
            raise FileNotFoundError("EchoMimicV2 produced no mp4 under external/echomimic_v2/outputs/")
        copy(outputs[-1], out)


def run_v3(reference: Path, audio: Path, out: Path, prompt: str) -> None:
    repo = backend_repo("echomimic_v3")
    py = backend_python("echomimic")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo.resolve()) + os.pathsep + env.get("PYTHONPATH", "")

    flash_model = repo / "flash" / "Wan2.1-Fun-V1.1-1.3B-InP"
    flash_ckpt = repo / "flash" / "transformer" / "diffusion_pytorch_model.safetensors"
    wav2vec = repo / "flash" / "chinese-wav2vec2-base"
    script = repo / "infer_flash.py"
    if not script.exists():
        raise FileNotFoundError(f"EchoMimicV3 infer_flash.py not found in {repo}")

    for required in (flash_model, flash_ckpt, wav2vec):
        if not required.exists():
            raise FileNotFoundError(
                f"EchoMimicV3 weights missing: {required}\n"
                f"Run: huggingface-cli download BadToBest/EchoMimicV3 --local-dir {repo / 'flash'}"
            )

    save_dir = path("output/echomimic_v3_tmp")
    save_dir.mkdir(parents=True, exist_ok=True)

    run(
        [
            str(py),
            str(script.name),
            "--image_path",
            str(reference.resolve()),
            "--audio_path",
            str(audio.resolve()),
            "--prompt",
            prompt,
            "--num_inference_steps",
            os.environ.get("VSC_AVATAR_STEPS", "25"),
            "--config_path",
            "config/config.yaml",
            "--model_name",
            str(flash_model),
            "--ckpt_idx",
            "50000",
            "--transformer_path",
            str(flash_ckpt),
            "--save_path",
            str(save_dir.resolve()),
            "--wav2vec_model_dir",
            str(wav2vec),
            "--sampler_name",
            "Flow_Unipc",
            "--video_length",
            os.environ.get("VSC_AVATAR_FRAMES", "81"),
            "--guidance_scale",
            os.environ.get("VSC_AVATAR_TEXT_CFG", "6.0"),
            "--audio_guidance_scale",
            os.environ.get("VSC_AVATAR_AUDIO_CFG", "3.0"),
            "--sample_size",
            os.environ.get("VSC_AVATAR_WIDTH", "768"),
            os.environ.get("VSC_AVATAR_HEIGHT", "768"),
            "--fps",
            os.environ.get("VSC_AVATAR_FPS", "25"),
        ],
        cwd=repo,
        env=env,
    )

    produced = sorted(save_dir.glob("**/*.mp4"), key=os.path.getmtime)
    if not produced:
        produced = sorted((repo / "outputs").glob("**/*.mp4"), key=os.path.getmtime)
    if not produced:
        raise FileNotFoundError("EchoMimicV3 produced no mp4 output.")
    copy(produced[-1], out)


def main() -> None:
    parser = argparse.ArgumentParser(description="EchoMimic avatar performance.")
    parser.add_argument("--reference", default="assets/avatar/reference.png")
    parser.add_argument("--audio", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--backend",
        default=os.environ.get("VSC_AVATAR_BACKEND", "echomimic_v2"),
        choices=["echomimic_v2", "echomimic_v3"],
    )
    parser.add_argument(
        "--prompt",
        default="A virtual singer performing passionately on stage, cinematic lighting, expressive gestures.",
    )
    args = parser.parse_args()

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
    if args.backend == "echomimic_v3":
        run_v3(reference, audio, out, args.prompt)
    else:
        run_v2(reference, audio, out, args.backend)
    print(out)


if __name__ == "__main__":
    main()
