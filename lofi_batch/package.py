from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_ROOT = ROOT / "output" / "lofi_batch"
REQUIRED_READY = ("playlist.wav", "cover.png", "video.mp4", "prompt.json", "meta.json")


def new_package_dir(out_root: Path, run_id: str, slug: str) -> Path:
    d = out_root / "queue" / f"{run_id}_{slug}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_meta(package_dir: Path, **fields: Any) -> Path:
    path = package_dir / "meta.json"
    data: dict[str, Any] = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    data.update(fields)
    data["updated_at"] = datetime.now().isoformat()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def read_meta(package_dir: Path) -> dict[str, Any]:
    return json.loads((package_dir / "meta.json").read_text(encoding="utf-8"))


def mark_ready(package_dir: Path) -> None:
    missing: list[str] = []
    for n in REQUIRED_READY:
        if n == "meta.json":
            if not (package_dir / n).exists():
                missing.append(n)
            continue
        p = package_dir / n
        if not p.exists():
            missing.append(n)
        elif n in ("playlist.wav", "cover.png", "video.mp4") and p.stat().st_size <= 0:
            missing.append(f"{n}(empty)")
    if missing:
        raise FileNotFoundError(f"Cannot mark ready, missing: {missing}")
    write_meta(package_dir, status="ready")


def list_ready_packages(queue_root: Path) -> list[Path]:
    if not queue_root.exists():
        return []
    ready: list[Path] = []
    for d in sorted(queue_root.iterdir()):
        if not d.is_dir():
            continue
        meta = d / "meta.json"
        if not meta.exists():
            continue
        data = json.loads(meta.read_text(encoding="utf-8"))
        if data.get("status") != "ready":
            continue
        if all(
            (d / n).exists() and (d / n).stat().st_size > 0
            for n in ("playlist.wav", "cover.png", "video.mp4")
        ):
            ready.append(d)
    return ready


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def already_published_today(state: dict[str, Any], today: str) -> bool:
    return state.get("last_publish_date") == today
