from __future__ import annotations

import argparse
import json

from common import hf_hub_cache, path

import torch
from diffusers import WanPipeline
from diffusers.utils import export_to_video


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes", default="output/scenes.json")
    parser.add_argument("--out-dir", default="output/scenes")
    parser.add_argument("--model", default="Wan-AI/Wan2.2-T2V-A14B-Diffusers")
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--frames", type=int, default=121)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--steps", type=int, default=40)
    args = parser.parse_args()

    scenes = json.loads(path(args.scenes).read_text(encoding="utf-8"))
    out_dir = path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pipe = WanPipeline.from_pretrained(
        args.model,
        torch_dtype=torch.bfloat16,
        cache_dir=str(hf_hub_cache()),
    )
    pipe.to("cuda")

    negative = "low quality, blurry, distorted face, bad hands, text, watermark, logo"

    for scene in scenes:
        out = out_dir / f"scene_{scene['id']:02d}.mp4"
        if out.exists():
            continue
        result = pipe(
            prompt=scene["prompt"],
            negative_prompt=negative,
            height=args.height,
            width=args.width,
            num_frames=args.frames,
            num_inference_steps=args.steps,
            guidance_scale=5.0,
        )
        export_to_video(result.frames[0], str(out), fps=args.fps)
        print(out)


if __name__ == "__main__":
    main()
