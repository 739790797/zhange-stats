"""Unit tests for AstrBot-style app self-update helpers."""

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from app.services import app_updator as u


def test_compare_version_semver():
    assert u.compare_version("0.2.15", "0.2.14") > 0
    assert u.compare_version("v0.2.14", "0.2.14") == 0
    assert u.compare_version("0.2.13", "0.2.14") < 0
    assert u.compare_version("1.0.0", "0.9.9") > 0


def test_path_whitelist_and_protected(tmp_path: Path):
    assert u._path_allowed_from_whitelist("backend/app/main.py")
    assert u._path_allowed_from_whitelist("VERSION")
    assert not u._path_allowed_from_whitelist("data/secret")
    assert not u._path_allowed_from_whitelist(".env")
    assert not u._path_allowed_from_whitelist("backend/.venv/lib/x")
    assert not u._path_allowed_from_whitelist("static/index.html")
    assert u._is_protected("uploads/avatars/a.png")


def test_apply_source_zip_whitelist_only(tmp_path: Path):
    install = tmp_path / "install"
    install.mkdir()
    (install / "data").mkdir()
    (install / "data" / "keep.txt").write_text("keep", encoding="utf-8")
    (install / ".env").write_text("SECRET=1", encoding="utf-8")
    (install / "backend" / "app").mkdir(parents=True)
    (install / "backend" / "app" / "old.py").write_text("old", encoding="utf-8")

    # Build a github-like zipball
    zip_path = tmp_path / "src.zip"
    root = "zhange-stats-abc123/"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(root + "VERSION", "9.9.9\n")
        zf.writestr(root + "backend/app/new.py", "new\n")
        zf.writestr(root + "backend/requirements.txt", "httpx==0.0\n")
        zf.writestr(root + ".env", "HACKED=1\n")
        zf.writestr(root + "data/evil.txt", "nope\n")
        zf.writestr(root + "README.md", "readme\n")

    applied = u.apply_source_zip(zip_path, install)
    assert "VERSION" in applied
    assert any(a.startswith("backend/app") for a in applied)
    assert (install / "VERSION").read_text(encoding="utf-8").strip() == "9.9.9"
    assert (install / "backend" / "app" / "new.py").read_text(encoding="utf-8") == "new\n"
    assert not (install / "backend" / "app" / "old.py").exists()
    assert (install / ".env").read_text(encoding="utf-8") == "SECRET=1"
    assert (install / "data" / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert not (install / "data" / "evil.txt").exists()


def test_apply_static_tar(tmp_path: Path):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "old.html").write_text("old", encoding="utf-8")

    tar_path = tmp_path / "static.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        data = b"<html>ok</html>"
        info = tarfile.TarInfo(name="index.html")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))

    u.apply_static_tar(tar_path, static_dir)
    assert (static_dir / "index.html").read_bytes() == b"<html>ok</html>"
    assert not (static_dir / "old.html").exists()


def test_update_lock_rejects_concurrent(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(u, "update_allowed", lambda: (True, ""))

    held = u._lock.acquire(blocking=False)
    assert held
    try:
        import asyncio

        result = asyncio.run(u.apply_update(version="latest", reboot=False))
        assert result.ok is False
        assert "进行中" in result.message
    finally:
        u._lock.release()
