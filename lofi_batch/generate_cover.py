from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

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


def generate_cover(
    image_prompt: str,
    out_png: Path,
    *,
    force: bool = False,
    width: int = 1280,
    height: int = 720,
    frames: int = 49,
    steps: int = 30,
    model: str | None = None,
) -> Path:
    if out_png.exists() and out_png.stat().st_size > 0 and not force:
        return out_png
    model_id = model or os.environ.get("COVER_MODEL", "Wan-AI/Wan2.2-T2V-A14B-Diffusers")
    out_png.parent.mkdir(parents=True, exist_ok=True)
    tmp_video = out_png.with_suffix(".tmp.mp4")

    cache = os.environ.get("HF_HOME") or os.environ.get("HUGGINGFACE_HUB_CACHE")
    pipe_kwargs = {"torch_dtype": torch.bfloat16}
    if cache:
        pipe_kwargs["cache_dir"] = cache
    pipe = WanPipeline.from_pretrained(model_id, **pipe_kwargs)
    pipe.to("cuda")

    negative = "low quality, blurry, text, watermark, logo, letters, UI, subtitle"
    result = pipe(
        prompt=image_prompt,
        negative_prompt=negative,
        height=height,
        width=width,
        num_frames=frames,
        num_inference_steps=steps,
        guidance_scale=5.0,
    )
    export_to_video(result.frames[0], str(tmp_video), fps=24)
    extract_png(tmp_video, out_png)
    try:
        tmp_video.unlink(missing_ok=True)
    except OSError:
        pass
    return out_png


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate still cover via Wan frame extract")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args()
    out = generate_cover(
        args.prompt,
        args.out,
        force=args.force,
        width=args.width,
        height=args.height,
    )
    print(out)


if __name__ == "__main__":
    main()
