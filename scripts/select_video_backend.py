from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass

from common import backend_python, backend_repo, path


@dataclass
class BackendPlan:
    clip_mode: str
    lipsync_backend: str | None
    avatar_backend: str | None
    fallback_clip_mode: str
    notes: list[str]


def _python_ok(name: str, snippet: str) -> bool:
    try:
        py = backend_python(name)
    except FileNotFoundError:
        return False
    proc = subprocess.run(
        [str(py), "-c", snippet],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def latentsync_ready() -> bool:
    repo = backend_repo("latentsync")
    ckpt = repo / "checkpoints" / "latentsync_unet.pt"
    return ckpt.exists() and _python_ok("latentsync", "import cv2; import diffusers")


def musetalk_ready() -> bool:
    repo = backend_repo("musetalk")
    unet = repo / "models" / "musetalkV15" / "unet.pth"
    if not unet.exists():
        return False
    try:
        py = backend_python("musetalk")
    except FileNotFoundError:
        return False
    proc = subprocess.run(
        [str(py), "-c", "import cv2"],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def echomimic_ready(version: str) -> bool:
    repo = backend_repo(f"echomimic_{version.split('_')[-1]}")
    if version == "echomimic_v2":
        weights = repo / "pretrained_weights" / "denoising_unet.pth"
        script = repo / "infer.py"
    else:
        weights = repo / "flash" / "transformer" / "diffusion_pytorch_model.safetensors"
        if not weights.exists():
            weights = repo / "preview" / "transformer" / "diffusion_pytorch_model.safetensors"
        script = repo / "infer_flash.py"
        if not script.exists():
            script = repo / "infer_preview.py"
    if not repo.exists() or not script.exists():
        return False
    if not weights.exists():
        return False
    return _python_ok("echomimic", "import diffusers, torch; assert torch.cuda.is_available()")


def hallo3_ready() -> bool:
    repo = backend_repo("hallo3")
    models = repo / "pretrained_models"
    script = repo / "scripts" / "inference_long_batch.sh"
    return models.exists() and script.exists() and _python_ok("hallo3", "import torch")


def resolve_lipsync(preferred: str) -> tuple[str | None, list[str]]:
    order = []
    if preferred == "latentsync":
        order = ["latentsync", "musetalk"]
    elif preferred == "musetalk":
        order = ["musetalk", "latentsync"]
    else:
        order = ["latentsync", "musetalk"]

    notes: list[str] = []
    checks = {
        "latentsync": latentsync_ready,
        "musetalk": musetalk_ready,
    }
    for name in order:
        if checks[name]():
            if name != preferred:
                notes.append(f"Lipsync fallback: {preferred} unavailable, using {name}.")
            return name, notes
    notes.append("No lipsync backend available; will use wan-only assembly.")
    return None, notes


def resolve_avatar(preferred: str, cinematic: bool = False) -> tuple[str | None, list[str]]:
    if cinematic:
        order = ["hallo3", "echomimic_v3", "echomimic_v2"]
    elif preferred == "echomimic_v3":
        order = ["echomimic_v3", "echomimic_v2", "hallo3"]
    elif preferred == "hallo3":
        order = ["hallo3", "echomimic_v3", "echomimic_v2"]
    else:
        order = ["echomimic_v2", "echomimic_v3", "hallo3"]

    notes: list[str] = []
    checks = {
        "echomimic_v2": lambda: echomimic_ready("echomimic_v2"),
        "echomimic_v3": lambda: echomimic_ready("echomimic_v3"),
        "hallo3": hallo3_ready,
    }
    for name in order:
        if name.startswith("echomimic"):
            if checks[name]():
                if name != preferred:
                    notes.append(f"Avatar fallback: {preferred} unavailable, using {name}.")
                return name, notes
        elif checks[name]():
            if name != preferred:
                notes.append(f"Avatar fallback: {preferred} unavailable, using {name}.")
            return name, notes

    notes.append("No avatar backend available; will use wan-only assembly.")
    return None, notes


def build_plan() -> BackendPlan:
    clip_mode = os.environ.get("VSC_CLIP_MODE", "hybrid")
    lipsync_pref = os.environ.get("VSC_LIPSYNC_BACKEND", "latentsync")
    avatar_pref = os.environ.get("VSC_AVATAR_BACKEND", "echomimic_v2")
    notes: list[str] = []

    lipsync_backend = None
    avatar_backend = None
    fallback = "wan"

    if clip_mode == "hybrid":
        lipsync_backend, lipsync_notes = resolve_lipsync(lipsync_pref)
        notes.extend(lipsync_notes)
        if lipsync_backend is None:
            fallback = "wan"
    elif clip_mode == "avatar":
        avatar_backend, avatar_notes = resolve_avatar(avatar_pref, cinematic=False)
        notes.extend(avatar_notes)
        if avatar_backend is None:
            fallback = "wan"
    elif clip_mode == "cinematic_avatar":
        avatar_backend, avatar_notes = resolve_avatar(avatar_pref, cinematic=True)
        notes.extend(avatar_notes)
        if avatar_backend is None:
            fallback = "wan"

    return BackendPlan(
        clip_mode=clip_mode,
        lipsync_backend=lipsync_backend,
        avatar_backend=avatar_backend,
        fallback_clip_mode=fallback,
        notes=notes,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve video backend plan from env vars.")
    parser.add_argument("--json", action="store_true", help="Print JSON plan")
    parser.add_argument("--check", choices=["latentsync", "musetalk", "echomimic_v2", "echomimic_v3", "hallo3"])
    args = parser.parse_args()

    if args.check:
        ok = {
            "latentsync": latentsync_ready,
            "musetalk": musetalk_ready,
            "echomimic_v2": lambda: echomimic_ready("echomimic_v2"),
            "echomimic_v3": lambda: echomimic_ready("echomimic_v3"),
            "hallo3": hallo3_ready,
        }[args.check]()
        print("ok" if ok else "missing")
        sys.exit(0 if ok else 1)

    plan = build_plan()
    if args.json:
        print(json.dumps(asdict(plan), indent=2))
        return

    print(f"clip_mode={plan.clip_mode}")
    if plan.lipsync_backend:
        print(f"lipsync_backend={plan.lipsync_backend}")
    if plan.avatar_backend:
        print(f"avatar_backend={plan.avatar_backend}")
    print(f"fallback_clip_mode={plan.fallback_clip_mode}")
    for note in plan.notes:
        print(f"note: {note}")


if __name__ == "__main__":
    main()
