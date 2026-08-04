from pathlib import Path

from lofi_batch import run_batch


def test_skips_when_playlist_exists(tmp_path: Path, monkeypatch):
    package = tmp_path / "pkg"
    package.mkdir()
    playlist = package / "playlist.wav"
    playlist.write_bytes(b"x" * 64)
    called = {"n": 0}

    def boom(**kwargs):
        called["n"] += 1
        raise AssertionError("_run_generate should not be called")

    monkeypatch.setattr(run_batch, "_run_generate", boom)
    result = run_batch.process_package_audio(
        package,
        "prompt with NEGATIVE PROMPT",
        slug="demo",
        tracks=2,
        duration=30,
        config_path="x",
        lm_model="y",
        backend="pt",
    )
    assert result["status"] == "skipped"
    assert called["n"] == 0
    assert Path(result["playlist"]) == playlist
