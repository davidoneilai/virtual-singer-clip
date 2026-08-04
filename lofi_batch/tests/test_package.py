from pathlib import Path

from lofi_batch.package import (
    already_published_today,
    list_ready_packages,
    load_state,
    mark_ready,
    new_package_dir,
    save_state,
    write_meta,
)


def _touch(p: Path, size: int = 10) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * size)


def test_mark_ready_and_list_order(tmp_path: Path):
    queue = tmp_path / "queue"
    a = new_package_dir(tmp_path, "2026-08-04_1000", "alpha")
    b = new_package_dir(tmp_path, "2026-08-04_1100", "beta")
    for d in (a, b):
        for name in ("playlist.wav", "cover.png", "video.mp4", "prompt.json"):
            _touch(d / name)
        write_meta(d, status="generating", title="t", description="d", tags=["x"])
        mark_ready(d)
    ready = list_ready_packages(queue)
    assert [p.name for p in ready] == ["2026-08-04_1000_alpha", "2026-08-04_1100_beta"]


def test_daily_cap_state(tmp_path: Path):
    state_path = tmp_path / "state.json"
    save_state(state_path, {"last_publish_date": "2026-08-04", "last_video_id": "abc"})
    st = load_state(state_path)
    assert already_published_today(st, "2026-08-04") is True
    assert already_published_today(st, "2026-08-05") is False
