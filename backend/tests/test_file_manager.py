"""Site file manager: catalog sizes, path jail, sensitive download."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.services import file_manager as fm


def _ctx(tmp_path: Path, **overrides: object) -> fm.FileManagerContext:
    install = tmp_path / "zhange-stats"
    install.mkdir()
    (install / "VERSION").write_text("0.0.0\n", encoding="utf-8")
    (install / "backend").mkdir()
    var_dir = install / "var"
    data = var_dir / "data"
    uploads = var_dir / "uploads"
    data.mkdir(parents=True)
    uploads.mkdir(parents=True)
    kwargs = {
        "install_dir": install,
        "data_dir": data,
        "upload_dir": uploads,
        "var_dir": var_dir,
        "venv_dir": install / "backend" / ".venv",
        "node_modules_dir": install / "frontend" / "node_modules",
        "static_dir": None,
        "backup_dir": None,
        "extra": (),
    }
    kwargs.update(overrides)
    return fm.FileManagerContext(**kwargs)  # type: ignore[arg-type]


def test_normalize_rel_rejects_parent() -> None:
    with pytest.raises(fm.FileManagerError):
        fm.normalize_rel("../secret")
    with pytest.raises(fm.FileManagerError):
        fm.normalize_rel("a/../../b")
    assert fm.normalize_rel("/foo/bar") == "foo/bar"
    assert fm.normalize_rel("foo\\bar") == "foo/bar"
    assert fm.normalize_rel("\\\\foo\\\\bar") == "foo/bar"
    assert fm.normalize_rel("//foo/bar") == "foo/bar"


def test_resolve_in_root_accepts_backslash_and_slash(tmp_path: Path) -> None:
    root = tmp_path / "root"
    nested = root / "a" / "b"
    nested.mkdir(parents=True)
    (nested / "f.txt").write_text("ok", encoding="utf-8")
    via_slash = fm.resolve_in_root(root, "a/b/f.txt")
    via_backslash = fm.resolve_in_root(root, "a\\b\\f.txt")
    assert via_slash.name == "f.txt"
    assert fm.same_path(via_slash, via_backslash)
    mixed = Path(str(nested).replace("\\", "/"))
    assert fm.is_under(mixed, root)
    assert fm.rel_posix(nested, root) == "a/b"


def test_reject_windows_drive_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    if os.name != "nt":
        pytest.skip("Windows drive jail")
    with pytest.raises(fm.FileManagerError):
        fm.resolve_in_root(root, r"C:\Windows")
    with pytest.raises(fm.FileManagerError):
        fm.resolve_in_root(root, "C:/Windows")


def test_backup_dir_defaults_to_install_var_backups(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZHANGE_BACKUP_DIR", raising=False)
    assert fm._backup_dir(tmp_path) == tmp_path / "var" / "backups"
    monkeypatch.setenv("ZHANGE_BACKUP_DIR", str(tmp_path / "custom"))
    assert fm._backup_dir(tmp_path) == tmp_path / "custom"


def test_resolve_in_root_blocks_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "outside.txt").write_text("nope", encoding="utf-8")
    with pytest.raises(fm.FileManagerError):
        fm.resolve_in_root(root, "../outside.txt")


def test_is_sensitive_name() -> None:
    assert fm.is_sensitive_name(".secret_key")
    assert fm.is_sensitive_name(".env")
    assert fm.is_sensitive_name(".env.local")
    assert fm.is_sensitive_name(".git")
    assert fm.is_sensitive_name("tls.pem")
    assert not fm.is_sensitive_name(".env.example")
    assert not fm.is_sensitive_name(".gitignore")
    assert not fm.is_sensitive_name("app.jsonl")
    assert not fm.is_sensitive_name("det.onnx")
    assert fm.rel_is_sensitive(".git/config")
    assert not fm.rel_is_sensitive("docs/README.md")
    assert fm.rel_is_sensitive("var/mariadb/provision.json")
    assert fm.rel_is_sensitive("var/mariadb/data")
    assert fm.rel_is_sensitive("var/mariadb/data/ibdata1")
    assert not fm.rel_is_sensitive("var/mariadb/my.ini")
    assert not fm.rel_is_sensitive("var/mariadb/dist/bin/mysqld.exe")
    assert fm.rel_is_sensitive("var/backups/zhange-20260101-000000.tar.gz")
    assert fm.rel_is_sensitive("zhange.sql")
    assert not fm.rel_is_sensitive("var/backups")


def test_leftover_excludes_classified_children(tmp_path: Path) -> None:
    fm.clear_size_cache()
    ctx = _ctx(tmp_path)
    rapid = ctx.data_dir / "rapidocr"
    rapid.mkdir()
    (rapid / "det.onnx").write_bytes(b"x" * 20)
    (ctx.data_dir / "notes.txt").write_bytes(b"abc")
    (ctx.upload_dir / "avatars").mkdir()
    (ctx.upload_dir / "avatars" / "1.jpg").write_bytes(b"y" * 8)
    (ctx.var_dir / "cache").mkdir()
    (ctx.var_dir / "cache" / "vite.bin").write_bytes(b"z" * 4)

    summary = fm.build_summary(ctx)
    by_id = {row.id: row for row in summary.buckets}
    assert by_id["ocr_rapidocr"].size_bytes == 20
    assert by_id["ocr_rapidocr"].kind == "download"
    assert by_id["uploads_avatars"].size_bytes == 8
    assert by_id["uploads_avatars"].kind == "generated"
    assert by_id["runtime_cache"].size_bytes == 4
    assert by_id["runtime_cache"].kind == "cache"
    assert by_id["data_leftover"].size_bytes == 3
    assert "ocr_rapidocr" not in (by_id["data_leftover"].path,)

    kinds = {row.kind: row.size_bytes for row in summary.kind_totals}
    assert kinds["download"] >= 20
    assert kinds["generated"] >= 8 + 3
    assert kinds["cache"] >= 4

    ocr = next(row for row in summary.business_totals if row.business == "ocr")
    assert ocr.size_bytes == 20


def test_browse_and_sensitive_download(tmp_path: Path) -> None:
    fm.clear_size_cache()
    ctx = _ctx(tmp_path)
    (ctx.data_dir / ".secret_key").write_text("secret\n", encoding="utf-8")
    (ctx.data_dir / "ok.log").write_text("hello\n", encoding="utf-8")
    listing = fm.list_directory("install", "var/data", ctx=ctx)
    names = {row.name: row for row in listing.entries}
    assert names[".secret_key"].sensitive is True
    assert names[".secret_key"].downloadable is False
    assert names["ok.log"].downloadable is True

    got = fm.resolve_download("install", "var/data/ok.log", ctx=ctx)
    assert got.name == "ok.log"
    with pytest.raises(fm.FileManagerError) as blocked:
        fm.resolve_download("install", "var/data/.secret_key", ctx=ctx)
    assert blocked.value.status_code == 403


def test_browse_install_root_greys_secrets(tmp_path: Path) -> None:
    fm.clear_size_cache()
    ctx = _ctx(tmp_path)
    (ctx.install_dir / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (ctx.install_dir / ".env.example").write_text("SECRET=\n", encoding="utf-8")
    git = ctx.install_dir / ".git"
    git.mkdir()
    (git / "config").write_text("x\n", encoding="utf-8")
    listing = fm.list_directory("install", "", ctx=ctx)
    names = {row.name: row for row in listing.entries}
    assert names["backend"].is_dir is True
    assert names["backend"].sensitive is False
    assert names["VERSION"].sensitive is False
    assert names[".env"].sensitive is True
    assert names[".env"].downloadable is False
    assert names[".env.example"].sensitive is False
    assert names[".env.example"].downloadable is True
    assert names[".git"].sensitive is True
    assert names[".git"].is_dir is True
    with pytest.raises(fm.FileManagerError) as hidden:
        fm.list_directory("install", ".git", ctx=ctx)
    assert hidden.value.status_code == 403
    with pytest.raises(fm.FileManagerError) as blocked:
        fm.resolve_download("install", ".git/config", ctx=ctx)
    assert blocked.value.status_code == 403


def test_browse_root_prefers_install_for_nested_var(tmp_path: Path) -> None:
    fm.clear_size_cache()
    ctx = _ctx(tmp_path)
    (ctx.data_dir / "rapidocr").mkdir()
    (ctx.data_dir / "rapidocr" / "a.bin").write_bytes(b"12")
    summary = fm.build_summary(ctx)
    root_ids = {row.id for row in summary.roots}
    assert "install" in root_ids
    assert "var" not in root_ids
    rapid = next(row for row in summary.buckets if row.id == "ocr_rapidocr")
    assert rapid.browse_root_id == "install"
    assert rapid.browse_path.replace("\\", "/") == "var/data/rapidocr"


def test_optional_missing_buckets_omitted(tmp_path: Path) -> None:
    fm.clear_size_cache()
    ctx = _ctx(tmp_path)
    summary = fm.build_summary(ctx)
    ids = {row.id for row in summary.buckets}
    assert "python_venv" not in ids
    assert "runtime_mariadb" not in ids
    assert "ocr_rapidocr" in ids


def test_mariadb_bucket_and_sensitive_browse(tmp_path: Path) -> None:
    fm.clear_size_cache()
    ctx = _ctx(tmp_path)
    mdb = ctx.var_dir / "mariadb"
    (mdb / "data").mkdir(parents=True)
    (mdb / "dist" / "bin").mkdir(parents=True)
    (mdb / "provision.json").write_text("{}\n", encoding="utf-8")
    (mdb / "data" / "ibdata1").write_bytes(b"x" * 12)
    (mdb / "dist" / "bin" / "mysqld.exe").write_bytes(b"mz")
    (mdb / "my.ini").write_text("[mysqld]\n", encoding="utf-8")

    summary = fm.build_summary(ctx)
    by_id = {row.id: row for row in summary.buckets}
    assert by_id["runtime_mariadb"].size_bytes >= 12
    assert by_id["runtime_mariadb"].kind == "dependency"

    listing = fm.list_directory("install", "var/mariadb", ctx=ctx)
    names = {row.name: row for row in listing.entries}
    assert names["provision.json"].sensitive is True
    assert names["provision.json"].downloadable is False
    assert names["data"].sensitive is True
    assert names["my.ini"].sensitive is False
    assert names["dist"].sensitive is False

    with pytest.raises(fm.FileManagerError) as hidden:
        fm.list_directory("install", "var/mariadb/data", ctx=ctx)
    assert hidden.value.status_code == 403
    with pytest.raises(fm.FileManagerError) as blocked:
        fm.resolve_download("install", "var/mariadb/provision.json", ctx=ctx)
    assert blocked.value.status_code == 403
    got = fm.resolve_download("install", "var/mariadb/my.ini", ctx=ctx)
    assert got.name == "my.ini"


def test_openapi_files_admin_only() -> None:
    from app.main import app

    schema = app.openapi()
    paths = schema.get("paths") or {}
    summary = paths.get("/api/settings/files/summary") or {}
    browse = paths.get("/api/settings/files/browse") or {}
    download = paths.get("/api/settings/files/download") or {}
    assert summary.get("get") is not None
    assert browse.get("get") is not None
    assert download.get("get") is not None
    components = (schema.get("components") or {}).get("schemas") or {}
    assert "FileSummaryOut" in components
    assert "FileBrowseOut" in components
