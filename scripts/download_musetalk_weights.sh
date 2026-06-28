#!/usr/bin/env bash
# Download MuseTalk weights into external/MuseTalk/models/
# Run inside the GPU Docker image (recommended) or any env with huggingface_hub + gdown.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MT="$ROOT/external/MuseTalk"
cd "$MT"

MODELS="$MT/models"
mkdir -p "$MODELS"/{musetalk,musetalkV15,syncnet,dwpose,face-parse-bisent,sd-vae,whisper}

python - <<'PY'
import subprocess
import sys
from pathlib import Path

models = Path("models")

def pip_install(*packages: str) -> None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-U", *packages])


def hf_download(repo: str, local_dir: Path, include: list[str]) -> None:
    from huggingface_hub import snapshot_download

    local_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=repo,
        local_dir=str(local_dir),
        allow_patterns=include,
        local_dir_use_symlinks=False,
    )
    print(f"OK {repo} -> {local_dir}")


try:
    import huggingface_hub  # noqa: F401
except ImportError:
    pip_install("huggingface_hub")

try:
    import gdown  # noqa: F401
except ImportError:
    pip_install("gdown")

from gdown import download as gdown_download
from huggingface_hub import snapshot_download

hf_download("TMElyralab/MuseTalk", models, ["musetalk/musetalk.json", "musetalk/pytorch_model.bin"])
hf_download("TMElyralab/MuseTalk", models, ["musetalkV15/musetalk.json", "musetalkV15/unet.pth"])
hf_download("stabilityai/sd-vae-ft-mse", models / "sd-vae", ["config.json", "diffusion_pytorch_model.bin"])
hf_download("openai/whisper-tiny", models / "whisper", ["config.json", "pytorch_model.bin", "preprocessor_config.json"])
hf_download("yzd-v/DWPose", models / "dwpose", ["dw-ll_ucoco_384.pth"])
hf_download("ByteDance/LatentSync", models / "syncnet", ["latentsync_syncnet.pt"])

face_parse = models / "face-parse-bisent"
face_parse.mkdir(parents=True, exist_ok=True)
gdown_download(
    id="154JgKpzCPW82qINcVieuPH3fZ2e0P812",
    output=str(face_parse / "79999_iter.pth"),
    quiet=False,
)
print("OK gdown face-parse-bisent")

resnet = face_parse / "resnet18-5c106cde.pth"
if not resnet.exists():
    subprocess.check_call(
        [
            "curl",
            "-L",
            "https://download.pytorch.org/models/resnet18-5c106cde.pth",
            "-o",
            str(resnet),
        ]
    )
print("OK resnet18")
PY

required=(
  "$MODELS/musetalkV15/unet.pth"
  "$MODELS/musetalkV15/musetalk.json"
  "$MODELS/sd-vae/diffusion_pytorch_model.bin"
  "$MODELS/whisper/pytorch_model.bin"
  "$MODELS/dwpose/dw-ll_ucoco_384.pth"
  "$MODELS/face-parse-bisent/79999_iter.pth"
  "$MODELS/face-parse-bisent/resnet18-5c106cde.pth"
)

missing=0
for f in "${required[@]}"; do
  if [ ! -f "$f" ]; then
    echo "MISSING: $f" >&2
    missing=1
  fi
done

if [ "$missing" -ne 0 ]; then
  echo "Download incomplete." >&2
  exit 1
fi

echo "MuseTalk weights ready under $MODELS"
