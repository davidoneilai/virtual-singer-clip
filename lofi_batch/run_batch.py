#!/usr/bin/env python3
"""Generate ~1h instrumental playlists from lofi_batch/prompts/*.txt."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PROMPTS_DIR = ROOT / "lofi_batch" / "prompts"
DEFAULT_OUT = ROOT / "output" / "lofi_batch"


def _slug_from_path(path: Path) -> str:
    return path.stem.strip().replace(" ", "_")


def _load_prompts(prompts_dir: Path) -> list[tuple[str, str]]:
    files = sorted(prompts_dir.glob("*.txt"))
    if not files:
        raise FileNotFoundError(f"No .txt prompts in {prompts_dir}")
    items: list[tuple[str, str]] = []
    for path in files:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            print(f"Skipping empty prompt: {path}", flush=True)
            continue
        items.append((_slug_from_path(path), text))
    if not items:
        raise FileNotFoundError(f"All prompts empty in {prompts_dir}")
    return items


def _write_instrumental_lyrics(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[Instrumental]\n", encoding="utf-8")
    return path


def _run_generate(
    *,
    prompt: str,
    lyrics: Path,
    out_wav: Path,
    duration: int,
    config_path: str,
    lm_model: str,
    backend: str,
) -> None:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(SCRIPTS / "01_generate_song_acestep.py"),
        "--lyrics",
        str(lyrics),
        "--out",
        str(out_wav),
        "--duration",
        str(duration),
        "--backend",
        backend,
        "--config-path",
        config_path,
        "--lm-model",
        lm_model,
        "--vocal-language",
        "en",
        "--prompt",
        prompt,
    ]
    print(f"=== generate {out_wav.name} ===", flush=True)
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def _ffmpeg_concat(track_paths: list[Path], playlist: Path) -> None:
    if not track_paths:
        raise RuntimeError("No tracks to concatenate")
    playlist.parent.mkdir(parents=True, exist_ok=True)
    list_file = playlist.parent / "concat.txt"
    # ffmpeg concat demuxer requires paths escaped carefully; use absolute paths
    lines = []
    for p in track_paths:
        escaped = str(p.resolve()).replace("'", r"'\''")
        lines.append(f"file '{escaped}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c",
        "copy",
        str(playlist),
    ]
    print(f"=== concat {len(track_paths)} tracks → {playlist} ===", flush=True)
    subprocess.run(cmd, check=True)


def _process_prompt_dir(
    *,
    slug: str,
    prompt: str,
    prompt_dir: Path,
    tracks: int,
    duration: int,
    config_path: str,
    lm_model: str,
    backend: str,
    fail_fast: bool,
) -> dict:
    tracks_dir = prompt_dir / "tracks"
    playlist = prompt_dir / "playlist.wav"
    lyrics = prompt_dir / "lyrics.txt"
    manifest_path = prompt_dir / "manifest.json"

    if playlist.exists() and playlist.stat().st_size > 0:
        print(f"Skipping {slug}: playlist.wav already exists", flush=True)
        return {
            "slug": slug,
            "prompt": prompt,
            "status": "skipped",
            "playlist": str(playlist),
        }

    _write_instrumental_lyrics(lyrics)
    tracks_dir.mkdir(parents=True, exist_ok=True)

    track_results: list[dict] = []
    ok_paths: list[Path] = []

    for i in range(1, tracks + 1):
        name = f"{i:02d}.wav"
        out_wav = tracks_dir / name
        entry: dict = {"index": i, "path": str(out_wav)}
        if out_wav.exists() and out_wav.stat().st_size > 0:
            print(f"Resume skip: {out_wav}", flush=True)
            entry["status"] = "skipped"
            ok_paths.append(out_wav)
            track_results.append(entry)
            continue
        try:
            _run_generate(
                prompt=prompt,
                lyrics=lyrics,
                out_wav=out_wav,
                duration=duration,
                config_path=config_path,
                lm_model=lm_model,
                backend=backend,
            )
            entry["status"] = "ok"
            ok_paths.append(out_wav)
        except subprocess.CalledProcessError as exc:
            entry["status"] = "failed"
            entry["error"] = str(exc)
            print(f"FAILED track {name} for {slug}: {exc}", flush=True)
            if fail_fast:
                track_results.append(entry)
                manifest = {
                    "slug": slug,
                    "prompt": prompt,
                    "status": "failed",
                    "tracks": track_results,
                    "config_path": config_path,
                    "duration": duration,
                }
                manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
                raise
        track_results.append(entry)

    if not ok_paths:
        manifest = {
            "slug": slug,
            "prompt": prompt,
            "status": "failed",
            "tracks": track_results,
            "config_path": config_path,
            "duration": duration,
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    _ffmpeg_concat(ok_paths, playlist)
    manifest = {
        "slug": slug,
        "prompt": prompt,
        "status": "ok",
        "playlist": str(playlist),
        "tracks": track_results,
        "config_path": config_path,
        "lm_model": lm_model,
        "duration": duration,
        "n_tracks_ok": len(ok_paths),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Done {slug}: {playlist}", flush=True)
    return manifest


def _process_prompt(
    *,
    slug: str,
    prompt: str,
    run_dir: Path,
    tracks: int,
    duration: int,
    config_path: str,
    lm_model: str,
    backend: str,
    fail_fast: bool,
) -> dict:
    return _process_prompt_dir(
        slug=slug,
        prompt=prompt,
        prompt_dir=run_dir / slug,
        tracks=tracks,
        duration=duration,
        config_path=config_path,
        lm_model=lm_model,
        backend=backend,
        fail_fast=fail_fast,
    )


def process_package_audio(
    package_dir: Path,
    prompt: str,
    *,
    slug: str,
    tracks: int,
    duration: int,
    config_path: str,
    lm_model: str,
    backend: str,
    fail_fast: bool = False,
) -> dict:
    """Generate playlist.wav into an existing queue package directory."""
    package_dir.mkdir(parents=True, exist_ok=True)
    return _process_prompt_dir(
        slug=slug,
        prompt=prompt,
        prompt_dir=package_dir,
        tracks=tracks,
        duration=duration,
        config_path=config_path,
        lm_model=lm_model,
        backend=backend,
        fail_fast=fail_fast,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prompts-dir",
        type=Path,
        default=PROMPTS_DIR,
        help="Directory of *.txt prompts",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=DEFAULT_OUT,
        help="Output root (run_id subdirectory created under this)",
    )
    parser.add_argument(
        "--run-id",
        default=os.environ.get("RUN_ID") or datetime.now().strftime("%Y-%m-%d_%H%M"),
    )
    parser.add_argument(
        "--tracks",
        type=int,
        default=int(os.environ.get("TRACKS", "20")),
        help="Tracks per prompt (default 20 ≈ 1h at 180s)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=int(os.environ.get("DURATION", "180")),
        help="Seconds per track",
    )
    parser.add_argument(
        "--config-path",
        default=os.environ.get("CONFIG_PATH", "acestep-v15-xl-turbo"),
    )
    parser.add_argument(
        "--lm-model",
        default=os.environ.get("LM_MODEL", "acestep-5Hz-lm-1.7B"),
    )
    parser.add_argument(
        "--backend",
        default=os.environ.get("BACKEND", "pt"),
        choices=["pt", "vllm", "mlx"],
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        default=os.environ.get("FAIL_FAST", "").strip() in ("1", "true", "yes"),
    )
    parser.add_argument(
        "--slug",
        default=None,
        help="Only process this prompt slug (filename without .txt)",
    )
    parser.add_argument(
        "--package-dir",
        type=Path,
        default=None,
        help="Generate audio into this package dir (reads prompt.json)",
    )
    args = parser.parse_args()

    # Ensure scripts/ is importable when 01 runs; it already uses cwd ROOT.
    sys.path.insert(0, str(SCRIPTS))
    sys.path.insert(0, str(ROOT))

    if args.package_dir is not None:
        from lofi_batch.prompt_schema import validate_prompt

        package_dir = args.package_dir.resolve()
        prompt_path = package_dir / "prompt.json"
        data = validate_prompt(json.loads(prompt_path.read_text(encoding="utf-8")))
        summary = process_package_audio(
            package_dir,
            data["music_prompt"],
            slug=data["slug"],
            tracks=args.tracks,
            duration=args.duration,
            config_path=args.config_path,
            lm_model=args.lm_model,
            backend=args.backend,
            fail_fast=args.fail_fast,
        )
        summary_path = package_dir / "batch_summary.json"
        summary_path.write_text(json.dumps([summary], indent=2), encoding="utf-8")
        print(f"Summary: {summary_path}", flush=True)
        return

    prompts = _load_prompts(args.prompts_dir)
    if args.slug:
        prompts = [(s, p) for s, p in prompts if s == args.slug]
        if not prompts:
            raise SystemExit(f"No prompt with slug={args.slug!r}")

    run_dir = args.out_root / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "batch.log"
    print(f"Run dir: {run_dir}", flush=True)
    print(f"Prompts: {len(prompts)} | tracks={args.tracks} duration={args.duration}s", flush=True)

    summaries: list[dict] = []
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"=== start {datetime.now().isoformat()} ===\n")
        for slug, prompt in prompts:
            try:
                summary = _process_prompt(
                    slug=slug,
                    prompt=prompt,
                    run_dir=run_dir,
                    tracks=args.tracks,
                    duration=args.duration,
                    config_path=args.config_path,
                    lm_model=args.lm_model,
                    backend=args.backend,
                    fail_fast=args.fail_fast,
                )
            except Exception as exc:
                summary = {"slug": slug, "prompt": prompt, "status": "failed", "error": str(exc)}
                print(f"Prompt {slug} failed: {exc}", flush=True)
                if args.fail_fast:
                    summaries.append(summary)
                    break
            summaries.append(summary)
            log.write(json.dumps(summary) + "\n")
            log.flush()
        log.write(f"=== end {datetime.now().isoformat()} ===\n")

    summary_path = run_dir / "batch_summary.json"
    summary_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(f"Summary: {summary_path}", flush=True)


if __name__ == "__main__":
    main()
