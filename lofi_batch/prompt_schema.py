from __future__ import annotations

import json
import re
from typing import Any

REQUIRED_FIELDS = (
    "slug",
    "music_prompt",
    "image_prompt",
    "title",
    "description",
    "tags",
)


def slugify(text: str) -> str:
    s = text.strip().lower()
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        raise ValueError("slugify produced empty slug")
    return s[:80]


def parse_prompt_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("No JSON object found in model output")
    return json.loads(text[start : end + 1])


def validate_prompt(data: dict[str, Any]) -> dict[str, Any]:
    missing = [k for k in REQUIRED_FIELDS if k not in data]
    if missing:
        raise ValueError(f"Missing fields: {missing}")
    out = dict(data)
    out["slug"] = slugify(str(out["slug"]))
    for key in ("music_prompt", "image_prompt", "title", "description"):
        val = str(out[key]).strip()
        if not val:
            raise ValueError(f"Empty field: {key}")
        out[key] = val
    tags = out["tags"]
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if not isinstance(tags, list) or not tags:
        raise ValueError("tags must be a non-empty list")
    out["tags"] = [str(t).strip() for t in tags if str(t).strip()]
    if "negative prompt" not in out["music_prompt"].lower():
        raise ValueError("music_prompt must include a NEGATIVE PROMPT section")
    return out
