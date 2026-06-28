from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
CACHE_ROOT = Path(os.environ.get("VSC_CACHE_DIR", ROOT / ".cache")).resolve()


def configure_cache() -> Path:
    """Send HF/torch caches to the project dir (on /raid), not /root/.cache."""
    hf_home = CACHE_ROOT / "huggingface"
    hf_hub = hf_home / "hub"
    for directory in (
        CACHE_ROOT,
        hf_home,
        hf_hub,
        hf_home / "transformers",
        CACHE_ROOT / "torch",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    os.environ["VSC_CACHE_DIR"] = str(CACHE_ROOT)
    os.environ["XDG_CACHE_HOME"] = str(CACHE_ROOT)
    os.environ["HF_HOME"] = str(hf_home)
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(hf_hub)
    os.environ["HF_HUB_CACHE"] = str(hf_hub)
    os.environ["TRANSFORMERS_CACHE"] = str(hf_home / "transformers")
    os.environ["TORCH_HOME"] = str(CACHE_ROOT / "torch")
    return hf_hub


configure_cache()


def hf_hub_cache() -> Path:
    return Path(os.environ["HUGGINGFACE_HUB_CACHE"])


def path(value: str | Path) -> Path:
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


def read_text(file_path: str | Path) -> str:
    return path(file_path).read_text(encoding="utf-8")


def write_text(file_path: str | Path, text: str) -> None:
    p = path(file_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def run(cmd: list[str], cwd: str | Path | None = None, env: dict[str, str] | None = None) -> None:
    print(" ".join(cmd))
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def rvc_subprocess_env() -> dict[str, str]:
    """Ensure RVC conda bin (ffmpeg) and .env paths work for subprocesses."""
    env = os.environ.copy()
    bin_dir = str(rvc_python().resolve().parent)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    rvc_root = path(os.environ.get("VSC_RVC_ROOT", "rvc/RVC"))
    env.setdefault("weight_root", str(rvc_root / "assets" / "weights"))
    env.setdefault("index_root", str(rvc_root / "logs"))
    env.setdefault("rmvpe_root", str(rvc_root / "assets" / "rmvpe"))
    return env


def newest_file(folder: str | Path, pattern: str) -> Path:
    files = sorted(path(folder).glob(pattern), key=os.path.getmtime)
    if not files:
        raise FileNotFoundError(f"No file matched {pattern} in {folder}")
    return files[-1]


def copy(src: str | Path, dst: str | Path) -> None:
    dst_path = path(dst)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path(src), dst_path)


def rvc_python() -> Path:
    """Python 3.10 conda env for RVC (fairseq incompatible with 3.11)."""
    explicit = os.environ.get("RVC_PYTHON")
    if explicit:
        return Path(explicit)
    env_py = path("rvc/conda-env/bin/python")
    if env_py.exists():
        return env_py
    raise FileNotFoundError(
        "RVC Python env not found. Run: bash scripts/setup_rvc.sh"
    )


def reexec_with_rvc_python() -> None:
    """Re-launch current script under the RVC conda env if needed."""
    import sys

    target = rvc_python().resolve()
    if Path(sys.executable).resolve() == target:
        return
    os.execv(str(target), [str(target), *sys.argv])


BACKEND_ENVS: dict[str, str] = {
    "latentsync": "latentsync/conda-env",
    "musetalk": "musetalk/conda-env",
    "echomimic": "echomimic/conda-env",
    "hallo3": "hallo3/conda-env",
}


def backend_python(name: str) -> Path:
    """Isolated Python for optional video backends."""
    env_key = f"{name.upper()}_PYTHON"
    explicit = os.environ.get(env_key)
    if explicit:
        return Path(explicit)
    env_dir = os.environ.get(
        f"VSC_{name.upper()}_CONDA_ENV",
        str(path(BACKEND_ENVS[name])),
    )
    env_py = Path(env_dir) / "bin" / "python"
    if env_py.exists():
        return env_py
    raise FileNotFoundError(
        f"{name} Python env not found at {env_py}. "
        f"Run: bash scripts/setup_{name}.sh"
    )


def backend_repo(name: str) -> Path:
    repos = {
        "latentsync": "external/LatentSync",
        "musetalk": "external/MuseTalk",
        "echomimic_v2": "external/echomimic_v2",
        "echomimic_v3": "external/echomimic_v3",
        "hallo3": "external/hallo3",
    }
    return path(repos[name])


def backend_marker(name: str) -> Path:
    return CACHE_ROOT / f"{name}_env_ok"
