from __future__ import annotations

import argparse
import shutil

import numpy as np
import soundfile as sf
import torch
from demucs.apply import apply_model
from demucs.audio import convert_audio
from demucs.pretrained import get_model

from pathlib import Path

from common import path


def _load_mono(source: Path, sample_rate: int = 48000) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(str(source), dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    if sr != sample_rate:
        import librosa

        mono = librosa.resample(mono, orig_sr=sr, target_rate=sample_rate)
        sr = sample_rate
    return mono, sr


def _isolate_vocals(source: Path, out: Path, device: str) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    model = get_model("htdemucs")
    model.to(device)
    model.eval()

    wav = torch.from_numpy(_load_mono(source, 44100)[0]).unsqueeze(0).repeat(2, 1)
    wav = convert_audio(wav, 44100, model.samplerate, model.audio_channels)
    ref = wav.mean(0, keepdim=True)
    wav = (wav - ref.mean()) / ref.std().clamp(min=1e-8)

    with torch.no_grad():
        sources = apply_model(model, wav[None], device=device, progress=True)[0]

    vocals = sources[model.sources.index("vocals")].detach().cpu().numpy().T
    sf.write(str(out), np.clip(vocals, -1.0, 1.0), model.samplerate, subtype="FLOAT")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare vocal dataset for RVC training.")
    parser.add_argument("--source", required=True, help="Raw reference audio (wav).")
    parser.add_argument("--out-dir", required=True, help="RVC dataset folder (wav files).")
    parser.add_argument(
        "--isolate-vocals",
        action="store_true",
        help="Run Demucs vocal isolation before training.",
    )
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()

    source = path(args.source)
    out_dir = path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    work = out_dir.parent / "_prep"
    work.mkdir(parents=True, exist_ok=True)

    if args.isolate_vocals:
        vocal_path = work / f"{source.stem}_vocals.wav"
        if not vocal_path.exists():
            print(f"Isolating vocals from {source} ...")
            _isolate_vocals(source, vocal_path, args.device)
        prepared = vocal_path
    else:
        prepared = source

    target = out_dir / f"{source.stem}.wav"
    shutil.copy2(prepared, target)
    print(f"RVC dataset ready: {target}")


if __name__ == "__main__":
    main()
