from __future__ import annotations

import argparse
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import torch
from demucs.apply import apply_model
from demucs.audio import convert_audio
from demucs.pretrained import get_model

from common import path

# ACE-Step samples 3 random 10 s chunks from the reference file.
# Keep exactly 30 s of strong vocal so every chunk is usable.
TARGET_SECONDS = 30.0
TARGET_SR = 44100


def _load_stereo(file_path: Path, sample_rate: int = TARGET_SR) -> np.ndarray:
    audio, sr = sf.read(str(file_path), dtype="float32", always_2d=True)
    if audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    if sr != sample_rate:
        audio = librosa.resample(audio.T, orig_sr=sr, target_rate=sample_rate).T
        if audio.ndim == 1:
            audio = np.stack([audio, audio], axis=-1)
    return audio


def _isolate_vocals(source: Path, work_dir: Path) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    model = get_model("htdemucs")
    model.cpu()
    model.eval()

    wav = torch.from_numpy(_load_stereo(source).T)
    wav = convert_audio(wav, TARGET_SR, model.samplerate, model.audio_channels)
    ref = wav.mean(0, keepdim=True)
    wav = (wav - ref.mean()) / ref.std().clamp(min=1e-8)

    with torch.no_grad():
        sources = apply_model(model, wav[None], device="cpu", progress=False)[0]

    vocals = sources[model.sources.index("vocals")].detach().cpu().numpy().T
    out = work_dir / f"{source.stem}_vocals.wav"
    sf.write(str(out), np.clip(vocals, -1.0, 1.0), model.samplerate, subtype="FLOAT")
    return out


def _best_window(audio: np.ndarray, sample_rate: int, window_seconds: float) -> np.ndarray:
    window = int(window_seconds * sample_rate)
    if audio.shape[0] <= window:
        return audio[:window]

    mono = audio.mean(axis=1)
    hop = max(1, sample_rate // 2)
    best_start = 0
    best_score = -1.0
    for start in range(0, audio.shape[0] - window, hop):
        chunk = mono[start : start + window]
        rms = float(np.sqrt(np.mean(chunk**2) + 1e-12))
        if rms > best_score:
            best_score = rms
            best_start = start
    return audio[best_start : best_start + window]


def prepare_reference_vocal(
    source: Path,
    out: Path,
    *,
    isolate_vocals: bool = False,
    target_seconds: float = TARGET_SECONDS,
) -> Path:
    """Trim/isolate reference to exactly 30 s of vocal for ACE-Step."""
    out.parent.mkdir(parents=True, exist_ok=True)
    work = out.parent / "_ref_prep"
    src = source

    probe = _load_stereo(source)
    duration = probe.shape[0] / TARGET_SR
    if isolate_vocals or duration > target_seconds * 1.25:
        print(f"Isolating vocals from reference ({duration:.1f}s): {source.name}")
        src = _isolate_vocals(source, work)

    audio = _load_stereo(src)
    clip = _best_window(audio, TARGET_SR, target_seconds)
    if clip.shape[0] < int(target_seconds * TARGET_SR):
        pad = np.zeros((int(target_seconds * TARGET_SR) - clip.shape[0], clip.shape[1]), dtype=clip.dtype)
        clip = np.concatenate([clip, pad], axis=0)

    sf.write(str(out), np.clip(clip, -1.0, 1.0), TARGET_SR, subtype="FLOAT")
    print(f"Prepared {target_seconds:.0f}s reference vocal -> {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--isolate-vocals", action="store_true")
    parser.add_argument("--seconds", type=float, default=TARGET_SECONDS)
    args = parser.parse_args()

    prepare_reference_vocal(
        path(args.source),
        path(args.out),
        isolate_vocals=args.isolate_vocals,
        target_seconds=args.seconds,
    )


if __name__ == "__main__":
    main()
