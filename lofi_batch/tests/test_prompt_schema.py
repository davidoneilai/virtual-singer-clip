from lofi_batch.prompt_schema import parse_prompt_payload, validate_prompt, slugify


def test_slugify_filesystem_safe():
    assert slugify("Rainy Cafe #1!") == "rainy_cafe_1"


def test_parse_and_validate_ok():
    raw = """{
      "slug": "rainy_cafe",
      "music_prompt": "soft piano lo-fi\\n\\nNEGATIVE PROMPT\\nNO vocals",
      "image_prompt": "cozy rainy cafe window, night, 16:9, no text",
      "title": "Rainy Cafe Lo-Fi",
      "description": "Chill instrumental playlist.",
      "tags": ["lofi", "rain", "study"]
    }"""
    data = validate_prompt(parse_prompt_payload(raw))
    assert data["slug"] == "rainy_cafe"
    assert "NEGATIVE PROMPT" in data["music_prompt"]
    assert data["tags"] == ["lofi", "rain", "study"]


def test_parse_rejects_missing_field():
    import pytest

    with pytest.raises(ValueError):
        validate_prompt({"slug": "x"})
