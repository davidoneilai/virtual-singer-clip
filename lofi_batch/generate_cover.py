from __future__ import annotations

import argparse
import gc
import os
import subprocess
from pathlib import Path

import torch
from diffusers import WanPipeline
from diffusers.utils import export_to_video


def ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def extract_png(video: Path, png: Path, frame_index: int = 8) -> None:
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


def _free_cuda() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()
        torch.cuda.synchronize()


def generate_cover(
    image_prompt: str,
    out_png: Path,
    *,
    force: bool = False,
    width: int = 1280,
    height: int = 720,
    frames: int = 17,
    steps: int = 25,
    model: str | None = None,
) -> Path:
    if out_png.exists() and out_png.stat().st_size > 0 and not force:
        return out_png
    model_id = model or os.environ.get("COVER_MODEL", "Wan-AI/Wan2.2-T2V-A14B-Diffusers")
    out_png.parent.mkdir(parents=True, exist_ok=True)
    tmp_video = out_png.with_suffix(".tmp.mp4")

    _free_cuda()

    cache = os.environ.get("HF_HOME") or os.environ.get("HUGGINGFACE_HUB_CACHE")
    pipe_kwargs: dict = {"torch_dtype": torch.bfloat16}
    if cache:
        pipe_kwargs["cache_dir"] = cache
    pipe = WanPipeline.from_pretrained(model_id, **pipe_kwargs)

    # Keep VRAM low after ACE-Step: offload + tiled VAE decode
    if hasattr(pipe, "enable_model_cpu_offload"):
        pipe.enable_model_cpu_offload()
    else:
        pipe.to("cuda")
    if hasattr(pipe, "enable_vae_tiling"):
        pipe.enable_vae_tiling()
    if hasattr(pipe, "vae") and hasattr(pipe.vae, "enable_tiling"):
        pipe.vae.enable_tiling()
    if hasattr(pipe, "vae") and hasattr(pipe.vae, "enable_slicing"):
        pipe.vae.enable_slicing()

    negative = "low quality, blurry, text, watermark, logo, letters, UI, subtitle"
    try:
        result = pipe(
            prompt=image_prompt,
            negative_prompt=negative,
            height=height,
            width=width,
            num_frames=frames,
            num_inference_steps=steps,
            guidance_scale=5.0,
        )
        export_to_video(result.frames[0], str(tmp_video), fps=16)
        del result
    finally:
        del pipe
        _free_cuda()

    extract_png(tmp_video, out_png, frame_index=min(8, max(0, frames // 2)))
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
    parser.add_argument("--frames", type=int, default=int(os.environ.get("COVER_FRAMES", "17")))
    parser.add_argument("--steps", type=int, default=int(os.environ.get("COVER_STEPS", "25")))
    args = parser.parse_args()
    out = generate_cover(
        args.prompt,
        args.out,
        force=args.force,
        width=args.width,
        height=args.height,
        frames=args.frames,
        steps=args.steps,
    )
    print(out)


if __name__ == "__main__":
    main()
