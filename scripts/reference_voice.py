from __future__ import annotations

import argparse
import re
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

from common import path

# ACE-Step randomly samples three 10 s windows from the reference file.
# Always feed exactly 30 s of isolated vocal.
DEFAULT_MAX_SECONDS = 30.0
DEFAULT_SAMPLE_RATE = 44100
PREPARE_THRESHOLD_SECONDS = 32.0


def _wav_files(folder: Path) -> list[Path]:
    files = sorted(folder.glob("*.wav"))
    if not files:
        raise FileNotFoundError(f"No .wav files in {folder}")
    return files


def _filter_by_tag(files: list[Path], tag: str | None) -> list[Path]:
    if not tag:
        return files
    token = tag.lower().replace("-", "_")
    matched = [
        f
        for f in files
        if token in f.stem.lower().replace("-", "_") or token in str(f.parent.name).lower()
    ]
    return matched or files


def _load_stereo(file_path: Path, sample_rate: int) -> np.ndarray:
    audio, sr = sf.read(str(file_path), dtype="float32", always_2d=True)
    if audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    if sr != sample_rate:
        audio = librosa.resample(audio.T, orig_sr=sr, target_rate=sample_rate).T
        if audio.ndim == 1:
            audio = np.stack([audio, audio], axis=-1)
    return audio


def _maybe_prepare_reference(
    source: Path,
    cache_path: Path,
    *,
    isolate_vocals: bool = False,
) -> Path:
    from prepare_reference_vocal import prepare_reference_vocal

    audio = _load_stereo(source, DEFAULT_SAMPLE_RATE)
    duration = audio.shape[0] / DEFAULT_SAMPLE_RATE
    needs_prep = (
        isolate_vocals
        or duration > PREPARE_THRESHOLD_SECONDS
        or duration < DEFAULT_MAX_SECONDS - 1.0
    )
    if not needs_prep and abs(duration - DEFAULT_MAX_SECONDS) < 0.5:
        return source

    stamp = cache_path.with_suffix(".stamp")
    signature = f"{source}:{source.stat().st_mtime_ns}:isolate={isolate_vocals}"
    if cache_path.exists() and stamp.exists() and stamp.read_text(encoding="utf-8") == signature:
        print(f"Using prepared reference: {cache_path}")
        return cache_path

    prepare_reference_vocal(
        source,
        cache_path,
        isolate_vocals=isolate_vocals or duration > PREPARE_THRESHOLD_SECONDS,
        target_seconds=DEFAULT_MAX_SECONDS,
    )
    stamp.write_text(signature, encoding="utf-8")
    return cache_path


def build_combined_reference(
    source_files: list[Path],
    out: Path,
    *,
    max_seconds: float = DEFAULT_MAX_SECONDS,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    gap_seconds: float = 0.15,
) -> Path:
    """Concatenate several acapella clips into one ACE-Step reference track."""
    out.parent.mkdir(parents=True, exist_ok=True)
    gap = np.zeros((int(sample_rate * gap_seconds), 2), dtype=np.float32)
    chunks: list[np.ndarray] = []
    total = 0
    max_samples = int(max_seconds * sample_rate)

    for wav in source_files:
        audio = _load_stereo(wav, sample_rate)
        if total + audio.shape[0] > max_samples:
            audio = audio[: max_samples - total]
        chunks.append(audio)
        total += audio.shape[0]
        if total >= max_samples:
            break
        if total < max_samples:
            chunks.append(gap)

    if not chunks:
        raise RuntimeError("No audio collected for combined reference")

    combined = np.concatenate(chunks, axis=0)[:max_samples]
    combined = np.clip(combined, -1.0, 1.0)
    sf.write(str(out), combined, sample_rate, subtype="FLOAT")
    return out


def resolve_reference_audio(
    *,
    reference_audio: str | None = None,
    reference_dir: str | None = None,
    reference_tag: str | None = None,
    cache_path: str | Path = "output/reference_voice_combined.wav",
    max_seconds: float = DEFAULT_MAX_SECONDS,
    isolate_vocals: bool = False,
    prepared_cache: str | Path | None = None,
) -> Path | None:
    if reference_audio:
        ref = path(reference_audio)
        if not ref.exists():
            raise FileNotFoundError(f"Reference audio not found: {ref}")
        prep_out = path(prepared_cache or cache_path.parent / f"reference_prepared_{ref.stem}.wav")
        return _maybe_prepare_reference(ref, prep_out, isolate_vocals=isolate_vocals)

    if not reference_dir:
        return None

    folder = path(reference_dir)
    if not folder.is_dir():
        raise FileNotFoundError(f"Reference directory not found: {folder}")

    files = _filter_by_tag(_wav_files(folder), reference_tag)
    if len(files) == 1:
        prep_out = path(prepared_cache or cache_path.parent / f"reference_prepared_{files[0].stem}.wav")
        return _maybe_prepare_reference(files[0], prep_out, isolate_vocals=isolate_vocals)

    cache = path(cache_path)
    signature = "_".join(f"{f.name}:{f.stat().st_mtime_ns}" for f in files)
    stamp = path(cache.parent / f".{re.sub(r'[^a-zA-Z0-9._-]+', '_', signature[:120])}.stamp")
    if cache.exists() and stamp.exists() and stamp.read_text(encoding="utf-8") == signature:
        combined = cache
    else:
        print(f"Combining {len(files)} reference clips -> {cache}")
        build_combined_reference(files, cache, max_seconds=max_seconds)
        stamp.write_text(signature, encoding="utf-8")
        combined = cache

    prep_out = path(prepared_cache or cache.parent / "reference_prepared_combined.wav")
    return _maybe_prepare_reference(combined, prep_out, isolate_vocals=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build or resolve ACE-Step reference audio from one file or a folder of acapellas."
    )
    parser.add_argument("--reference-audio", default=None)
    parser.add_argument("--reference-dir", default="assets/references/sabrina")
    parser.add_argument("--reference-tag", default=None, help="Optional filename/tag filter, e.g. jazz or rap")
    parser.add_argument("--out", default="output/reference_voice_combined.wav")
    parser.add_argument("--max-seconds", type=float, default=DEFAULT_MAX_SECONDS)
    args = parser.parse_args()

    ref = resolve_reference_audio(
        reference_audio=args.reference_audio,
        reference_dir=args.reference_dir if not args.reference_audio else None,
        reference_tag=args.reference_tag,
        cache_path=args.out,
        max_seconds=args.max_seconds,
    )
    if ref is None:
        raise SystemExit("Provide --reference-audio or --reference-dir")
    print(ref)


if __name__ == "__main__":
    main()
