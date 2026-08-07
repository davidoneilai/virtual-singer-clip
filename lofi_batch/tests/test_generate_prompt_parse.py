from __future__ import annotations

import json
from pathlib import Path

import pytest

from lofi_batch.generate_prompt import (
    generate_image_prompt,
    generate_metadata,
    generate_music_prompt,
    generate_prompt_package,
    generate_theme,
)


def _write_rules(tmp_path: Path) -> Path:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "theme_rules.md").write_text("be lofi", encoding="utf-8")
    (rules_dir / "music_rules.md").write_text("music rules", encoding="utf-8")
    (rules_dir / "metadata_rules.md").write_text("metadata rules", encoding="utf-8")
    (rules_dir / "image_rules.md").write_text("image rules", encoding="utf-8")
    return rules_dir


def test_generate_theme(tmp_path: Path):
    rules_dir = _write_rules(tmp_path)

    def complete(system: str, user: str) -> str:
        return json.dumps({"theme": "empty night bus stop, rain, soft piano"})

    theme = generate_theme(rules_path=rules_dir / "theme_rules.md", complete_fn=complete)
    assert theme == "empty night bus stop, rain, soft piano"


def test_generate_music_prompt(tmp_path: Path):
    rules_dir = _write_rules(tmp_path)

    def complete(system: str, user: str) -> str:
        return json.dumps(
            {
                "music_prompt": "soft keys, vinyl crackle\n\nNEGATIVE PROMPT\nNO vocals",
            }
        )

    music = generate_music_prompt(
        theme="rainy bus stop",
        rules_path=rules_dir / "music_rules.md",
        complete_fn=complete,
    )
    assert "NEGATIVE PROMPT" in music


def test_generate_music_prompt_rejects_missing_negative(tmp_path: Path):
    rules_dir = _write_rules(tmp_path)

    def complete(system: str, user: str) -> str:
        return json.dumps({"music_prompt": "soft keys only"})

    with pytest.raises(ValueError, match="NEGATIVE PROMPT"):
        generate_music_prompt(
            theme="rainy bus stop",
            rules_path=rules_dir / "music_rules.md",
            complete_fn=complete,
        )


def test_generate_metadata(tmp_path: Path):
    rules_dir = _write_rules(tmp_path)

    def complete(system: str, user: str) -> str:
        return json.dumps(
            {
                "title": "Midnight Bus Lo-Fi",
                "description": "Quiet ride home.",
                "tags": ["lofi", "night"],
            }
        )

    meta = generate_metadata(
        theme="rainy bus stop",
        rules_path=rules_dir / "metadata_rules.md",
        complete_fn=complete,
    )
    assert meta["title"] == "Midnight Bus Lo-Fi"
    assert meta["tags"] == ["lofi", "night"]


def test_generate_image_prompt(tmp_path: Path):
    rules_dir = _write_rules(tmp_path)

    def complete(system: str, user: str) -> str:
        return json.dumps(
            {"image_prompt": "empty night bus stop, rain, 16:9, no text"}
        )

    image = generate_image_prompt(
        theme="rainy bus stop",
        rules_path=rules_dir / "image_rules.md",
        complete_fn=complete,
    )
    assert "16:9" in image


def test_generate_prompt_package_valid(tmp_path: Path):
    rules_dir = _write_rules(tmp_path)

    def complete(system: str, user: str) -> str:
        if "invent original Lo-Fi themes" in system:
            return json.dumps({"theme": "quiet midnight bus ride in the rain"})
        if "ACE-Step" in system:
            return json.dumps(
                {
                    "music_prompt": "soft piano, rain texture\n\nNEGATIVE PROMPT\nNO vocals",
                }
            )
        if "title, description, and tags" in user:
            return json.dumps(
                {
                    "title": "Midnight Bus Lo-Fi",
                    "description": "Quiet ride home.",
                    "tags": ["lofi", "night"],
                }
            )
        return json.dumps(
            {"image_prompt": "empty night bus stop, rain, 16:9, no text"}
        )

    data = generate_prompt_package(rules_dir=rules_dir, complete_fn=complete)
    assert data["slug"] == "midnight_bus_lo_fi"
    assert "NEGATIVE PROMPT" in data["music_prompt"]
    assert data["title"] == "Midnight Bus Lo-Fi"
    assert data["tags"] == ["lofi", "night"]


def test_generate_prompt_package_repair(tmp_path: Path):
    rules_dir = _write_rules(tmp_path)
    calls = {"n": 0}

    def complete(system: str, user: str) -> str:
        calls["n"] += 1
        # First call (theme) returns invalid text.
        if calls["n"] == 1:
            return "not json at all"
        # Subsequent calls return valid JSON.
        if "invent original Lo-Fi themes" in system:
            return json.dumps({"theme": "quiet midnight bus ride in the rain"})
        if "ACE-Step" in system:
            return json.dumps(
                {
                    "music_prompt": "soft piano\n\nNEGATIVE PROMPT\nNO vocals",
                }
            )
        if "title, description, and tags" in user:
            return json.dumps(
                {
                    "title": "Midnight Bus Lo-Fi",
                    "description": "Quiet ride home.",
                    "tags": ["lofi"],
                }
            )
        return json.dumps(
            {"image_prompt": "empty night bus stop, rain, 16:9, no text"}
        )

    data = generate_prompt_package(rules_dir=rules_dir, complete_fn=complete, repair=True)
    assert data["slug"] == "midnight_bus_lo_fi"
    assert calls["n"] >= 4
