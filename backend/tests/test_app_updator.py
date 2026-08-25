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
    assert not u._path_allowed_from_whitelist("var/data/secret")
    assert not u._path_allowed_from_whitelist(".env")
    assert not u._path_allowed_from_whitelist("backend/.venv/lib/x")
    assert not u._path_allowed_from_whitelist("static/index.html")
    assert u._is_protected("uploads/avatars/a.png")
    assert u._is_protected("var/data/secret")


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


def test_snapshot_and_restore_source_paths(tmp_path: Path):
    install = tmp_path / "install"
    (install / "backend" / "app").mkdir(parents=True)
    (install / "backend" / "alembic").mkdir(parents=True)
    (install / "VERSION").write_text("0.3.0\n", encoding="utf-8")
    (install / "backend" / "app" / "keep.py").write_text("old\n", encoding="utf-8")
    (install / "backend" / "requirements.txt").write_text("x==1\n", encoding="utf-8")

    backup = tmp_path / "rollback"
    saved = u.snapshot_source_paths(install, backup)
    assert "VERSION" in saved
    assert any("backend/app" in s or s == "backend/app" for s in saved)

    (install / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    (install / "backend" / "app" / "keep.py").write_text("new\n", encoding="utf-8")
    u.restore_source_paths(install, backup)
    assert (install / "VERSION").read_text(encoding="utf-8") == "0.3.0\n"
    assert (install / "backend" / "app" / "keep.py").read_text(encoding="utf-8") == "old\n"


def test_run_install_migrations_raises_on_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    install = tmp_path / "install"
    (install / "backend").mkdir(parents=True)
    fake_py = install / "backend" / ".venv" / "bin" / "python"
    fake_py.parent.mkdir(parents=True)
    fake_py.write_text("", encoding="utf-8")

    class FakeProc:
        returncode = 1
        stdout = ""
        stderr = "CAST AS JSON not supported"

    monkeypatch.setattr(u.subprocess, "run", lambda *a, **k: FakeProc())
    with pytest.raises(RuntimeError, match="数据库迁移失败"):
        u.run_install_migrations(install)


def test_apply_update_core_rolls_back_when_migrate_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    install = tmp_path / "install"
    (install / "backend" / "app").mkdir(parents=True)
    (install / "backend" / "alembic").mkdir(parents=True)
    (install / "VERSION").write_text("0.3.0\n", encoding="utf-8")
    (install / "backend" / "app" / "x.py").write_text("old\n", encoding="utf-8")
    (install / "backend" / "requirements.txt").write_text("httpx\n", encoding="utf-8")
    (install / "static").mkdir()
    data = install / "data"
    data.mkdir()

    zip_path_holder: dict[str, Path] = {}

    async def fake_download(url: str, dest: Path, proxy: str | None = None) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.name == "source.zip":
            root = "zhange-stats-x/"
            with zipfile.ZipFile(dest, "w") as zf:
                zf.writestr(root + "VERSION", "0.3.1\n")
                zf.writestr(root + "backend/app/x.py", "new\n")
                zf.writestr(root + "backend/requirements.txt", "httpx\n")
                zf.writestr(root + "backend/alembic/.keep", "")
            zip_path_holder["zip"] = dest
        else:
            dest.write_bytes(b"")

    monkeypatch.setattr(u, "_download", fake_download)
    monkeypatch.setattr(u, "pip_install_requirements", lambda *_a, **_k: None)
    monkeypatch.setattr(u, "apply_static_tar", lambda *_a, **_k: None)

    def boom(_install: Path) -> None:
        # Simulate on-disk new code already applied, then migrate fails.
        assert (install / "VERSION").read_text(encoding="utf-8").strip() == "0.3.1"
        raise RuntimeError("数据库迁移失败，已中止重启以免服务挂死。详情: boom")

    monkeypatch.setattr(u, "run_install_migrations", boom)
    monkeypatch.setattr(
        u,
        "get_settings",
        lambda: type(
            "S",
            (),
            {
                "DATA_DIR": str(data),
                "STATIC_DIR": str(install / "static"),
                "UPDATE_GITHUB_REPO": "739790797/zhange-stats",
                "APP_VERSION": "0.3.0",
            },
        )(),
    )

    target = u.ReleaseInfo(
        tag_name="v0.3.1",
        name="v0.3.1",
        body="",
        published_at="",
        zipball_url="https://example.com/src.zip",
        static_asset_url="",
    )
    import asyncio

    result = asyncio.run(
        u._apply_update_core(
            target=target,
            proxy=None,
            reboot=True,
            install_dir=install,
        )
    )
    assert result.ok is False
    assert "回滚" in result.message
    assert (install / "VERSION").read_text(encoding="utf-8").strip() == "0.3.0"
    assert (install / "backend" / "app" / "x.py").read_text(encoding="utf-8") == "old\n"


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
