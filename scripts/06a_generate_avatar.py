from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from common import hf_hub_cache, path

import torch
from diffusers import WanPipeline
from diffusers.utils import export_to_video


def ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def extract_png(video: Path, png: Path, frame_index: int = 12) -> None:
    png.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg(),
        "-y",
        "-i",
        str(video),
        "-vf",
        f"select=eq(n\\,{frame_index})",
        "-vframes",
        "1",
        str(png),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a reusable virtual-singer avatar clip/image with Wan."
    )
    parser.add_argument("--out-video", default="assets/avatar.mp4")
    parser.add_argument("--out-image", default="assets/avatar.png")
    parser.add_argument("--model", default="Wan-AI/Wan2.2-T2V-A14B-Diffusers")
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--frames", type=int, default=49, help="Shorter clip for MuseTalk source")
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument(
        "--prompt",
        default=(
            "music video close-up portrait, young female pop singer, confident expression, "
            "looking at camera, studio lighting, sharp face details, neutral background, "
            "shoulders visible, cinematic 24fps, 720p, photorealistic"
        ),
    )
    parser.add_argument("--force", action="store_true", help="Regenerate even if avatar exists")
    args = parser.parse_args()

    out_video = path(args.out_video)
    out_image = path(args.out_image)
    if out_video.exists() and out_image.exists() and not args.force:
        print(f"Avatar already exists: {out_video} + {out_image}")
        return

    out_video.parent.mkdir(parents=True, exist_ok=True)

    pipe = WanPipeline.from_pretrained(
        args.model,
        torch_dtype=torch.bfloat16,
        cache_dir=str(hf_hub_cache()),
    )
    pipe.to("cuda")

    negative = "low quality, blurry, distorted face, bad hands, text, watermark, logo, side profile"
    result = pipe(
        prompt=args.prompt,
        negative_prompt=negative,
        height=args.height,
        width=args.width,
        num_frames=args.frames,
        num_inference_steps=args.steps,
        guidance_scale=5.0,
    )
    export_to_video(result.frames[0], str(out_video), fps=args.fps)
    extract_png(out_video, out_image)
    print(out_video)
    print(out_image)


if __name__ == "__main__":
    main()
