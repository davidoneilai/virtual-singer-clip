from __future__ import annotations

import json
from pathlib import Path

from lofi_batch.generate_prompt import build_user_message, generate_prompt_dict


def test_generate_prompt_valid(tmp_path: Path):
    rules = tmp_path / "rules.md"
    rules.write_text("be lofi", encoding="utf-8")

    def complete(system: str, user: str) -> str:
        return json.dumps(
            {
                "slug": "midnight_bus",
                "music_prompt": "soft keys\n\nNEGATIVE PROMPT\nNO vocals",
                "image_prompt": "empty night bus stop, rain, 16:9, no text",
                "title": "Midnight Bus Lo-Fi",
                "description": "Quiet ride home.",
                "tags": ["lofi", "night"],
            }
        )

    data = generate_prompt_dict(rules_path=rules, complete_fn=complete)
    assert data["slug"] == "midnight_bus"
    assert "be lofi" in build_user_message(rules.read_text(encoding="utf-8"))


def test_generate_prompt_repair(tmp_path: Path):
    rules = tmp_path / "rules.md"
    rules.write_text("rules", encoding="utf-8")
    calls = {"n": 0}

    def complete(system: str, user: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return "not json at all"
        return json.dumps(
            {
                "slug": "ok",
                "music_prompt": "x\n\nNEGATIVE PROMPT\nNO drums",
                "image_prompt": "scene",
                "title": "t",
                "description": "d",
                "tags": ["lofi"],
            }
        )

    data = generate_prompt_dict(rules_path=rules, complete_fn=complete, repair=True)
    assert data["slug"] == "ok"
    assert calls["n"] == 2
