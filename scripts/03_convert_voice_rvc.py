from __future__ import annotations

import argparse
import os

from common import path, reexec_with_rvc_python, rvc_python, rvc_subprocess_env, run


def resolve_model(voice_name: str) -> tuple[str, str]:
    """Return (model_name for RVC assets/weights, index_path)."""
    voice_dir = path("assets/voices") / voice_name
    model_link = voice_dir / "model.pth"
    index_path = voice_dir / "model.index"

    rvc = path(os.environ.get("VSC_RVC_ROOT", "rvc/RVC"))
    weights = rvc / "assets" / "weights" / f"{voice_name}.pth"

    if not model_link.exists() and not weights.exists():
        raise FileNotFoundError(
            f"No RVC model for '{voice_name}'. Train with scripts/rvc_train.py first."
        )

    target = rvc / "assets" / "weights" / f"{voice_name}.pth"
    target.parent.mkdir(parents=True, exist_ok=True)
    if model_link.exists() and (
        not target.exists() or target.stat().st_mtime < model_link.stat().st_mtime
    ):
        import shutil

        shutil.copy2(model_link, target)

    if not index_path.exists():
        logs = rvc / "logs" / voice_name
        candidates = sorted(logs.glob("added_*.index"), key=os.path.getmtime)
        if candidates:
            index_path = candidates[-1]
        else:
            raise FileNotFoundError(f"No RVC index for '{voice_name}' at {index_path}")

    # RVC get_vc loads: {weight_root}/{model_name} — name must include .pth
    return f"{voice_name}.pth", str(index_path)


def main() -> None:
    reexec_with_rvc_python()
    parser = argparse.ArgumentParser(description="Convert vocals with a trained RVC model.")
    parser.add_argument("--source", default="output/vocals.wav")
    parser.add_argument("--out", default="output/converted_vocal.wav")
    parser.add_argument("--voice", default="anderson", help="Voice name under assets/voices/")
    parser.add_argument("--f0-method", default="rmvpe", choices=("rmvpe", "harvest", "pm"))
    parser.add_argument("--index-rate", type=float, default=0.75)
    parser.add_argument("--f0-up-key", type=int, default=0)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()

    rvc = path(os.environ.get("VSC_RVC_ROOT", "rvc/RVC"))
    model_name, index_path = resolve_model(args.voice)

    out = path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    run(
        [
            str(rvc_python()),
            "tools/infer_cli.py",
            "--f0up_key",
            str(args.f0_up_key),
            "--input_path",
            str(path(args.source)),
            "--index_path",
            index_path,
            "--f0method",
            args.f0_method,
            "--opt_path",
            str(out),
            "--model_name",
            model_name,
            "--index_rate",
            str(args.index_rate),
            "--device",
            args.device,
            "--is_half",
            "True",
            "--filter_radius",
            "3",
            "--resample_sr",
            "0",
            "--rms_mix_rate",
            "0.25",
            "--protect",
            "0.33",
        ],
        cwd=rvc,
        env=rvc_subprocess_env(),
    )
    print(f"RVC output: {out}")


if __name__ == "__main__":
    main()
