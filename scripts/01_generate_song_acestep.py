from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from common import path, read_text
from reference_voice import resolve_reference_audio


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ace-repo", default="external/ACE-Step-1.5")
    parser.add_argument("--lyrics", default="output/lyrics.txt")
    parser.add_argument("--out", default="output/song.wav")
    parser.add_argument("--duration", type=int, default=180)
    parser.add_argument(
        "--prompt",
        default=(
            "Brazilian samba-pop, female virtual singer, cavaquinho, pandeiro, surdo, "
            "warm bass, pop-rock chorus energy, emotional but danceable, studio quality"
        ),
    )
    parser.add_argument("--config-path", default="acestep-v15-turbo")
    parser.add_argument("--lm-model", default="acestep-5Hz-lm-1.7B")
    parser.add_argument(
        "--backend",
        default="pt",
        choices=["pt", "vllm", "mlx"],
        help="LM backend. Use 'pt' if vllm/flash-attn are unavailable.",
    )
    parser.add_argument("--vocal-language", default="pt")
    parser.add_argument("--reference-audio", default=None, help="Single reference wav")
    parser.add_argument(
        "--reference-dir",
        default=None,
        help="Folder of acapella clips; combined automatically if several files",
    )
    parser.add_argument(
        "--reference-tag",
        default=None,
        help="Optional filter when using --reference-dir (e.g. jazz, rap, espresso)",
    )
    parser.add_argument(
        "--audio-cover-strength",
        type=float,
        default=0.72,
        help="Reference vocal influence (0.55 subtle, 0.72 balanced, 0.85 strong timbre)",
    )
    parser.add_argument(
        "--isolate-reference-vocals",
        action="store_true",
        help="Force Demucs vocal isolation on reference before generation",
    )
    args = parser.parse_args()

    repo = path(args.ace_repo).resolve()
    if not repo.is_dir():
        raise FileNotFoundError(f"ACE-Step repo not found: {repo}")

    out = path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # ACE-Step resolves checkpoints relative to project root / cwd.
    import os

    os.environ.setdefault("ACESTEP_PROJECT_ROOT", str(repo))

    sys.path.insert(0, str(repo))

    from acestep.gpu_config import (
        VRAM_AUTO_OFFLOAD_THRESHOLD_GB,
        find_best_lm_model_on_disk,
        get_gpu_config,
        set_global_gpu_config,
    )
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music
    from acestep.llm_inference import LLMHandler
    from acestep.model_downloader import ensure_lm_model

    gpu_config = get_gpu_config()
    set_global_gpu_config(gpu_config)
    auto_offload = (
        gpu_config.gpu_memory_gb > 0
        and gpu_config.gpu_memory_gb < VRAM_AUTO_OFFLOAD_THRESHOLD_GB
    )

    checkpoint_dir = repo / "checkpoints"
    save_dir = out.parent / "acestep_tmp"
    save_dir.mkdir(parents=True, exist_ok=True)

    dit_handler = AceStepHandler()
    status, ok = dit_handler.initialize_service(
        project_root=str(repo),
        config_path=args.config_path,
        device="auto",
        offload_to_cpu=auto_offload,
    )
    if not ok:
        raise RuntimeError(f"ACE-Step DiT init failed: {status}")

    llm_handler = LLMHandler()
    lm_model = args.lm_model
    lm_path = checkpoint_dir / lm_model
    if not lm_path.exists():
        ok, msg = ensure_lm_model(lm_model, checkpoints_dir=checkpoint_dir)
        if not lm_path.exists():
            available = llm_handler.get_available_5hz_lm_models()
            if available:
                lm_model = find_best_lm_model_on_disk(lm_model, available) or available[0]
                print(f"LM '{args.lm_model}' missing; using on-disk model: {lm_model}")
            else:
                raise RuntimeError(f"ACE-Step LM not found: {msg}")

    status, ok = llm_handler.initialize(
        checkpoint_dir=str(checkpoint_dir),
        lm_model_path=lm_model,
        backend=args.backend,
        device="auto",
        offload_to_cpu=auto_offload,
    )
    if not ok:
        raise RuntimeError(f"ACE-Step LM init failed: {status}")

    reference = resolve_reference_audio(
        reference_audio=args.reference_audio,
        reference_dir=args.reference_dir,
        reference_tag=args.reference_tag,
        cache_path=out.parent / "reference_voice_combined.wav",
        isolate_vocals=args.isolate_reference_vocals,
        prepared_cache=out.parent / "reference_prepared.wav",
    )
    if reference:
        print(f"ACE-Step reference vocal: {reference}")

    params = GenerationParams(
        task_type="text2music",
        thinking=True,
        caption=args.prompt,
        lyrics=read_text(args.lyrics),
        vocal_language=args.vocal_language,
        duration=args.duration,
        inference_steps=8,
        guidance_scale=1.0,
        seed=-1,
        reference_audio=str(reference) if reference else None,
        audio_cover_strength=args.audio_cover_strength,
    )
    config = GenerationConfig(batch_size=1, audio_format="wav")

    result = generate_music(
        dit_handler,
        llm_handler,
        params=params,
        config=config,
        save_dir=str(save_dir),
    )
    if not result.success:
        raise RuntimeError(f"ACE-Step generation failed: {result.status_message}")

    generated = next((audio["path"] for audio in result.audios if audio.get("path")), None)
    if not generated or not Path(generated).exists():
        raise RuntimeError("ACE-Step did not write an output audio file")

    shutil.copy2(generated, out)
    print(out)


if __name__ == "__main__":
    main()
