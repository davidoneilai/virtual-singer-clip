from __future__ import annotations

import argparse
from pathlib import Path

import soundfile as sf
import torch
from demucs.apply import apply_model
from demucs.audio import convert_audio
from demucs.pretrained import get_model

from common import copy, path


def load_wav(track: Path, sample_rate: int, channels: int) -> torch.Tensor:
    audio, sr = sf.read(str(track), dtype="float32", always_2d=True)
    wav = torch.from_numpy(audio.T)
    return convert_audio(wav, sr, sample_rate, channels)


def save_wav(wav: torch.Tensor, out_path: Path, sample_rate: int) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    audio = wav.detach().cpu().numpy()
    if audio.ndim == 2:
        audio = audio.T
    sf.write(str(out_path), audio, sample_rate, subtype="FLOAT")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--song", default="output/song.wav")
    parser.add_argument("--out-dir", default="output/stems")
    parser.add_argument("--vocals-out", default="output/vocals.wav")
    parser.add_argument("--instrumental-out", default="output/instrumental.wav")
    args = parser.parse_args()

    song = path(args.song)
    out_dir = path(args.out_dir)
    model_out = out_dir / "htdemucs" / song.stem
    model_out.mkdir(parents=True, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = get_model(name="htdemucs")
    model.to(device).eval()

    print(f"Separating track {song}")
    wav = load_wav(song, model.samplerate, model.audio_channels)

    ref = wav.mean(0)
    wav = (wav - ref.mean()) / ref.std()

    with torch.no_grad():
        sources = apply_model(
            model,
            wav[None],
            device=device,
            shifts=1,
            split=True,
            overlap=0.25,
            progress=True,
        )[0]

    sources = sources * ref.std() + ref.mean()

    vocals = sources[model.sources.index("vocals")]
    instrumental = sum(
        source for name, source in zip(model.sources, sources) if name != "vocals"
    )

    vocals_path = model_out / "vocals.wav"
    instrumental_path = model_out / "no_vocals.wav"
    save_wav(vocals, vocals_path, model.samplerate)
    save_wav(instrumental, instrumental_path, model.samplerate)

    copy(vocals_path, args.vocals_out)
    copy(instrumental_path, args.instrumental_out)
    print(f"Stems written to {model_out}")


if __name__ == "__main__":
    main()
