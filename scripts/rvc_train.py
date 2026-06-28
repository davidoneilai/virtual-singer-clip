from __future__ import annotations

import argparse
import json
import os
import platform
import random
import subprocess
import sys
from pathlib import Path

from common import path, reexec_with_rvc_python, rvc_python, rvc_subprocess_env, run


def _rvc_root() -> Path:
    return path(os.environ.get("VSC_RVC_ROOT", "rvc/RVC"))


def _exp_dir(rvc: Path, name: str) -> Path:
    return rvc / "logs" / name


def _write_filelist(
    exp: Path,
    *,
    version: str,
    sample_rate: str,
    with_f0: bool,
    rvc: Path,
) -> None:
    gt_wavs = exp / "0_gt_wavs"
    feature_dir = exp / ("3_feature256" if version == "v1" else "3_feature768")
    names = {p.stem for p in gt_wavs.glob("*.wav")} & {p.stem for p in feature_dir.glob("*.npy")}
    if with_f0:
        f0_dir = exp / "2a_f0"
        f0nsf_dir = exp / "2b-f0nsf"
        names &= {p.stem for p in f0_dir.glob("*.npy")}
        names &= {p.stem.split(".")[0] for p in f0nsf_dir.glob("*.npy")}

    lines: list[str] = []
    for name in sorted(names):
        if with_f0:
            lines.append(
                f"{gt_wavs}/{name}.wav|{feature_dir}/{name}.npy|"
                f"{f0_dir}/{name}.wav.npy|{f0nsf_dir}/{name}.wav.npy|0"
            )
        else:
            lines.append(f"{gt_wavs}/{name}.wav|{feature_dir}/{name}.npy|0")

    fea_dim = 256 if version == "v1" else 768
    mute = rvc / "logs" / "mute"
    for _ in range(2):
        if with_f0:
            lines.append(
                f"{mute}/0_gt_wavs/mute{sample_rate}.wav|"
                f"{mute}/3_feature{fea_dim}/mute.npy|"
                f"{mute}/2a_f0/mute.wav.npy|"
                f"{mute}/2b-f0nsf/mute.wav.npy|0"
            )
        else:
            lines.append(f"{mute}/0_gt_wavs/mute{sample_rate}.wav|{mute}/3_feature{fea_dim}/mute.npy|0")

    random.shuffle(lines)
    (exp / "filelist.txt").write_text("\n".join(lines), encoding="utf-8")


def _ensure_config(exp: Path, rvc: Path, sample_rate: str, version: str) -> None:
    config_key = f"v1/{sample_rate}.json" if version == "v1" or sample_rate == "40k" else f"v2/{sample_rate}.json"
    src = rvc / "configs" / config_key
    inuse = rvc / "configs" / "inuse" / config_key
    inuse.parent.mkdir(parents=True, exist_ok=True)
    if not inuse.exists():
        inuse.write_bytes(src.read_bytes())
    with open(inuse, encoding="utf-8") as f:
        cfg = json.load(f)
    (exp / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


def _build_index(exp: Path, exp_name: str, version: str) -> Path:
    import faiss
    import numpy as np
    from sklearn.cluster import MiniBatchKMeans

    feature_dir = exp / ("3_feature256" if version == "v1" else "3_feature768")
    npys = [np.load(feature_dir / name) for name in sorted(os.listdir(feature_dir))]
    big_npy = np.concatenate(npys, 0)
    idx = np.arange(big_npy.shape[0])
    np.random.shuffle(idx)
    big_npy = big_npy[idx]

    if big_npy.shape[0] > 200_000:
        print(f"kmeans reducing {big_npy.shape[0]} -> 10000 centers")
        big_npy = (
            MiniBatchKMeans(
                n_clusters=10_000,
                verbose=True,
                batch_size=256 * max(1, os.cpu_count() or 1),
                compute_labels=False,
                init="random",
            )
            .fit(big_npy)
            .cluster_centers_
        )

    np.save(exp / "total_fea.npy", big_npy)
    dim = 256 if version == "v1" else 768
    n_ivf = min(int(16 * np.sqrt(big_npy.shape[0])), big_npy.shape[0] // 39)
    index = faiss.index_factory(dim, f"IVF{n_ivf},Flat")
    index_ivf = faiss.extract_index_ivf(index)
    index_ivf.nprobe = 1
    index.train(big_npy)
    for start in range(0, big_npy.shape[0], 8192):
        index.add(big_npy[start : start + 8192])

    out = exp / f"added_IVF{n_ivf}_Flat_nprobe_{index_ivf.nprobe}_{exp_name}_{version}.index"
    faiss.write_index(index, str(out))
    print(f"Index saved: {out}")
    return out


def _rvc_run(cmd: list[str], cwd: Path | None = None) -> None:
    run(cmd, cwd=cwd, env=rvc_subprocess_env())


def train(
    *,
    dataset_dir: Path,
    exp_name: str,
    sample_rate: str = "48k",
    version: str = "v2",
    epochs: int = 200,
    batch_size: int = 12,
    save_every: int = 50,
    gpu: str = "0",
    n_cpu: int | None = None,
    train_only: bool = False,
) -> Path:
    rvc = _rvc_root()
    if not (rvc / "infer-web.py").exists():
        raise FileNotFoundError(f"RVC checkout missing: {rvc}")

    sr_hz = {"32k": 32000, "40k": 40000, "48k": 48000}[sample_rate]
    n_cpu = n_cpu or max(1, (os.cpu_count() or 8) // 2)
    exp = _exp_dir(rvc, exp_name)
    exp.mkdir(parents=True, exist_ok=True)

    py = str(rvc_python())
    pg = rvc / "assets" / "pretrained_v2" / f"f0G{sample_rate}.pth"
    pd = rvc / "assets" / "pretrained_v2" / f"f0D{sample_rate}.pth"
    if not pg.exists():
        raise FileNotFoundError(f"Missing pretrained G: {pg} — run scripts/setup_rvc.sh")

    if not train_only:
        print("=== RVC preprocess ===")
        _rvc_run(
            [
                py,
                "infer/modules/train/preprocess.py",
                str(dataset_dir),
                str(sr_hz),
                str(n_cpu),
                str(exp),
                "False",
                "3.7",
            ],
            cwd=rvc,
        )

        print("=== RVC f0 (rmvpe gpu) ===")
        _rvc_run(
            [py, "infer/modules/train/extract/extract_f0_rmvpe.py", "1", "0", gpu, str(exp), "True"],
            cwd=rvc,
        )

        print("=== RVC feature extract ===")
        _rvc_run(
            [
                py,
                "infer/modules/train/extract_feature_print.py",
                "cuda:0",
                "1",
                "0",
                gpu,
                str(exp),
                version,
                "True",
            ],
            cwd=rvc,
        )
    else:
        print("=== Skipping preprocess / f0 / features (--train-only) ===")

    _write_filelist(exp, version=version, sample_rate=sample_rate, with_f0=True, rvc=rvc)
    _ensure_config(exp, rvc, sample_rate, version)

    print("=== RVC train ===")
    _rvc_run(
        [
            py,
            "infer/modules/train/train.py",
            "-e",
            exp_name,
            "-sr",
            sample_rate,
            "-f0",
            "1",
            "-bs",
            str(batch_size),
            "-g",
            gpu,
            "-te",
            str(epochs),
            "-se",
            str(save_every),
            "-pg",
            str(pg),
            "-pd",
            str(pd),
            "-l",
            "1",
            "-c",
            "0",
            "-sw",
            "1",
            "-v",
            version,
        ],
        cwd=rvc,
    )

    print("=== RVC index ===")
    index_path = _build_index(exp, exp_name, version)

    weights = rvc / "assets" / "weights" / f"{exp_name}.pth"
    if not weights.exists():
        g_ckpts = sorted(exp.glob("G_*.pth"), key=os.path.getmtime)
        if not g_ckpts:
            raise FileNotFoundError(f"No G_*.pth in {exp}")
        weights.parent.mkdir(parents=True, exist_ok=True)
        shutil_copy = subprocess.run(
            ["cp", str(g_ckpts[-1]), str(weights)],
            check=True,
        )
        del shutil_copy

    voice_dir = path("assets/voices") / exp_name
    voice_dir.mkdir(parents=True, exist_ok=True)
    for src, dst in (
        (weights, voice_dir / "model.pth"),
        (index_path, voice_dir / "model.index"),
    ):
        if src.exists():
            subprocess.run(["cp", str(src), str(dst)], check=True)

    print(f"Model: {weights}")
    print(f"Index: {index_path}")
    return weights


def main() -> None:
    reexec_with_rvc_python()
    py = rvc_python()
    try:
        subprocess.run(
            [str(py), "-c", "import scipy, fairseq, torch"],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        raise RuntimeError(
            f"RVC env at {py} is missing scipy/fairseq/torch.\n"
            "Run: bash scripts/setup_rvc.sh\n"
            f"Or:  {py} -m pip install -r requirements-rvc-py310.txt"
        ) from None

    parser = argparse.ArgumentParser(description="Train an RVC voice model (headless).")
    parser.add_argument("--dataset-dir", required=True)
    parser.add_argument("--exp-name", required=True)
    parser.add_argument("--sample-rate", default="48k", choices=("32k", "40k", "48k"))
    parser.add_argument("--version", default="v2", choices=("v1", "v2"))
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--save-every", type=int, default=50)
    parser.add_argument("--gpu", default="0")
    parser.add_argument(
        "--train-only",
        action="store_true",
        help="Skip preprocess/f0/features (resume after a failed train step).",
    )
    args = parser.parse_args()

    train(
        dataset_dir=path(args.dataset_dir),
        exp_name=args.exp_name,
        sample_rate=args.sample_rate,
        version=args.version,
        epochs=args.epochs,
        batch_size=args.batch_size,
        save_every=args.save_every,
        gpu=args.gpu,
        train_only=args.train_only,
    )


if __name__ == "__main__":
    main()
