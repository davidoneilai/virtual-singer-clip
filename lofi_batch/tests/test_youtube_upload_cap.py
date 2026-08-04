import json
from pathlib import Path

from lofi_batch.package import new_package_dir, write_meta, mark_ready, save_state
from lofi_batch.youtube_upload import upload_one_if_allowed


def _ready_pkg(out_root: Path, run_id: str, slug: str) -> Path:
    d = new_package_dir(out_root, run_id, slug)
    for name in ("playlist.wav", "cover.png", "video.mp4", "prompt.json"):
        (d / name).write_bytes(b"x" * 20)
    (d / "prompt.json").write_text(
        json.dumps(
            {
                "slug": slug,
                "music_prompt": "x\n\nNEGATIVE PROMPT\nNO",
                "image_prompt": "y",
                "title": f"Title {slug}",
                "description": "desc",
                "tags": ["lofi"],
            }
        ),
        encoding="utf-8",
    )
    write_meta(d, status="generating", title=f"Title {slug}", description="desc", tags=["lofi"])
    mark_ready(d)
    return d


def test_skips_when_already_published(tmp_path: Path):
    out = tmp_path
    save_state(out / "state.json", {"last_publish_date": "2026-08-04", "last_video_id": "v1"})
    _ready_pkg(out, "2026-08-04_1000", "a")
    result = upload_one_if_allowed(out, dry_run=True, tz_name=None)
    # force today via monkeypatch by setting state to today after computing — instead call with state
    # Re-check: already_published uses state date == today_str(). Set state to actual today.
    from lofi_batch.youtube_upload import today_str

    save_state(out / "state.json", {"last_publish_date": today_str(), "last_video_id": "v1"})
    result = upload_one_if_allowed(out, dry_run=False)
    assert result["status"] == "skipped_daily_cap"


def test_dry_run_selects_oldest(tmp_path: Path):
    out = tmp_path
    _ready_pkg(out, "2026-08-04_1000", "alpha")
    _ready_pkg(out, "2026-08-04_1100", "beta")
    result = upload_one_if_allowed(out, dry_run=True)
    assert result["status"] == "dry_run"
    assert result["package"].endswith("2026-08-04_1000_alpha")


def test_uploader_moves_on_success(tmp_path: Path):
    out = tmp_path
    pkg = _ready_pkg(out, "2026-08-04_1000", "alpha")

    def fake_upload(package_dir: Path, privacy: str):
        assert package_dir == pkg
        return {"video_id": "vid123", "url": "https://youtube.com/watch?v=vid123"}

    result = upload_one_if_allowed(out, _uploader=fake_upload, privacy="unlisted")
    assert result["status"] == "published"
    assert result["video_id"] == "vid123"
    assert not pkg.exists()
    published = out / "published" / "2026-08-04_1000_alpha"
    assert published.exists()
    state = json.loads((out / "state.json").read_text(encoding="utf-8"))
    assert state["last_video_id"] == "vid123"
