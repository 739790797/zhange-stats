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


def test_check_cache_roundtrip(monkeypatch: pytest.MonkeyPatch):
    u.invalidate_check_cache()
    rel = u.ReleaseInfo(
        tag_name="v9.9.9",
        name="v9.9.9",
        body="",
        published_at="",
        zipball_url="https://example.com/z.zip",
    )
    u._write_check_cache(rel, [rel])
    cached = u._read_check_cache()
    assert cached is not None
    latest, releases = cached
    assert latest is not None and latest.tag_name == "v9.9.9"
    assert len(releases) == 1

    monkeypatch.setattr(u, "CHECK_CACHE_TTL_SEC", 0)
    u._write_check_cache(rel, [rel])
    # expires_at = now + 0 → immediately stale on next read after tiny sleep
    import time

    time.sleep(0.01)
    assert u._read_check_cache() is None
    u.invalidate_check_cache()
    assert u._read_check_cache() is None


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


def test_update_allowed_requires_writable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    install = tmp_path / "install"
    (install / "backend" / "app").mkdir(parents=True)
    (install / "VERSION").write_text("0.2.22\n", encoding="utf-8")
    (install / "static").mkdir()
    data = install / "data"
    data.mkdir()

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOW_IN_APP_UPDATE", "true")
    monkeypatch.setenv("APP_INSTALL_DIR", str(install))
    monkeypatch.setenv("DATA_DIR", str(data))
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(u, "resolve_install_dir", lambda: install.resolve())
    monkeypatch.setattr(
        u,
        "get_settings",
        lambda: type(
            "S",
            (),
            {
                "allow_in_app_update": True,
                "DATA_DIR": str(data),
                "APP_INSTALL_DIR": str(install),
                "APP_VERSION": "0.2.22",
            },
        )(),
    )

    ok, _ = u.update_allowed()
    assert ok is True

    # Simulate root-owned unwritable app tree
    app_dir = install / "backend" / "app"
    monkeypatch.setattr(
        u.os,
        "access",
        lambda path, mode, **kwargs: False
        if str(path) == str(app_dir) and mode == u.os.W_OK
        else True,
    )
    ok2, reason = u.update_allowed()
    assert ok2 is False
    assert "不可写" in reason
    get_settings.cache_clear()


def test_build_reboot_argv_uvicorn_console_script(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        u.sys,
        "argv",
        ["/opt/zhange-stats/backend/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0"],
    )
    exe = "/opt/zhange-stats/backend/.venv/bin/python"
    argv = u._build_reboot_argv(exe)
    assert argv[0] == exe
    assert argv[1].endswith("uvicorn")
    assert "app.main:app" in argv


def test_build_reboot_argv_python_dash_m(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        u.sys,
        "argv",
        ["python", "-m", "uvicorn", "app.main:app", "--port", "8000"],
    )
    exe = "/usr/bin/python3"
    argv = u._build_reboot_argv(exe)
    assert argv == [exe, "-m", "uvicorn", "app.main:app", "--port", "8000"]


def test_resolve_target_latest_and_explicit():
    current = "0.2.18"
    older = u.ReleaseInfo(
        tag_name="v0.2.17",
        name="v0.2.17",
        body="",
        published_at="",
        zipball_url="https://example.com/a.zip",
    )
    newer = u.ReleaseInfo(
        tag_name="v0.2.19",
        name="v0.2.19",
        body="",
        published_at="",
        zipball_url="https://example.com/b.zip",
    )
    resolved = u._resolve_target_release([newer, older], "latest", current)
    assert isinstance(resolved, u.ReleaseInfo)
    assert resolved.tag_name == "v0.2.19"

    already = u._resolve_target_release([older], "latest", current)
    assert isinstance(already, u.UpdateResult)
    assert already.ok is False
    assert "最新" in already.message

    explicit = u._resolve_target_release([newer, older], "v0.2.17", current)
    assert isinstance(explicit, u.ReleaseInfo)
    assert explicit.tag_name == "v0.2.17"

    missing = u._resolve_target_release([newer], "v9.9.9", current)
    assert isinstance(missing, u.UpdateResult)
    assert "未找到" in missing.message


def test_update_lock_rejects_concurrent(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(u, "update_allowed", lambda: (True, ""))

    held = u._lock.acquire(blocking=False)
    assert held
    try:
        import asyncio

        result = asyncio.run(u.apply_update(version="latest", reboot=False))
        assert result.ok is False
        assert "进行中" in result.message

        queued = asyncio.run(u.enqueue_update(version="latest", reboot=False))
        assert queued.ok is False
        assert "进行中" in queued.message
    finally:
        u._lock.release()
