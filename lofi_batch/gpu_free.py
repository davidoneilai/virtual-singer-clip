from __future__ import annotations

import argparse
import subprocess


def parse_nvidia_smi_csv(text: str) -> list[dict[str, float]]:
    rows = []
    for line in text.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        rows.append(
            {
                "index": float(parts[0]),
                "util": float(parts[1]),
                "mem_free_mib": float(parts[2]),
            }
        )
    return rows


def is_gpu_free(
    gpu_index: int,
    *,
    util_max: float = 5.0,
    mem_free_min_mib: int = 20000,
    smi_output: str | None = None,
) -> bool:
    if smi_output is None:
        cmd = [
            "nvidia-smi",
            "--query-gpu=index,utilization.gpu,memory.free",
            "--format=csv,noheader,nounits",
        ]
        smi_output = subprocess.check_output(cmd, text=True)
    for row in parse_nvidia_smi_csv(smi_output):
        if int(row["index"]) != int(gpu_index):
            continue
        return row["util"] <= util_max and row["mem_free_mib"] >= mem_free_min_mib
    raise ValueError(f"GPU index {gpu_index} not found in nvidia-smi output")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check if a GPU looks free")
    parser.add_argument("--gpu", type=int, default=0)
    parser.add_argument("--util-max", type=float, default=5.0)
    parser.add_argument("--mem-free-min-mib", type=int, default=20000)
    args = parser.parse_args()
    free = is_gpu_free(args.gpu, util_max=args.util_max, mem_free_min_mib=args.mem_free_min_mib)
    print("free" if free else "busy")
    raise SystemExit(0 if free else 1)


if __name__ == "__main__":
    main()
