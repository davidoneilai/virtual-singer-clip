from __future__ import annotations

import argparse
import os

import common  # noqa: F401 — configure HF/torch cache before transformers loads
from common import write_text

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def configure_lyrics_hub_cache() -> None:
    """Prefer global /raid hub for lyrics model when configured."""
    lyrics_hub = os.environ.get("VSC_LYRICS_HUB_CACHE")
    if not lyrics_hub:
        return
    hub = str(common.path(lyrics_hub)) if not os.path.isabs(lyrics_hub) else lyrics_hub
    os.environ["HF_HUB_CACHE"] = hub
    os.environ["HUGGINGFACE_HUB_CACHE"] = hub


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen3-4B-Instruct-2507")
    parser.add_argument("--theme", default="uma cantora virtual descobrindo o Brasil pela noite")
    parser.add_argument("--language", default="pt", choices=["pt", "en"])
    parser.add_argument(
        "--genre",
        default="samba-pop",
        choices=["samba-pop", "modao-goiano", "pop-rap", "custom"],
        help="Lyrics style preset (ignored if --theme fully describes the song)",
    )
    parser.add_argument("--out", default="output/lyrics.txt")
    args = parser.parse_args()

    configure_lyrics_hub_cache()

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )

    if args.language == "en":
        prompt = f"""
Write original English lyrics for a 90s-style pop-rap song.
Theme: {args.theme}
Structure: [Verse 1], [Hook], [Verse 2], [Bridge], [Hook Out].
Keep it playful, rhythmic, and MTV-era. Do not name real artists. Return lyrics only.
""".strip()
        system = "You write original, rhythmic, singable rap-pop lyrics."
    elif args.genre == "modao-goiano":
        prompt = f"""
Crie uma letra original em portugues brasileiro para um modao goiano / sertanejo de raiz.
Tema: {args.theme}
Estrutura: [Verso 1], [Refrão], [Verso 2], [Ponte], [Refrão Final].
Use linguagem caipira autentica de Goias (sem exagero caricato), com imagens de cerrado, viola,
saudade, estrada de terra, boteco, luar e coracao sofrido. Deve soar cantavel em voz masculina
emocionada, com frases que pedem melisma e sustentacao. Evite citar artistas reais.
Retorne apenas a letra com tags de secao.
""".strip()
        system = (
            "Voce escreve modoes goianos originais, emotivos e cantaveis, "
            "no espirito do sertanejo de raiz."
        )
    else:
        prompt = f"""
Crie uma letra original em portugues brasileiro para uma musica de samba-pop.
Tema: {args.theme}
Estrutura: [Verso 1], [Pre-Refrão], [Refrão], [Verso 2], [Ponte], [Refrão Final].
Evite citar artistas reais. A letra deve ser cantavel, jovem e emocional.
Retorne apenas a letra.
""".strip()
        system = "Voce escreve letras originais e cantaveis."

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    inputs = tokenizer([text], return_tensors="pt").to(model.device)

    ids = model.generate(**inputs, max_new_tokens=900, temperature=0.9, do_sample=True)
    new_ids = ids[0][inputs.input_ids.shape[-1] :]
    lyrics = tokenizer.decode(new_ids, skip_special_tokens=True).strip()
    write_text(args.out, lyrics + "\n")
    print(args.out)


if __name__ == "__main__":
    main()
