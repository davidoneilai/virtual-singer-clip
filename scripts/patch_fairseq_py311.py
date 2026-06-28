"""Patch fairseq + hydra dataclass defaults for Python 3.11+ (RVC HuBERT extract)."""
from __future__ import annotations

import re
import site
import sys
from pathlib import Path

SKIP_MARKER = "RVC_SKIP_HYDRA_INIT"
MUTABLE_DEFAULT = re.compile(r"^(\s+)(\w+): (\w+) = \3\(\)$", re.MULTILINE)


def _site_roots() -> list[Path]:
    return [Path(p) for p in site.getsitepackages() + [site.getusersitepackages()] if p]


def _find_package_root(name: str) -> Path:
    for root in _site_roots():
        candidate = root / name
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(f"package not found: {name}")


def _ensure_field_import(text: str) -> str:
    if "from dataclasses import dataclass, field" in text:
        return text
    return text.replace(
        "from dataclasses import dataclass",
        "from dataclasses import dataclass, field",
        1,
    )


def _patch_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    updated, count = MUTABLE_DEFAULT.subn(
        r"\1\2: \3 = field(default_factory=\3)",
        text,
    )
    if count == 0:
        return 0
    updated = _ensure_field_import(updated)
    path.write_text(updated, encoding="utf-8")
    return count


def _patch_tree(root: Path, label: str) -> int:
    total = 0
    for path in sorted(root.rglob("*.py")):
        n = _patch_file(path)
        if n:
            print(f"  {label}: {n} field(s) in {path.relative_to(root.parent)}")
            total += n
    return total


def patch_fairseq_skip_hydra_init() -> None:
    path = _find_package_root("fairseq") / "__init__.py"
    text = path.read_text(encoding="utf-8")
    if SKIP_MARKER in text:
        print("fairseq hydra_init already disabled")
        return
    if "hydra_init()" not in text:
        raise RuntimeError(f"hydra_init() not found in {path}")
    text = text.replace(
        "hydra_init()",
        f"pass  # {SKIP_MARKER}: RVC HuBERT only; hydra breaks on py311",
        1,
    )
    path.write_text(text, encoding="utf-8")
    print("Disabled fairseq hydra_init")


def main() -> None:
    fairseq_root = _find_package_root("fairseq")
    hydra_root = _find_package_root("hydra")

    print("Patching fairseq dataclasses (recursive)...")
    n_fairseq = _patch_tree(fairseq_root, "fairseq")
    print(f"fairseq total: {n_fairseq} field(s)")

    print("Patching hydra dataclasses (recursive)...")
    n_hydra = _patch_tree(hydra_root, "hydra")
    print(f"hydra total: {n_hydra} field(s)")

    patch_fairseq_skip_hydra_init()

    import fairseq.checkpoint_utils  # noqa: F401

    print("fairseq ok (checkpoint_utils)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"patch_fairseq_py311 failed: {exc}", file=sys.stderr)
        raise
