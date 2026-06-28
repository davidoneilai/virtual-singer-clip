from __future__ import annotations

import argparse

import librosa
import numpy as np
import soundfile as sf

from common import path


def load_stereo(file_path: str, target_sr: int = 44100) -> np.ndarray:
    audio, sr = sf.read(str(path(file_path)), dtype="float32", always_2d=True)
    if audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    elif audio.shape[1] > 2:
        audio = audio[:, :2]

    if sr != target_sr:
        audio = librosa.resample(audio.T, orig_sr=sr, target_sr=target_sr).T
        if audio.ndim == 1:
            audio = np.stack([audio, audio], axis=-1)

    return audio


def pad_to_length(audio: np.ndarray, length: int) -> np.ndarray:
    if audio.shape[0] >= length:
        return audio
    pad = np.zeros((length - audio.shape[0], audio.shape[1]), dtype=audio.dtype)
    return np.concatenate([audio, pad], axis=0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vocal", default="output/converted_vocal.wav")
    parser.add_argument("--instrumental", default="output/instrumental.wav")
    parser.add_argument("--out", default="output/final_audio.wav")
    parser.add_argument("--vocal-volume", type=float, default=1.2)
    parser.add_argument("--instrumental-volume", type=float, default=0.85)
    parser.add_argument("--sample-rate", type=int, default=44100)
    args = parser.parse_args()

    out = path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    instrumental = load_stereo(args.instrumental, args.sample_rate) * args.instrumental_volume
    vocal = load_stereo(args.vocal, args.sample_rate) * args.vocal_volume

    length = max(instrumental.shape[0], vocal.shape[0])
    mixed = pad_to_length(instrumental, length) + pad_to_length(vocal, length)
    mixed = np.clip(mixed, -1.0, 1.0)

    sf.write(str(out), mixed, args.sample_rate, subtype="FLOAT")
    print(out)


if __name__ == "__main__":
    main()
