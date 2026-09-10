"""Unit tests for AstrBot-style app self-update helpers."""

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import httpx
import pytest

from app.services import app_updator as u


def test_cpu_torch_pip_uses_official_cpu_index():
    python = Path("/venv/bin/python")
    cmd = u.cpu_torch_pip_cmd(python)
    assert cmd[0] == str(python)
    assert cmd[-2:] == ["--index-url", u.TORCH_CPU_INDEX]
    assert "torch" in cmd and "torchvision" in cmd
    assert "cuda" not in " ".join(cmd).lower()


def test_torch_constraint_lines_only_pins_torch_family():
    freeze = "\n".join(
        [
            "easyocr==1.7.2",
            "torch==2.8.0+cpu",
            "torchvision==0.23.0+cpu",
            "nvidia-cudnn-cu13==9.24.0.43",
        ]
    )
    assert u.torch_constraint_lines(freeze) == [
        "torch==2.8.0+cpu",
        "torchvision==0.23.0+cpu",
    ]


def test_pip_install_requirements_pins_cpu_torch_before_requirements(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    install = tmp_path / "install"
    backend = install / "backend"
    venv_py = backend / ".venv" / "bin" / "python"
    venv_py.parent.mkdir(parents=True)
    venv_py.write_text("", encoding="utf-8")
    (backend / "requirements.txt").write_text("easyocr>=1.7.2\n", encoding="utf-8")
    calls: list[list[str]] = []

    class FakePopen:
        def __init__(self, cmd, **_kwargs):
            calls.append(list(cmd))
            self.stdout = io.StringIO("ok\n")

        def wait(self) -> int:
            return 0

    class FakeProc:
        returncode = 0
        stdout = "torch==2.8.0+cpu\ntorchvision==0.23.0+cpu\neasyocr==1.7.2\n"
        stderr = ""

    def fake_run(cmd, **kwargs):
        if list(cmd)[1:4] == ["-m", "pip", "freeze"]:
            return FakeProc()
        calls.append(list(cmd))
        return FakeProc()

    monkeypatch.setattr(u.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(u.subprocess, "run", fake_run)
    u.pip_install_requirements(install)
    joined = [" ".join(c) for c in calls]
    assert any(u.TORCH_CPU_INDEX in c and "torchvision" in c for c in joined)
    req_cmds = [c for c in calls if "-r" in c]
    assert req_cmds
    assert "-c" in req_cmds[0]
    constraint = Path(req_cmds[0][req_cmds[0].index("-c") + 1])
    assert not constraint.exists()
    assert any("opencv-python-headless" in c for c in joined)


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
    assert not u._path_allowed_from_whitelist("config/app.json")
    assert not u._path_allowed_from_whitelist("config/integrations.json")
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


def test_parse_py_string_tuple():
    text = '''
SOURCE_WHITELIST: tuple[str, ...] = (
    "VERSION",
    "backend/app",
    "docs/extra.md",
)
MERGE_TREES: tuple[str, ...] = ("frontend",)
'''
    assert u.parse_py_string_tuple(text, "SOURCE_WHITELIST") == (
        "VERSION",
        "backend/app",
        "docs/extra.md",
    )
    assert u.parse_py_string_tuple(text, "MERGE_TREES") == ("frontend",)
    assert u.parse_py_string_tuple("x = 1", "SOURCE_WHITELIST") is None
    live = Path(u.__file__).read_text(encoding="utf-8")
    assert u.parse_py_string_tuple(live, "SOURCE_WHITELIST") == u.SOURCE_WHITELIST
    assert u.parse_py_string_tuple(live, "MERGE_TREES") == u.MERGE_TREES
    assert "deploy" not in u.SOURCE_WHITELIST
    assert "scripts" in u.SOURCE_WHITELIST


def test_apply_source_zip_deletes_removed_whitelist_file(tmp_path: Path):
    install = tmp_path / "install"
    install.mkdir()
    (install / "AGENTS.md").write_text("old agents\n", encoding="utf-8")
    (install / "backend" / "app").mkdir(parents=True)
    (install / "backend" / "app" / "keep.py").write_text("keep\n", encoding="utf-8")

    zip_path = tmp_path / "src.zip"
    root = "zhange-stats-abc/"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(root + "VERSION", "1.0.0\n")
        zf.writestr(root + "backend/app/keep.py", "keep\n")
        zf.writestr(root + "README.md", "readme\n")

    applied = u.apply_source_zip(zip_path, install)
    assert "-AGENTS.md" in applied
    assert not (install / "AGENTS.md").exists()
    assert (install / "README.md").read_text(encoding="utf-8") == "readme\n"


def test_remove_legacy_deploy_tree(tmp_path: Path) -> None:
    install = tmp_path / "install"
    (install / "scripts" / "linux").mkdir(parents=True)
    (install / "scripts" / "linux" / "zhange-stats.service").write_text("unit\n", encoding="utf-8")
    systemd = install / "deploy" / "systemd"
    systemd.mkdir(parents=True)
    (systemd / "zhange-stats.service").write_text("old\n", encoding="utf-8")
    assert u.remove_legacy_deploy_tree(install) is True
    assert not (install / "deploy").exists()
    assert (install / "scripts" / "linux" / "zhange-stats.service").read_text(
        encoding="utf-8"
    ) == "unit\n"
    assert u.remove_legacy_deploy_tree(install) is False


def test_apply_source_zip_removes_root_config_example(tmp_path: Path):
    install = tmp_path / "install"
    (install / "config.example").mkdir(parents=True)
    (install / "config.example" / "app.json").write_text("old\n", encoding="utf-8")
    (install / "deploy" / "old.txt").parent.mkdir(parents=True)
    (install / "deploy" / "old.txt").write_text("x\n", encoding="utf-8")
    (install / "backend" / "app").mkdir(parents=True)

    zip_path = tmp_path / "src.zip"
    root = "zhange-stats-abc/"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(root + "VERSION", "1.0.0\n")
        zf.writestr(root + "backend/app/x.py", "x\n")
        zf.writestr(root + "scripts/config.example/app.json", '{"_version": 1}\n')
        zf.writestr(root + "scripts/linux/zhange-stats.service", "unit\n")

    applied = u.apply_source_zip(zip_path, install)
    assert not (install / "config.example").exists()
    assert not (install / "deploy").exists()
    assert (install / "scripts" / "config.example" / "app.json").is_file()
    assert any(item.startswith("-config.example") for item in applied)
    assert any(item.startswith("-deploy") for item in applied)


def test_apply_source_zip_new_whitelist_path_from_incoming_updator(tmp_path: Path):
    install = tmp_path / "install"
    install.mkdir()
    (install / "backend" / "app").mkdir(parents=True)

    zip_path = tmp_path / "src.zip"
    root = "zhange-stats-abc/"
    updator = '''
SOURCE_WHITELIST: tuple[str, ...] = (
    "VERSION",
    "backend/app",
    "docs/extra.md",
)
MERGE_TREES: tuple[str, ...] = ("frontend",)
'''
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(root + "VERSION", "1.2.3\n")
        zf.writestr(root + "backend/app/main.py", "ok\n")
        zf.writestr(root + "backend/app/services/app_updator.py", updator)
        zf.writestr(root + "docs/extra.md", "new-doc\n")
        zf.writestr(root + ".env", "HACKED=1\n")

    applied = u.apply_source_zip(zip_path, install)
    assert any(a == "docs/extra.md" or a.endswith("docs/extra.md") for a in applied)
    assert (install / "docs" / "extra.md").read_text(encoding="utf-8") == "new-doc\n"
    assert not (install / ".env").exists()


def test_apply_source_zip_merges_frontend_without_wiping_node_modules(tmp_path: Path):
    install = tmp_path / "install"
    src_dir = install / "frontend" / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "old.tsx").write_text("old\n", encoding="utf-8")
    nm = install / "frontend" / "node_modules" / "keep"
    nm.mkdir(parents=True)
    (nm / "pkg.js").write_text("pkg\n", encoding="utf-8")

    zip_path = tmp_path / "src.zip"
    root = "zhange-stats-abc/"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(root + "VERSION", "1.0.0\n")
        zf.writestr(root + "backend/app/x.py", "x\n")
        zf.writestr(root + "frontend/src/new.tsx", "new\n")
        zf.writestr(root + "frontend/package.json", "{}\n")
        zf.writestr(root + "frontend/node_modules/evil.js", "nope\n")

    u.apply_source_zip(zip_path, install)
    assert (install / "frontend" / "src" / "new.tsx").read_text(encoding="utf-8") == "new\n"
    assert not (src_dir / "old.tsx").exists()
    assert (nm / "pkg.js").read_text(encoding="utf-8") == "pkg\n"
    assert not (install / "frontend" / "node_modules" / "evil.js").exists()


def test_resolve_target_force_reapplies_current():
    current = "0.2.18"
    same = u.ReleaseInfo(
        tag_name="v0.2.18",
        name="v0.2.18",
        body="",
        published_at="",
        zipball_url="https://example.com/a.zip",
    )
    skipped = u._resolve_target_release([same], "latest", current)
    assert isinstance(skipped, u.UpdateResult)
    assert skipped.skipped is True
    forced = u._resolve_target_release([same], "latest", current, force=True)
    assert isinstance(forced, u.ReleaseInfo)
    assert forced.tag_name == "v0.2.18"


def test_update_allowed_host_skips_env_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    install = tmp_path / "install"
    (install / "backend" / "app").mkdir(parents=True)
    (install / "VERSION").write_text("0.2.22\n", encoding="utf-8")
    (install / "static").mkdir()
    data = install / "data"
    data.mkdir()

    monkeypatch.setattr(u, "resolve_install_dir", lambda: install.resolve())
    monkeypatch.setattr(
        u,
        "get_settings",
        lambda: type(
            "S",
            (),
            {
                "allow_in_app_update": False,
                "DATA_DIR": str(data),
                "APP_INSTALL_DIR": str(install),
                "APP_VERSION": "0.2.22",
            },
        )(),
    )
    blocked, reason = u.update_allowed()
    assert blocked is False
    assert "不允许" in reason
    ok, _ = u.update_allowed(host=True)
    assert ok is True


def test_host_update_main_check_and_skip(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    async def fake_check(**_kwargs):
        rel = u.ReleaseInfo(
            tag_name="v9.9.9",
            name="v9.9.9",
            body="",
            published_at="",
            zipball_url="https://example.com/z.zip",
        )
        return rel, [rel]

    monkeypatch.setattr(u, "check_update", fake_check)
    monkeypatch.setattr(u, "get_settings", lambda: type("S", (), {"APP_VERSION": "0.1.0"})())
    assert u.host_update_main(["--check"]) == 0
    out = capsys.readouterr().out
    assert "CURRENT=0.1.0" in out
    assert "LATEST=9.9.9" in out
    assert "HAS_NEW=1" in out

    async def fake_apply(**_kwargs):
        return u.UpdateResult(
            ok=False,
            message="当前已经是最新版本（0.1.0）",
            version="0.1.0",
            skipped=True,
        )

    monkeypatch.setattr(u, "apply_update", fake_apply)
    assert u.host_update_main(["--version", "latest"]) == 2


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


def test_snapshot_restore_frontend_keeps_node_modules(tmp_path: Path):
    install = tmp_path / "install"
    (install / "backend" / "app").mkdir(parents=True)
    (install / "VERSION").write_text("1\n", encoding="utf-8")
    src = install / "frontend" / "src"
    src.mkdir(parents=True)
    (src / "a.tsx").write_text("old\n", encoding="utf-8")
    nm = install / "frontend" / "node_modules" / "x"
    nm.mkdir(parents=True)
    (nm / "p.js").write_text("nm\n", encoding="utf-8")

    backup = tmp_path / "rollback"
    saved = u.snapshot_source_paths(install, backup)
    assert "frontend" in saved
    assert not (backup / "frontend" / "node_modules").exists()

    (src / "a.tsx").write_text("new\n", encoding="utf-8")
    (src / "b.tsx").write_text("extra\n", encoding="utf-8")
    u.restore_source_paths(install, backup)
    assert (src / "a.tsx").read_text(encoding="utf-8") == "old\n"
    assert not (src / "b.tsx").exists()
    assert (nm / "p.js").read_text(encoding="utf-8") == "nm\n"


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
    monkeypatch.setattr(u, "update_allowed", lambda **_kwargs: (True, ""))

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


def test_download_retryable_and_size_helpers(tmp_path: Path):
    assert u._download_retryable(u.IncompleteDownload("x"))
    assert u._download_retryable(
        httpx.RemoteProtocolError(
            "peer closed connection without sending complete message body "
            "(received 6634923 bytes, expected 6889538)"
        )
    )
    not_found = httpx.Response(404, request=httpx.Request("GET", "https://example.com/x"))
    assert not u._download_retryable(
        httpx.HTTPStatusError("nope", request=not_found.request, response=not_found)
    )
    bad_gateway = httpx.Response(502, request=httpx.Request("GET", "https://example.com/x"))
    assert u._download_retryable(
        httpx.HTTPStatusError("bad", request=bad_gateway.request, response=bad_gateway)
    )
    assert not u._download_retryable(RuntimeError("缺少 zipball_url"))

    assert u._parse_content_range("bytes 5-9/10") == (5, 9, 10)
    assert u._parse_content_range("bytes 0-0/*") == (0, 0, 1)
    assert u._parse_content_range("nope") is None

    headers = httpx.Headers({"Content-Length": "10"})
    assert u._expected_total_bytes(status=200, headers=headers, resume_from=0) == 10
    headers_206 = httpx.Headers(
        {"Content-Range": "bytes 5-9/10", "Content-Length": "5"}
    )
    assert u._expected_total_bytes(status=206, headers=headers_206, resume_from=5) == 10

    dest = tmp_path / "partial.bin"
    dest.write_bytes(b"abc")
    with pytest.raises(u.IncompleteDownload, match="应为 10"):
        u._check_download_size(dest, 10)
    dest.write_bytes(b"0123456789")
    u._check_download_size(dest, 10)

    msg = u._format_download_error(
        httpx.RemoteProtocolError(
            "peer closed connection without sending complete message body "
            "(received 6634923 bytes, expected 6889538)"
        )
    )
    assert "从 GitHub 下载被中断" in msg
    assert "一键更新" in msg
    assert u._format_download_error(RuntimeError(msg)) == msg
    forbidden = httpx.Response(403, request=httpx.Request("GET", "https://api.github.com/x"))
    assert "403" in u._format_download_error(
        httpx.HTTPStatusError("nope", request=forbidden.request, response=forbidden)
    )

    assert not u._download_send_range("https://api.github.com/repos/x/y/zipball/v1", 100)
    assert u._download_send_range("https://codeload.github.com/x/y/zip/refs/tags/v1", 100)
    assert not u._download_send_range("https://codeload.github.com/x/y/zip/v1", 0)


def _patch_download_client(
    monkeypatch: pytest.MonkeyPatch, handler
) -> None:
    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(*args: object, **kwargs: object):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(u.httpx, "AsyncClient", client_factory)

    async def no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(u.asyncio, "sleep", no_sleep)


def test_download_retries_truncated_body_then_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    dest = tmp_path / "file.bin"
    payload = b"abcdefghij"
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        if state["n"] == 1:
            raise httpx.RemoteProtocolError(
                "peer closed connection without sending complete message body "
                "(received 6634923 bytes, expected 6889538)"
            )
        return httpx.Response(
            200,
            content=payload,
            headers={"Content-Length": str(len(payload))},
        )

    _patch_download_client(monkeypatch, handler)
    import asyncio

    asyncio.run(u._download("https://example.com/file.bin", dest))
    assert dest.read_bytes() == payload
    assert state["n"] == 2


def test_download_resumes_partial_with_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    dest = tmp_path / "file.bin"
    dest.write_bytes(b"hello")
    seen: dict[str, str | None] = {"range": None}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["range"] = request.headers.get("range")
        if request.headers.get("range") == "bytes=5-":
            return httpx.Response(
                206,
                content=b"world",
                headers={
                    "Content-Range": "bytes 5-9/10",
                    "Content-Length": "5",
                },
            )
        return httpx.Response(
            200,
            content=b"helloworld",
            headers={"Content-Length": "10"},
        )

    _patch_download_client(monkeypatch, handler)
    import asyncio

    asyncio.run(u._download("https://example.com/file.bin", dest))
    assert dest.read_bytes() == b"helloworld"
    assert seen["range"] == "bytes=5-"


def test_download_404_does_not_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    dest = tmp_path / "file.bin"
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        return httpx.Response(404, content=b"missing")

    _patch_download_client(monkeypatch, handler)
    import asyncio

    with pytest.raises(RuntimeError):
        asyncio.run(u._download("https://example.com/file.bin", dest))
    assert state["n"] == 1


def test_download_exhausted_retries_use_chinese_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    dest = tmp_path / "file.bin"
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        raise httpx.RemoteProtocolError(
            "peer closed connection without sending complete message body"
        )

    _patch_download_client(monkeypatch, handler)
    monkeypatch.setattr(u, "_DOWNLOAD_ATTEMPTS", 3)
    import asyncio

    with pytest.raises(RuntimeError, match="一键更新"):
        asyncio.run(u._download("https://example.com/file.bin", dest))
    assert state["n"] == 3
