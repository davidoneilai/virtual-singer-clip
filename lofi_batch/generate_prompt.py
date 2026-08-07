from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable

from lofi_batch.prompt_schema import parse_prompt_payload, validate_prompt, slugify

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES_DIR = Path(__file__).resolve().parent / "rules"
DEFAULT_RULES = DEFAULT_RULES_DIR / "lofi_rules.md"


def _build_user_message(intro: str, rules: str, context: str = "") -> str:
    parts = [intro, "\nRULES:\n" + rules]
    if context:
        parts.insert(1, "\nCONTEXT:\n" + context)
    return "".join(parts)


def _extract_field(raw: str, field: str, complete_fn: Callable[[str, str], str] | None = None) -> Any:
    """Parse JSON output and return a specific field, with optional repair."""
    try:
        data = parse_prompt_payload(raw)
    except Exception as err:
        if complete_fn is None:
            raise
        repaired = complete_fn(
            "You return JSON only.",
            f"Fix this into valid JSON only. Error: {err}\n\nOUTPUT:\n{raw}",
        )
        data = parse_prompt_payload(repaired)
    if field not in data:
        raise ValueError(f"Missing field: {field}")
    return data[field]


def generate_theme(
    *,
    rules_path: Path,
    complete_fn: Callable[[str, str], str],
    repair: bool = True,
) -> str:
    rules = rules_path.read_text(encoding="utf-8")
    system = "You invent original Lo-Fi themes. Output JSON only."
    user = _build_user_message(
        "Using the rules below, invent ONE new Lo-Fi theme for today.",
        rules,
    )
    raw = complete_fn(system, user)
    try:
        return str(_extract_field(raw, "theme")).strip()
    except Exception as first_err:
        if not repair:
            raise
        raw2 = complete_fn(
            system,
            f"Fix this into valid JSON with key 'theme'. Error: {first_err}\n\nOUTPUT:\n{raw}",
        )
        return str(_extract_field(raw2, "theme")).strip()


def generate_music_prompt(
    *,
    theme: str,
    rules_path: Path,
    complete_fn: Callable[[str, str], str],
    repair: bool = True,
) -> str:
    rules = rules_path.read_text(encoding="utf-8")
    system = "You write ACE-Step music prompts for Lo-Fi themes. Output JSON only."
    user = _build_user_message(
        "Using the rules below, write a music prompt for the following Lo-Fi theme.",
        rules,
        context=f"THEME:\n{theme}",
    )
    raw = complete_fn(system, user)
    try:
        music = str(_extract_field(raw, "music_prompt")).strip()
    except Exception as first_err:
        if not repair:
            raise
        raw2 = complete_fn(
            system,
            f"Fix this into valid JSON with key 'music_prompt'. Error: {first_err}\n\nOUTPUT:\n{raw}",
        )
        music = str(_extract_field(raw2, "music_prompt")).strip()
    if "negative prompt" not in music.lower():
        raise ValueError("music_prompt must include a NEGATIVE PROMPT section")
    return music


def generate_metadata(
    *,
    theme: str,
    rules_path: Path,
    complete_fn: Callable[[str, str], str],
    repair: bool = True,
) -> dict[str, Any]:
    rules = rules_path.read_text(encoding="utf-8")
    system = "You write YouTube metadata for Lo-Fi themes. Output JSON only."
    user = _build_user_message(
        "Using the rules below, write title, description, and tags for the following Lo-Fi theme.",
        rules,
        context=f"THEME:\n{theme}",
    )
    raw = complete_fn(system, user)
    try:
        data = parse_prompt_payload(raw)
    except Exception as first_err:
        if not repair:
            raise
        raw2 = complete_fn(
            system,
            f"Fix this into valid JSON with keys title, description, tags. Error: {first_err}\n\nOUTPUT:\n{raw}",
        )
        data = parse_prompt_payload(raw2)
    for key in ("title", "description", "tags"):
        if key not in data:
            raise ValueError(f"Missing field: {key}")
    return {
        "title": str(data["title"]).strip(),
        "description": str(data["description"]).strip(),
        "tags": [str(t).strip() for t in data["tags"] if str(t).strip()],
    }


def generate_image_prompt(
    *,
    theme: str,
    rules_path: Path,
    complete_fn: Callable[[str, str], str],
    repair: bool = True,
) -> str:
    rules = rules_path.read_text(encoding="utf-8")
    system = "You write still cover prompts for Lo-Fi themes. Output JSON only."
    user = _build_user_message(
        "Using the rules below, write a cover image prompt for the following Lo-Fi theme.",
        rules,
        context=f"THEME:\n{theme}",
    )
    raw = complete_fn(system, user)
    try:
        return str(_extract_field(raw, "image_prompt")).strip()
    except Exception as first_err:
        if not repair:
            raise
        raw2 = complete_fn(
            system,
            f"Fix this into valid JSON with key 'image_prompt'. Error: {first_err}\n\nOUTPUT:\n{raw}",
        )
        return str(_extract_field(raw2, "image_prompt")).strip()


def generate_prompt_package(
    *,
    rules_dir: Path,
    complete_fn: Callable[[str, str], str],
    repair: bool = True,
) -> dict[str, Any]:
    """Generate a full Lo-Fi prompt package from specialized rules.

    Flow:
        1. Generate a theme.
        2. Generate music_prompt, metadata, and image_prompt sequentially from the theme.
        3. Validate and return the final prompt dict.
    """
    theme = generate_theme(
        rules_path=rules_dir / "theme_rules.md",
        complete_fn=complete_fn,
        repair=repair,
    )
    music_prompt = generate_music_prompt(
        theme=theme,
        rules_path=rules_dir / "music_rules.md",
        complete_fn=complete_fn,
        repair=repair,
    )
    metadata = generate_metadata(
        theme=theme,
        rules_path=rules_dir / "metadata_rules.md",
        complete_fn=complete_fn,
        repair=repair,
    )
    image_prompt = generate_image_prompt(
        theme=theme,
        rules_path=rules_dir / "image_rules.md",
        complete_fn=complete_fn,
        repair=repair,
    )
    slug = slugify(metadata["title"])
    data = {
        "slug": slug,
        "music_prompt": music_prompt,
        "image_prompt": image_prompt,
        **metadata,
    }
    return validate_prompt(data)


def generate_prompt_dict(
    *,
    rules_path: Path,
    complete_fn: Callable[[str, str], str],
    repair: bool = True,
) -> dict[str, Any]:
    """Legacy compatibility wrapper around generate_prompt_package.

    Uses the parent directory of ``rules_path`` as the rules directory.
    """
    return generate_prompt_package(
        rules_dir=rules_path.parent,
        complete_fn=complete_fn,
        repair=repair,
    )


def _qwen_complete(model_name: str) -> Callable[[str, str], str]:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )

    def complete(system: str, user: str) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        inputs = tokenizer([text], return_tensors="pt").to(model.device)
        ids = model.generate(**inputs, max_new_tokens=1200, temperature=0.9, do_sample=True)
        new_ids = ids[0][inputs.input_ids.shape[-1] :]
        return tokenizer.decode(new_ids, skip_special_tokens=True).strip()

    return complete


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Lo-Fi prompt JSON with local Qwen")
    parser.add_argument("--rules-dir", type=Path, default=DEFAULT_RULES_DIR)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--model",
        default=os.environ.get("PROMPT_LLM_MODEL", "Qwen/Qwen3-4B-Instruct-2507"),
    )
    args = parser.parse_args()
    rules_dir = args.rules_dir
    if args.rules != DEFAULT_RULES:
        # If --rules is overridden, use its parent directory.
        rules_dir = args.rules.parent
    data = generate_prompt_package(rules_dir=rules_dir, complete_fn=_qwen_complete(args.model))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
