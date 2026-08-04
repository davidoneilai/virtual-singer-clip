from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Callable

from lofi_batch.prompt_schema import parse_prompt_payload, validate_prompt

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES = Path(__file__).resolve().parent / "rules" / "lofi_rules.md"


def build_user_message(rules: str) -> str:
    return (
        "Using the rules below, invent ONE new Lo-Fi piece for today. "
        "Return ONLY a JSON object with keys: slug, music_prompt, image_prompt, "
        "title, description, tags.\n\nRULES:\n" + rules
    )


def generate_prompt_dict(
    *,
    rules_path: Path,
    complete_fn: Callable[[str, str], str],
    repair: bool = True,
) -> dict:
    rules = rules_path.read_text(encoding="utf-8")
    system = "You write Lo-Fi music and cover prompts. Output JSON only."
    raw = complete_fn(system, build_user_message(rules))
    try:
        return validate_prompt(parse_prompt_payload(raw))
    except Exception as first_err:
        if not repair:
            raise
        raw2 = complete_fn(
            system,
            "Fix this into valid JSON only with the required keys. Error: "
            f"{first_err}\n\nOUTPUT:\n{raw}",
        )
        return validate_prompt(parse_prompt_payload(raw2))


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
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--model",
        default=os.environ.get("PROMPT_LLM_MODEL", "Qwen/Qwen3-4B-Instruct-2507"),
    )
    args = parser.parse_args()
    data = generate_prompt_dict(rules_path=args.rules, complete_fn=_qwen_complete(args.model))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
