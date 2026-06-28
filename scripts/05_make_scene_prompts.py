from __future__ import annotations

import argparse
import json

from common import path, read_text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lyrics", default="output/lyrics.txt")
    parser.add_argument("--out", default="output/scenes.json")
    parser.add_argument("--num-scenes", type=int, default=12)
    parser.add_argument(
        "--visual-style",
        default=(
            "cinematic Brazilian samba-pop music video, warm street lights, Rio night, "
            "virtual female singer, colorful percussion, dancing crowd, handheld camera, "
            "high detail, 24fps, 720p"
        ),
    )
    args = parser.parse_args()

    lyrics = read_text(args.lyrics)
    visual_style = args.visual_style

    scenes = []
    for i in range(args.num_scenes):
        scenes.append(
            {
                "id": i,
                "prompt": (
                    f"{visual_style}. Scene {i + 1}: expressive performance matching this original lyric mood: "
                    f"{lyrics[:900]}"
                ),
            }
        )

    out = path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scenes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
