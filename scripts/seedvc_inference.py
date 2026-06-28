"""Run Seed-VC inference without torchcodec (uses soundfile for wav output)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import common  # noqa: E402,F401 — configure HF/torch cache on /raid

sys.path.insert(0, str(ROOT / "external" / "seed-vc"))
SEEDVC = ROOT / "external" / "seed-vc"
os.chdir(SEEDVC)
os.environ["HF_HUB_CACHE"] = str(ROOT / "external" / "seed-vc" / "checkpoints" / "hf_cache")

import soundfile as sf
import torch

import torchaudio


def _save_wav(uri, src, sample_rate, **kwargs) -> None:
    audio = src.detach().cpu().numpy()
    if audio.ndim == 2:
        audio = audio.T
    out = Path(uri)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), audio, sample_rate, subtype="FLOAT")


torchaudio.save = _save_wav

import argparse
from inference import main
from modules.commons import str2bool

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=str, required=True)
    parser.add_argument("--target", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--diffusion-steps", type=int, default=30)
    parser.add_argument("--length-adjust", type=float, default=1.0)
    parser.add_argument("--inference-cfg-rate", type=float, default=0.7)
    parser.add_argument("--f0-condition", type=str2bool, default=False)
    parser.add_argument("--auto-f0-adjust", type=str2bool, default=False)
    parser.add_argument("--semi-tone-shift", type=int, default=0)
    parser.add_argument("--checkpoint", type=str, default=None)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--fp16", type=str2bool, default=True)
    main(parser.parse_args())
