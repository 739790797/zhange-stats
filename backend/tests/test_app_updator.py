"""Unit tests for AstrBot-style app self-update helpers."""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import tarfile
import zipfile
from pathlib import Path

import httpx
import pytest

from app.services import app_updator as u


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _targz(entries: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, text in entries.items():
            data = text.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _source_targz(version: str, files: dict[str, str]) -> bytes:
    """Like ``git archive --prefix=zhange-stats-<ver>/``."""
    return _targz({f"zhange-stats-{version}/{rel}": text for rel, text in files.items()})


def _release(
    version: str,
    blobs: dict[str, bytes],
    *,
    digests: dict[str, str] | None = None,
    zipball: str = "",
    prerelease: bool = False,
) -> u.ReleaseInfo:
    assets = {
        name: u.ReleaseAsset(
            name=name,
            url=f"https://github.com/o/r/releases/download/v{version}/{name}",
            digest=(digests or {}).get(name, f"sha256:{_sha(blob)}"),
        )
        for name, blob in blobs.items()
    }
    static = assets.get(f"zhange-stats-{version}-static.tar.gz")
    return u.ReleaseInfo(
        tag_name=f"v{version}",
        name=f"v{version}",
        body="",
        published_at="",
        zipball_url=zipball,
        static_asset_url=static.url if static else None,
        static_asset_name=static.name if static else None,
        assets=assets,
        prerelease=prerelease,
    )


def _serve_release_downloads(
    monkeypatch: pytest.MonkeyPatch, blobs_by_url: dict[str, bytes]
) -> list[str]:
    fetched: list[str] = []

    async def fake_download(url: str, dest: Path, proxy: str | None = None) -> None:
        fetched.append(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blobs_by_url[url])

    monkeypatch.setattr(u, "_download", fake_download)
    return fetched


def _fake_settings(install: Path, **extra: object) -> object:
    values: dict[str, object] = {
        "DATA_DIR": str(install / "data"),
        "STATIC_DIR": str(install / "static"),
        "APP_INSTALL_DIR": str(install),
        "UPDATE_GITHUB_REPO": "o/r",
        "UPDATE_GITHUB_API": "https://api.github.com",
        "UPDATE_GITHUB_TOKEN": "",
        "APP_VERSION": "0.3.0",
    }
    values.update(extra)
    return type("S", (), values)()


def _make_install(tmp_path: Path) -> Path:
    install = tmp_path / "install"
    (install / "backend" / "app").mkdir(parents=True)
    (install / "backend" / "alembic").mkdir(parents=True)
    (install / "VERSION").write_text("0.3.0\n", encoding="utf-8")
    (install / "backend" / "app" / "x.py").write_text("old\n", encoding="utf-8")
    (install / "backend" / "requirements.txt").write_text("httpx\n", encoding="utf-8")
    venv_py = install / "backend" / ".venv" / "bin" / "python"
    venv_py.parent.mkdir(parents=True)
    venv_py.write_text("", encoding="utf-8")
    (install / "static").mkdir()
    (install / "static" / "index.html").write_text("old-ui", encoding="utf-8")
    (install / "data").mkdir()
    return install


def _new_release_031(*, extra_files: dict[str, str] | None = None) -> tuple[u.ReleaseInfo, dict[str, bytes]]:
    files = {
        "VERSION": "0.3.1\n",
        "backend/app/x.py": "new\n",
        "backend/requirements.txt": "httpx\n",
        "backend/constraints.txt": "httpx==0.28.1\n",
        "backend/alembic/.keep": "",
    }
    files.update(extra_files or {})
    source = _source_targz("0.3.1", files)
    static = _targz({"./index.html": "new-ui", "./assets/app.js": "js"})
    blobs = {
        "zhange-stats-0.3.1-source.tar.gz": source,
        "zhange-stats-0.3.1-static.tar.gz": static,
    }
    rel = _release("0.3.1", blobs)
    return rel, {rel.assets[name].url: blob for name, blob in blobs.items()}


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

    monkeypatch.setattr(u, "database_is_configured", lambda: True)
    monkeypatch.setattr(u.subprocess, "run", lambda *a, **k: FakeProc())
    with pytest.raises(RuntimeError, match="数据库迁移失败"):
        u.run_install_migrations(install)


def test_run_install_migrations_noop_before_database_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def no_subprocess(*_a, **_k):
        raise AssertionError("migrate subprocess must not run without a database")

    monkeypatch.setattr(u, "database_is_configured", lambda: False)
    monkeypatch.setattr(u.subprocess, "run", no_subprocess)
    u.run_install_migrations(tmp_path / "install")


def _run_core(install: Path, target: u.ReleaseInfo, *, reboot: bool = False) -> u.UpdateResult:
    return asyncio.run(
        u._apply_update_core(target=target, proxy=None, reboot=reboot, install_dir=install)
    )


def test_apply_update_core_rolls_back_when_migrate_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    install = _make_install(tmp_path)
    incoming_updator = '''
SOURCE_WHITELIST: tuple[str, ...] = (
    "VERSION",
    "backend/app",
    "docs/extra.md",
)
MERGE_TREES: tuple[str, ...] = ("frontend",)
'''
    target, blobs = _new_release_031(
        extra_files={
            "backend/app/services/app_updator.py": incoming_updator,
            "docs/extra.md": "new-doc\n",
        }
    )
    _serve_release_downloads(monkeypatch, blobs)
    monkeypatch.setattr(u, "pip_install_requirements", lambda *_a, **_k: None)
    monkeypatch.setattr(u, "get_settings", lambda: _fake_settings(install))

    def boom(_install: Path) -> None:
        # New code is on disk when migrate fails.
        assert (install / "VERSION").read_text(encoding="utf-8").strip() == "0.3.1"
        assert (install / "docs" / "extra.md").is_file()
        raise RuntimeError("数据库迁移失败，已中止重启以免服务挂死。详情: boom")

    monkeypatch.setattr(u, "run_install_migrations", boom)
    restarts: list[float] = []
    monkeypatch.setattr(u, "trigger_restart", lambda **kw: restarts.append(kw.get("delay_sec", 0)))

    result = _run_core(install, target, reboot=True)
    assert result.ok is False
    assert "回滚" in result.message
    assert restarts == []
    assert (install / "VERSION").read_text(encoding="utf-8").strip() == "0.3.0"
    assert (install / "backend" / "app" / "x.py").read_text(encoding="utf-8") == "old\n"
    # Paths added only by the incoming whitelist are removed again.
    assert not (install / "docs" / "extra.md").exists()
    assert (install / "static" / "index.html").read_text(encoding="utf-8") == "old-ui"
    assert not (install / "static.new").exists()
    assert not (install / "backend" / ".venv" / u.PIP_STAMP_NAME).exists()


def test_apply_update_core_pip_failure_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    install = _make_install(tmp_path)
    target, blobs = _new_release_031()
    _serve_release_downloads(monkeypatch, blobs)
    monkeypatch.setattr(u, "get_settings", lambda: _fake_settings(install))
    seen: dict[str, Path] = {}

    def failing_pip(_install: Path, source_backend: Path | None = None) -> None:
        assert source_backend is not None
        seen["req"] = source_backend / "requirements.txt"
        assert (source_backend / "constraints.txt").read_text(encoding="utf-8") == "httpx==0.28.1\n"
        raise RuntimeError("pip 安装失败（exit=1）。PyPI down")

    def no_migrate(_install: Path) -> None:
        raise AssertionError("must not migrate after pip failure")

    monkeypatch.setattr(u, "pip_install_requirements", failing_pip)
    monkeypatch.setattr(u, "run_install_migrations", no_migrate)

    with pytest.raises(RuntimeError, match="代码未改动"):
        _run_core(install, target)
    assert seen["req"].read_text(encoding="utf-8") == "httpx\n"
    assert (install / "VERSION").read_text(encoding="utf-8").strip() == "0.3.0"
    assert (install / "backend" / "app" / "x.py").read_text(encoding="utf-8") == "old\n"
    assert (install / "static" / "index.html").read_text(encoding="utf-8") == "old-ui"
    assert not (install / "static.new").exists()


def test_apply_update_core_refuses_checksum_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    install = _make_install(tmp_path)
    target, blobs = _new_release_031()
    static_name = "zhange-stats-0.3.1-static.tar.gz"
    blobs[target.assets[static_name].url] = b"tampered"
    fetched = _serve_release_downloads(monkeypatch, blobs)
    monkeypatch.setattr(u, "get_settings", lambda: _fake_settings(install))
    monkeypatch.setattr(
        u, "pip_install_requirements", lambda *_a, **_k: pytest.fail("pip must not run")
    )

    with pytest.raises(u.ChecksumMismatch, match="sha256"):
        _run_core(install, target)
    # One fresh re-download before giving up.
    assert fetched.count(target.assets[static_name].url) == 2
    assert (install / "VERSION").read_text(encoding="utf-8").strip() == "0.3.0"
    assert (install / "static" / "index.html").read_text(encoding="utf-8") == "old-ui"


def test_apply_update_core_success_swaps_static_and_writes_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    install = _make_install(tmp_path)
    target, blobs = _new_release_031()
    _serve_release_downloads(monkeypatch, blobs)
    monkeypatch.setattr(u, "get_settings", lambda: _fake_settings(install))
    pip_calls: list[Path | None] = []
    monkeypatch.setattr(
        u,
        "pip_install_requirements",
        lambda _install, source_backend=None: pip_calls.append(source_backend),
    )

    def migrate(_install: Path) -> None:
        # Live static is swapped only after migrations succeed.
        assert (install / "static" / "index.html").read_text(encoding="utf-8") == "old-ui"
        assert (install / "static.new" / "index.html").is_file()

    monkeypatch.setattr(u, "run_install_migrations", migrate)

    result = _run_core(install, target)
    assert result.ok is True, result.message
    assert len(pip_calls) == 1
    assert (install / "VERSION").read_text(encoding="utf-8").strip() == "0.3.1"
    assert (install / "backend" / "constraints.txt").is_file()
    assert (install / "static" / "index.html").read_text(encoding="utf-8") == "new-ui"
    assert (install / "static" / "assets" / "app.js").is_file()
    assert (install / "static.prev" / "index.html").read_text(encoding="utf-8") == "old-ui"
    assert not (install / "static.new").exists()
    stamp = (install / "backend" / ".venv" / u.PIP_STAMP_NAME).read_text(encoding="utf-8")
    assert stamp == u.requirements_stamp(install / "backend")


def test_apply_update_core_skips_pip_when_stamp_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    install = _make_install(tmp_path)
    target, blobs = _new_release_031()
    _serve_release_downloads(monkeypatch, blobs)
    monkeypatch.setattr(u, "get_settings", lambda: _fake_settings(install))
    staged = tmp_path / "same-reqs"
    staged.mkdir()
    (staged / "requirements.txt").write_text("httpx\n", encoding="utf-8")
    (staged / "constraints.txt").write_text("httpx==0.28.1\n", encoding="utf-8")
    (install / "backend" / ".venv" / u.PIP_STAMP_NAME).write_text(
        u.requirements_stamp(staged).replace("\n", "\r\n"), encoding="utf-8"
    )
    monkeypatch.setattr(
        u, "pip_install_requirements", lambda *_a, **_k: pytest.fail("pip must be skipped")
    )
    monkeypatch.setattr(u, "run_install_migrations", lambda _install: None)

    result = _run_core(install, target)
    assert result.ok is True, result.message
    assert (install / "VERSION").read_text(encoding="utf-8").strip() == "0.3.1"


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


def test_fetch_releases_direct_first_then_proxy_without_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    monkeypatch.setattr(u, "get_settings", lambda: _fake_settings(tmp_path))
    monkeypatch.setattr(u, "_github_token", lambda: "ghp-secret")
    seen: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.host, request.headers.get("authorization")))
        if request.url.host == "api.github.com":
            raise httpx.ConnectError("blocked", request=request)
        return httpx.Response(200, json=[{"tag_name": "v1.0.0", "assets": []}])

    _patch_download_client(monkeypatch, handler)
    caplog.set_level(logging.WARNING, logger=u.logger.name)
    releases = asyncio.run(u.fetch_releases(proxy="https://ghproxy.example"))
    assert [r.tag_name for r in releases] == ["v1.0.0"]
    assert seen == [("api.github.com", "Bearer ghp-secret"), ("ghproxy.example", None)]
    assert "proxy" in caplog.text
    assert "ghp-secret" not in caplog.text


def test_fetch_releases_direct_success_never_touches_proxy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(u, "get_settings", lambda: _fake_settings(tmp_path))
    monkeypatch.setattr(u, "_github_token", lambda: "")
    hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        return httpx.Response(
            200,
            json=[
                {"tag_name": "v1.1.0", "draft": True, "assets": []},
                {"tag_name": "v1.0.0", "assets": []},
            ],
        )

    _patch_download_client(monkeypatch, handler)
    releases = asyncio.run(u.fetch_releases(proxy="https://ghproxy.example"))
    assert hosts == ["api.github.com"]
    assert [r.tag_name for r in releases] == ["v1.0.0"]


def test_fetch_release_by_tag_404_does_not_fall_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(u, "get_settings", lambda: _fake_settings(tmp_path))
    monkeypatch.setattr(u, "_github_token", lambda: "")
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(404, json={"message": "Not Found"})

    _patch_download_client(monkeypatch, handler)
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(u.fetch_release_by_tag("0.9.0", proxy="https://ghproxy.example"))
    assert urls == ["https://api.github.com/repos/o/r/releases/tags/v0.9.0"]


def test_token_only_for_github_hosts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        u,
        "get_settings",
        lambda: _fake_settings(tmp_path, UPDATE_GITHUB_API="https://ghe.example.com/api/v3"),
    )
    assert u._token_allowed("https://api.github.com/repos/o/r/releases")
    assert u._token_allowed("https://ghe.example.com/api/v3/repos/o/r/releases")
    assert not u._token_allowed("https://ghproxy.example/https://api.github.com/repos/o/r")
    assert not u._token_allowed("https://objects.githubusercontent.com/x")


def test_parse_release_uses_exact_static_asset_name():
    digest = "sha256:" + "a" * 64
    lookalike = u._parse_release(
        {
            "tag_name": "v1.2.3",
            "assets": [
                {
                    "name": "evil-static.tar.gz",
                    "browser_download_url": "https://github.com/o/r/releases/download/v1.2.3/evil-static.tar.gz",
                    "digest": digest,
                }
            ],
        }
    )
    assert lookalike.static_asset_url is None
    exact = u._parse_release(
        {
            "tag_name": "v1.2.3",
            "prerelease": True,
            "assets": [
                {
                    "name": "zhange-stats-1.2.3-static.tar.gz",
                    "browser_download_url": "https://github.com/o/r/releases/download/v1.2.3/s.tgz",
                    "digest": digest,
                }
            ],
        }
    )
    assert exact.static_asset_name == "zhange-stats-1.2.3-static.tar.gz"
    assert exact.assets["zhange-stats-1.2.3-static.tar.gz"].digest == digest
    assert exact.prerelease is True


def test_latest_is_highest_semver_stable_release(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def rel(tag: str, **kw: bool) -> u.ReleaseInfo:
        return u.ReleaseInfo(tag_name=tag, name=tag, body="", published_at="", zipball_url="", **kw)

    releases = [rel("v0.2.9"), rel("v0.2.11", prerelease=True), rel("v0.2.10"), rel("v0.2.8")]
    newest = u.latest_stable_release(releases)
    assert newest is not None and newest.tag_name == "v0.2.10"
    resolved = u._resolve_target_release(releases, "latest", "0.2.9")
    assert isinstance(resolved, u.ReleaseInfo) and resolved.tag_name == "v0.2.10"
    only_pre = u._resolve_target_release([rel("v1.0.0", prerelease=True)], "latest", "0.1.0")
    assert isinstance(only_pre, u.UpdateResult) and only_pre.ok is False

    async def fake_fetch(**_kw: object) -> list[u.ReleaseInfo]:
        return releases

    monkeypatch.setattr(u, "fetch_releases", fake_fetch)
    monkeypatch.setattr(u, "get_settings", lambda: _fake_settings(tmp_path, APP_VERSION="0.2.8"))
    try:
        latest, _ = asyncio.run(u.check_update(force=True))
        assert latest is not None and latest.tag_name == "v0.2.10"
    finally:
        u.invalidate_check_cache()


def test_parse_sha256sums_and_cross_check():
    a, b = "a" * 64, "b" * 64
    static, source = "zhange-stats-1.0.0-static.tar.gz", "zhange-stats-1.0.0-source.tar.gz"
    sums = u.parse_sha256sums(f"{a}  {static}\n{b} *{source}\nnot a checksum line\n")
    assert sums == {static: a, source: b}
    rel = _release("1.0.0", {static: b"x"}, digests={static: f"sha256:{a.upper()}"})
    assert u.expected_sha256(rel, static, sums) == a
    assert u.expected_sha256(rel, source, sums) == b
    with pytest.raises(u.ChecksumMismatch):
        u.expected_sha256(rel, static, {static: b})


def test_download_release_files_verifies_sha256sums_and_prefers_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    target, blobs = _new_release_031()
    sums_text = "".join(
        f"{_sha(blobs[asset.url])}  {name}\n" for name, asset in target.assets.items()
    ).encode()
    sums_asset = u.ReleaseAsset(
        name=u.SHA256SUMS_NAME,
        url="https://github.com/o/r/releases/download/v0.3.1/SHA256SUMS",
        digest=f"sha256:{_sha(sums_text)}",
    )
    target.assets[u.SHA256SUMS_NAME] = sums_asset
    blobs[sums_asset.url] = sums_text
    fetched = _serve_release_downloads(monkeypatch, blobs)

    source, static = asyncio.run(u.download_release_files(target, tmp_path / "work", proxy=None))
    assert source is not None and source.name == "zhange-stats-0.3.1-source.tar.gz"
    assert static.read_bytes() == blobs[target.assets["zhange-stats-0.3.1-static.tar.gz"].url]
    assert fetched[0] == sums_asset.url
    assert len(fetched) == 3


def test_download_release_files_zipball_fallback_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    static = _targz({"index.html": "ui"})
    target = _release(
        "0.3.1",
        {"zhange-stats-0.3.1-static.tar.gz": static},
        zipball="https://api.github.com/repos/o/r/zipball/v0.3.1",
    )
    assert target.static_asset_url
    _serve_release_downloads(
        monkeypatch, {target.static_asset_url: static, target.zipball_url: b"PK"}
    )
    caplog.set_level(logging.WARNING, logger=u.logger.name)
    source, _ = asyncio.run(u.download_release_files(target, tmp_path / "work", proxy=None))
    assert source is not None and source.name == "source.zip"
    assert "zipball" in caplog.text


def test_download_release_files_refuses_missing_static_or_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    no_static = _release("0.3.1", {"other-static.tar.gz": b"x"}, zipball="https://example.com/z")
    _serve_release_downloads(monkeypatch, {})
    with pytest.raises(RuntimeError, match="缺少前端资产"):
        asyncio.run(u.download_release_files(no_static, tmp_path / "w1", proxy=None))

    name = "zhange-stats-0.3.1-static.tar.gz"
    no_digest = _release("0.3.1", {name: b"x"}, digests={name: ""})
    assert no_digest.static_asset_url
    _serve_release_downloads(monkeypatch, {no_digest.static_asset_url: b"x"})
    with pytest.raises(u.ChecksumMismatch, match="缺少 sha256"):
        asyncio.run(u.download_release_files(no_digest, tmp_path / "w2", proxy=None))


def test_extract_source_archive_tar_and_zip(tmp_path: Path):
    tar_path = tmp_path / "src.tar.gz"
    tar_path.write_bytes(_source_targz("1.0.0", {"VERSION": "1.0.0\n", "backend/app/a.py": "a\n"}))
    root = u.extract_source_archive(tar_path, tmp_path / "out-tar")
    assert root.name == "zhange-stats-1.0.0"
    assert (root / "backend" / "app" / "a.py").read_text(encoding="utf-8") == "a\n"

    zip_path = tmp_path / "src.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("o-r-abc123/VERSION", "1.0.0\n")
    root = u.extract_source_archive(zip_path, tmp_path / "out-zip")
    assert (root / "VERSION").read_text(encoding="utf-8") == "1.0.0\n"


@pytest.mark.parametrize("with_data_filter", [True, False])
def test_extract_tar_rejects_path_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, with_data_filter: bool
):
    if with_data_filter and not hasattr(tarfile, "data_filter"):
        pytest.skip("tarfile.data_filter unavailable on this Python")
    if not with_data_filter:
        monkeypatch.delattr(u.tarfile, "data_filter", raising=False)
    bad = tmp_path / "bad.tar.gz"
    bad.write_bytes(_targz({"../escape.txt": "x"}))
    with pytest.raises((RuntimeError, tarfile.TarError)):
        u.extract_source_archive(bad, tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()


def test_apply_static_tar_keeps_previous_tree(tmp_path: Path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("v1", encoding="utf-8")
    stale_prev = tmp_path / "static.prev"
    stale_prev.mkdir()
    (stale_prev / "stale.txt").write_text("x", encoding="utf-8")
    tar_path = tmp_path / "s.tar.gz"
    tar_path.write_bytes(_targz({"index.html": "v2"}))

    u.apply_static_tar(tar_path, static)
    assert (static / "index.html").read_text(encoding="utf-8") == "v2"
    assert (stale_prev / "index.html").read_text(encoding="utf-8") == "v1"
    assert not (stale_prev / "stale.txt").exists()
    assert not (tmp_path / "static.new").exists()


def test_stage_static_requires_index_html(tmp_path: Path):
    tar_path = tmp_path / "s.tar.gz"
    tar_path.write_bytes(_targz({"assets/app.js": "js"}))
    with pytest.raises(RuntimeError, match="index.html"):
        u.stage_static_tar(tar_path, tmp_path / "static.new")
    assert not (tmp_path / "static.new").exists()


def test_requirements_stamp_matches_sha256sum_output(tmp_path: Path):
    backend = tmp_path / "backend"
    backend.mkdir()
    req, lock = b"httpx\n", b"httpx==0.28.1\n"
    (backend / "requirements.txt").write_bytes(req)
    assert u.requirements_stamp(backend) == f"{_sha(req)}  requirements.txt\n"
    (backend / "constraints.txt").write_bytes(lock)
    expected = f"{_sha(req)}  requirements.txt\n{_sha(lock)}  constraints.txt\n"
    assert u.requirements_stamp(backend) == expected

    import shutil
    import subprocess

    if shutil.which("sha256sum"):
        out = subprocess.run(
            ["sha256sum", *u.PIP_STAMP_FILES],
            cwd=backend,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert out == expected


def test_pip_install_requirements_uses_staged_constraints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    install = tmp_path / "install"
    venv_py = install / "backend" / ".venv" / "bin" / "python"
    venv_py.parent.mkdir(parents=True)
    venv_py.write_text("", encoding="utf-8")
    staged = tmp_path / "staged-backend"
    staged.mkdir()
    (staged / "requirements.txt").write_text("easyocr>=1.7.2\n", encoding="utf-8")
    (staged / "constraints.txt").write_text("easyocr==1.7.2\n", encoding="utf-8")
    calls: list[list[str]] = []

    class FakePopen:
        def __init__(self, cmd, **_kwargs):
            calls.append(list(cmd))
            self.stdout = io.StringIO("ok\n")

        def wait(self) -> int:
            return 0

    class FakeProc:
        returncode = 0
        stdout = "torch==2.8.0+cpu\n"
        stderr = ""

    def fake_run(cmd, **_kwargs):
        calls.append(list(cmd))
        return FakeProc()

    monkeypatch.setattr(u.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(u.subprocess, "run", fake_run)
    u.pip_install_requirements(install, staged)

    lock = str(staged / "constraints.txt")
    torch_cmd = next(c for c in calls if u.TORCH_CPU_INDEX in c)
    assert "-c" not in torch_cmd
    req_cmd = next(c for c in calls if "-r" in c)
    assert req_cmd[req_cmd.index("-r") + 1] == str(staged / "requirements.txt")
    assert lock in req_cmd
    opencv_cmd = next(c for c in calls if "opencv-python-headless>=4.8.0" in c)
    assert lock in opencv_cmd


def test_enqueue_update_keeps_background_task_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    install = _make_install(tmp_path)
    monkeypatch.setattr(u, "update_allowed", lambda **_kw: (True, ""))
    monkeypatch.setattr(u, "resolve_install_dir", lambda: install)
    monkeypatch.setattr(u, "get_settings", lambda: _fake_settings(install))
    target = _release("0.3.1", {})

    async def fake_fetch(**_kw: object) -> list[u.ReleaseInfo]:
        return [target]

    monkeypatch.setattr(u, "fetch_releases", fake_fetch)

    async def scenario() -> None:
        gate = asyncio.Event()

        async def fake_core(**_kw: object) -> u.UpdateResult:
            await gate.wait()
            return u.UpdateResult(ok=True, message="ok")

        monkeypatch.setattr(u, "_apply_update_core", fake_core)
        result = await u.enqueue_update(version="latest", reboot=False)
        assert result.ok, result.message
        assert len(u._background_tasks) == 1
        gate.set()
        await asyncio.gather(*list(u._background_tasks))
        await asyncio.sleep(0)
        assert not u._background_tasks

    try:
        asyncio.run(scenario())
        assert u._lock.acquire(blocking=False)
        u._lock.release()
    finally:
        u._set_progress(busy=False, phase="", message="", error="", target_version="")


def test_install_static_only_verifies_and_installs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    install = _make_install(tmp_path)
    (install / "VERSION").write_text("0.3.1\n", encoding="utf-8")
    (install / "static" / "index.html").unlink()
    target, blobs = _new_release_031()
    monkeypatch.setattr(u, "resolve_install_dir", lambda: install)
    monkeypatch.setattr(u, "get_settings", lambda: _fake_settings(install, STATIC_DIR=""))
    asked: list[str] = []

    async def fake_by_tag(version: str, proxy: str | None = None) -> u.ReleaseInfo:
        asked.append(version)
        return target

    monkeypatch.setattr(u, "fetch_release_by_tag", fake_by_tag)
    fetched = _serve_release_downloads(monkeypatch, blobs)

    result = asyncio.run(u.install_static_only())
    assert result.ok, result.message
    assert asked == ["0.3.1"]
    assert fetched == [target.static_asset_url]
    assert (install / "static" / "index.html").read_text(encoding="utf-8") == "new-ui"
    assert (install / "backend" / "app" / "x.py").read_text(encoding="utf-8") == "old\n"


def test_install_static_only_failure_lists_alternatives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    install = _make_install(tmp_path)
    monkeypatch.setattr(u, "resolve_install_dir", lambda: install)
    monkeypatch.setattr(u, "get_settings", lambda: _fake_settings(install))

    async def missing(version: str, proxy: str | None = None) -> u.ReleaseInfo:
        resp = httpx.Response(404, request=httpx.Request("GET", "https://api.github.com/x"))
        raise httpx.HTTPStatusError("nope", request=resp.request, response=resp)

    monkeypatch.setattr(u, "fetch_release_by_tag", missing)
    result = asyncio.run(u.install_static_only())
    assert result.ok is False
    assert "v0.3.0" in result.message
    assert "npm run build" in result.message
    assert (install / "static" / "index.html").read_text(encoding="utf-8") == "old-ui"


def test_host_update_main_static_only(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict[str, object]] = []

    async def fake_static(**kwargs: object) -> u.UpdateResult:
        calls.append(kwargs)
        return u.UpdateResult(ok=True, message="已安装前端 static")

    monkeypatch.setattr(u, "install_static_only", fake_static)
    assert u.host_update_main(["--static-only"]) == 0
    assert calls == [{"proxy": None}]
    assert u.host_update_main(["--static-only", "--version", "v1.0.0"]) == 1
    assert len(calls) == 1
