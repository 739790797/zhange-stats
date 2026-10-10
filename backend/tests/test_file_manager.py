"""Site file manager: catalog sizes, path jail, sensitive download."""

from __future__ import annotations

import io
import os
import stat
import threading
from pathlib import Path

import pytest

from app.services import file_manager as fm


def _ctx(tmp_path: Path, **overrides: object) -> fm.FileManagerContext:
    install = tmp_path / "zhange-stats"
    install.mkdir()
    (install / "VERSION").write_text("0.0.0\n", encoding="utf-8")
    (install / "backend").mkdir()
    data_root = install / "data"
    data = data_root / "runtime"
    uploads = data_root / "uploads"
    models = data_root / "models"
    data.mkdir(parents=True)
    uploads.mkdir(parents=True)
    models.mkdir(parents=True)
    kwargs = {
        "install_dir": install,
        "data_dir": data,
        "upload_dir": uploads,
        "data_root": data_root,
        "models_dir": models,
        "venv_dir": install / "backend" / ".venv",
        "node_modules_dir": install / "frontend" / "node_modules",
        "static_dir": None,
        "backup_dir": None,
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


def test_backup_dir_defaults_to_install_data_backups(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZHANGE_BACKUP_DIR", raising=False)
    assert fm._backup_dir(tmp_path) == tmp_path / "data" / "backups"
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
    assert not fm.is_sensitive_name(".git")
    assert not fm.is_sensitive_name("config")
    assert fm.is_sensitive_name("tls.pem")
    assert not fm.is_sensitive_name(".env.example")
    assert not fm.is_sensitive_name(".gitignore")
    assert not fm.is_sensitive_name("app.jsonl")
    assert not fm.is_sensitive_name("det.onnx")
    assert not fm.rel_is_sensitive(".git/config")
    assert not fm.rel_is_sensitive("config/app.json")
    assert not fm.rel_is_sensitive("docs/README.md")
    assert fm.rel_is_sensitive("data/mariadb/provision.json")
    assert fm.rel_is_sensitive("data/mariadb/data")
    assert fm.rel_is_sensitive("data/mariadb/data/ibdata1")
    assert not fm.rel_is_sensitive("data/mariadb/my.ini")
    assert not fm.rel_is_sensitive("data/mariadb/dist/bin/mysqld.exe")
    assert fm.rel_is_sensitive("var/mariadb/provision.json")
    assert fm.rel_is_sensitive("data/backups/zhange-20260101-000000.tar.gz")
    assert fm.rel_is_sensitive("var/backups/zhange-20260101-000000.tar.gz")
    assert fm.rel_is_sensitive("zhange.sql")
    assert not fm.rel_is_sensitive("config.example/app.json")
    assert not fm.rel_is_sensitive("scripts/config.example/app.json")


def test_leftover_excludes_classified_children(tmp_path: Path) -> None:
    fm.clear_size_cache()
    ctx = _ctx(tmp_path)
    rapid = ctx.models_dir / "rapidocr"
    rapid.mkdir()
    (rapid / "det.onnx").write_bytes(b"x" * 20)
    (ctx.data_dir / "notes.txt").write_bytes(b"abc")
    (ctx.upload_dir / "avatars").mkdir()
    (ctx.upload_dir / "avatars" / "1.jpg").write_bytes(b"y" * 8)
    (ctx.data_root / "cache").mkdir()
    (ctx.data_root / "cache" / "vite.bin").write_bytes(b"z" * 4)

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
    listing = fm.list_directory("install", "data/runtime", ctx=ctx)
    names = {row.name: row for row in listing.entries}
    assert names[".secret_key"].sensitive is True
    assert names[".secret_key"].downloadable is False
    assert names["ok.log"].downloadable is True

    got = fm.resolve_download("install", "data/runtime/ok.log", ctx=ctx)
    assert got.name == "ok.log"
    with pytest.raises(fm.FileManagerError) as blocked:
        fm.resolve_download("install", "data/runtime/.secret_key", ctx=ctx)
    assert blocked.value.status_code == 403


def test_browse_install_root_greys_secrets(tmp_path: Path) -> None:
    fm.clear_size_cache()
    ctx = _ctx(tmp_path)
    (ctx.install_dir / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (ctx.install_dir / ".env.example").write_text("SECRET=\n", encoding="utf-8")
    git = ctx.install_dir / ".git"
    git.mkdir()
    (git / "config").write_text("x\n", encoding="utf-8")
    cfg = ctx.install_dir / "config"
    cfg.mkdir()
    (cfg / "app.json").write_text("{}\n", encoding="utf-8")
    listing = fm.list_directory("install", "", ctx=ctx)
    names = {row.name: row for row in listing.entries}
    assert names["backend"].is_dir is True
    assert names["backend"].sensitive is False
    assert names["VERSION"].sensitive is False
    assert names[".env"].sensitive is True
    assert names[".env"].downloadable is False
    assert names[".env.example"].sensitive is False
    assert names[".env.example"].downloadable is True
    assert names[".git"].sensitive is False
    assert names[".git"].is_dir is True
    assert names["config"].sensitive is False
    assert names["config"].is_dir is True
    git_listing = fm.list_directory("install", ".git", ctx=ctx)
    assert {row.name for row in git_listing.entries} == {"config"}
    cfg_listing = fm.list_directory("install", "config", ctx=ctx)
    assert {row.name for row in cfg_listing.entries} == {"app.json"}
    assert fm.resolve_download("install", ".git/config", ctx=ctx).name == "config"
    assert fm.resolve_download("install", "config/app.json", ctx=ctx).name == "app.json"
    deleted_git = fm.delete_entries("install", "", [".git"], ctx=ctx)
    assert deleted_git.kept_sensitive is False
    assert not git.exists()


def test_browse_root_prefers_install_for_nested_data(tmp_path: Path) -> None:
    fm.clear_size_cache()
    ctx = _ctx(tmp_path)
    (ctx.models_dir / "rapidocr").mkdir()
    (ctx.models_dir / "rapidocr" / "a.bin").write_bytes(b"12")
    summary = fm.build_summary(ctx)
    assert [row.id for row in summary.roots] == ["install"]
    rapid = next(row for row in summary.buckets if row.id == "ocr_rapidocr")
    assert rapid.browse_root_id == "install"
    assert rapid.browse_path.replace("\\", "/") == "data/models/rapidocr"


def test_file_manager_stays_inside_install_root(tmp_path: Path) -> None:
    outside_backup = tmp_path / "outside-backups"
    outside_static = tmp_path / "outside-static"
    outside_backup.mkdir()
    outside_static.mkdir()
    ctx = _ctx(tmp_path, backup_dir=outside_backup, static_dir=outside_static)
    assert [row.id for row in fm.browse_roots(ctx)] == ["install"]
    ids = {row.id for row in fm.catalog_buckets(ctx)}
    assert "site_backup" not in ids
    assert "frontend_static" not in ids
    with pytest.raises(fm.FileManagerError) as missing:
        fm.list_directory("hf_cache", "", ctx=ctx)
    assert missing.value.status_code == 404

    inside_backup = ctx.data_root / "backups"
    inside_backup.mkdir()
    ctx_in = fm.FileManagerContext(
        **{**ctx.__dict__, "backup_dir": inside_backup}
    )
    assert "site_backup" in {row.id for row in fm.catalog_buckets(ctx_in)}


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
    mdb = ctx.data_root / "mariadb"
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

    listing = fm.list_directory("install", "data/mariadb", ctx=ctx)
    names = {row.name: row for row in listing.entries}
    assert names["provision.json"].sensitive is True
    assert names["provision.json"].downloadable is False
    assert names["data"].sensitive is True
    assert names["my.ini"].sensitive is False
    assert names["dist"].sensitive is False

    with pytest.raises(fm.FileManagerError) as hidden:
        fm.list_directory("install", "data/mariadb/data", ctx=ctx)
    assert hidden.value.status_code == 403
    with pytest.raises(fm.FileManagerError) as blocked:
        fm.resolve_download("install", "data/mariadb/provision.json", ctx=ctx)
    assert blocked.value.status_code == 403
    got = fm.resolve_download("install", "data/mariadb/my.ini", ctx=ctx)
    assert got.name == "my.ini"


def test_openapi_files_admin_only() -> None:
    from app.main import app

    schema = app.openapi()
    paths = schema.get("paths") or {}
    summary = paths.get("/api/settings/files/summary") or {}
    browse = paths.get("/api/settings/files/browse") or {}
    download = paths.get("/api/settings/files/download") or {}
    contents = paths.get("/api/settings/files/contents") or {}
    assert summary.get("get") is not None
    assert browse.get("get") is not None
    assert download.get("get") is not None
    assert contents.get("get") is not None
    assert contents.get("put") is not None
    assert (paths.get("/api/settings/files/upload") or {}).get("post") is not None
    assert (paths.get("/api/settings/files/create-folder") or {}).get("post") is not None
    assert (paths.get("/api/settings/files/create-file") or {}).get("post") is not None
    assert (paths.get("/api/settings/files/rename") or {}).get("post") is not None
    assert (paths.get("/api/settings/files/delete") or {}).get("post") is not None
    components = (schema.get("components") or {}).get("schemas") or {}
    assert "FileSummaryOut" in components
    assert "FileBrowseOut" in components
    assert "FileOkOut" in components
    assert "FileContentsOut" in components
    entry = components["FileBrowseEntryOut"]["properties"]
    assert "editable" in entry


def test_crud_inside_install_root(tmp_path: Path) -> None:
    fm.clear_size_cache()
    ctx = _ctx(tmp_path)
    notes = ctx.data_dir / "notes"
    created = fm.create_folder("install", "data/runtime", "notes", ctx=ctx)
    assert created.name == "notes"
    assert notes.is_dir()

    made = fm.create_file("install", "data/runtime/notes", "hello.txt", "hi\n", ctx=ctx)
    assert made.name == "hello.txt"
    assert (notes / "hello.txt").read_text(encoding="utf-8") == "hi\n"

    listing = fm.list_directory("install", "data/runtime/notes", ctx=ctx)
    names = {row.name: row for row in listing.entries}
    assert names["hello.txt"].downloadable is True
    assert names["hello.txt"].editable is True

    read = fm.read_text("install", "data/runtime/notes/hello.txt", ctx=ctx)
    assert read.content == "hi\n"
    fm.write_text("install", "data/runtime/notes/hello.txt", "updated\n", ctx=ctx)
    assert (notes / "hello.txt").read_text(encoding="utf-8") == "updated\n"

    fm.rename_entry("install", "data/runtime/notes", "hello.txt", "hi.txt", ctx=ctx)
    assert not (notes / "hello.txt").exists()
    assert (notes / "hi.txt").is_file()

    uploaded = fm.upload_file(
        "install",
        "data/runtime/notes",
        "pack.bin",
        b"xyz",
        ctx=ctx,
    )
    assert uploaded.name == "pack.bin"
    assert (notes / "pack.bin").read_bytes() == b"xyz"
    fm.upload_file("install", "data/runtime/notes", "pack.bin", b"zzz", ctx=ctx)
    assert (notes / "pack.bin").read_bytes() == b"zzz"

    deleted = fm.delete_entries(
        "install",
        "data/runtime/notes",
        ["hi.txt", "pack.bin"],
        ctx=ctx,
    )
    assert deleted.kept_sensitive is False
    assert list(notes.iterdir()) == []

    fm.delete_entries("install", "data/runtime", ["notes"], ctx=ctx)
    assert not notes.exists()


def test_crud_refuses_sensitive_and_escape(tmp_path: Path) -> None:
    fm.clear_size_cache()
    ctx = _ctx(tmp_path)
    (ctx.install_dir / ".env").write_text("SECRET=1\n", encoding="utf-8")
    secret = ctx.data_dir / ".secret_key"
    secret.write_text("secret\n", encoding="utf-8")
    (ctx.data_dir / "ok.log").write_text("hello\n", encoding="utf-8")
    cfg = ctx.install_dir / "config"
    cfg.mkdir()
    (cfg / "app.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(fm.FileManagerError) as create_env:
        fm.create_file("install", "", ".env.local", "x=1\n", ctx=ctx)
    assert create_env.value.status_code == 403
    with pytest.raises(fm.FileManagerError) as upload_key:
        fm.upload_file("install", "data/runtime", ".secret_key", b"nope", ctx=ctx)
    assert upload_key.value.status_code == 403
    with pytest.raises(fm.FileManagerError) as write_secret:
        fm.write_text("install", "data/runtime/.secret_key", "x", ctx=ctx)
    assert write_secret.value.status_code == 403
    with pytest.raises(fm.FileManagerError) as read_secret:
        fm.read_text("install", "data/runtime/.secret_key", ctx=ctx)
    assert read_secret.value.status_code == 403
    with pytest.raises(fm.FileManagerError) as del_env:
        fm.delete_entries("install", "", [".env"], ctx=ctx)
    assert del_env.value.status_code == 403
    assert (ctx.install_dir / ".env").is_file()
    deleted_cfg = fm.delete_entries("install", "", ["config"], ctx=ctx)
    assert deleted_cfg.kept_sensitive is False
    assert not cfg.exists()
    with pytest.raises(fm.FileManagerError) as rename_secret:
        fm.rename_entry("install", "data/runtime", ".secret_key", "key.txt", ctx=ctx)
    assert rename_secret.value.status_code == 403
    with pytest.raises(fm.FileManagerError) as rename_to_env:
        fm.rename_entry("install", "data/runtime", "ok.log", ".env", ctx=ctx)
    assert rename_to_env.value.status_code == 403
    with pytest.raises(fm.FileManagerError):
        fm.create_file("install", "data/runtime", "../outside.txt", "nope", ctx=ctx)
    with pytest.raises(fm.FileManagerError):
        fm.delete_entries("install", "data/runtime", ["../outside.txt"], ctx=ctx)
    assert secret.read_text(encoding="utf-8") == "secret\n"


def test_delete_dir_skips_sensitive_children(tmp_path: Path) -> None:
    fm.clear_size_cache()
    ctx = _ctx(tmp_path)
    runtime = ctx.data_dir
    (runtime / ".secret_key").write_text("secret\n", encoding="utf-8")
    logs = runtime / "logs"
    logs.mkdir()
    (logs / "app.jsonl").write_text("{}\n", encoding="utf-8")
    (runtime / "ok.log").write_text("hello\n", encoding="utf-8")

    result = fm.delete_entries("install", "data", ["runtime"], ctx=ctx)
    assert result.kept_sensitive is True
    assert (runtime / ".secret_key").is_file()
    assert not (runtime / "ok.log").exists()
    assert not logs.exists()

    mdb = ctx.data_root / "mariadb"
    (mdb / "data").mkdir(parents=True)
    (mdb / "data" / "ibdata1").write_bytes(b"x" * 8)
    (mdb / "provision.json").write_text("{}\n", encoding="utf-8")
    (mdb / "my.ini").write_text("[mysqld]\n", encoding="utf-8")
    (mdb / "dist").mkdir()
    (mdb / "dist" / "readme.txt").write_text("bin\n", encoding="utf-8")
    nested = fm.delete_entries("install", "data", ["mariadb"], ctx=ctx)
    assert nested.kept_sensitive is True
    assert (mdb / "data" / "ibdata1").is_file()
    assert (mdb / "provision.json").is_file()
    assert not (mdb / "my.ini").exists()
    assert not (mdb / "dist").exists()


def test_rename_dir_blocked_when_it_holds_secrets(tmp_path: Path) -> None:
    fm.clear_size_cache()
    ctx = _ctx(tmp_path)
    (ctx.data_dir / ".secret_key").write_text("secret\n", encoding="utf-8")
    (ctx.data_dir / "ok.log").write_text("hello\n", encoding="utf-8")
    with pytest.raises(fm.FileManagerError) as blocked:
        fm.rename_entry("install", "data", "runtime", "runtime-old", ctx=ctx)
    assert blocked.value.status_code == 403
    assert ctx.data_dir.is_dir()
    empty = ctx.data_root / "tmp"
    empty.mkdir()
    (empty / "a.txt").write_text("x\n", encoding="utf-8")
    fm.rename_entry("install", "data", "tmp", "tmp2", ctx=ctx)
    assert not empty.exists()
    assert (ctx.data_root / "tmp2" / "a.txt").is_file()


def test_validate_entry_name() -> None:
    assert fm.validate_entry_name("ok.log") == "ok.log"
    assert fm.validate_entry_name("dir/foo.txt", from_upload=True) == "foo.txt"
    with pytest.raises(fm.FileManagerError):
        fm.validate_entry_name("a/b")
    with pytest.raises(fm.FileManagerError):
        fm.validate_entry_name("..")
    with pytest.raises(fm.FileManagerError):
        fm.validate_entry_name("")
    assert fm.looks_like_text_name("hello.txt", 12) is True
    assert fm.looks_like_text_name("det.onnx", 12) is False
    assert fm.looks_like_text_name("VERSION", 6) is True
    assert fm.looks_like_text_name(".env.example", 8) is True


def test_create_conflict_and_binary_text(tmp_path: Path) -> None:
    fm.clear_size_cache()
    ctx = _ctx(tmp_path)
    fm.create_file("install", "data/runtime", "a.txt", "one", ctx=ctx)
    with pytest.raises(fm.FileManagerError) as exists:
        fm.create_file("install", "data/runtime", "a.txt", "two", ctx=ctx)
    assert exists.value.status_code == 409
    (ctx.data_dir / "blob.bin").write_bytes(b"\x00\x01\x02")
    listing = fm.list_directory("install", "data/runtime", ctx=ctx)
    names = {row.name: row for row in listing.entries}
    assert names["blob.bin"].editable is False
    with pytest.raises(fm.FileManagerError) as not_text:
        fm.read_text("install", "data/runtime/blob.bin", ctx=ctx)
    assert not_text.value.status_code == 415
    with pytest.raises(fm.FileManagerError) as missing:
        fm.delete_entries("install", "data/runtime", ["nope.txt"], ctx=ctx)
    assert missing.value.status_code == 404


def _site_config(ctx: fm.FileManagerContext) -> Path:
    cfg = ctx.install_dir / "config"
    cfg.mkdir()
    (cfg / "app.json").write_text("{}\n", encoding="utf-8")
    (cfg / "database.json").write_text('{"url": "mysql+pymysql://u:pw@db/z"}\n', encoding="utf-8")
    (cfg / "integrations.json").write_text('{"steam_api_key": "k"}\n', encoding="utf-8")
    (cfg / "email.json").write_text('{"smtp_password": "p"}\n', encoding="utf-8")
    return cfg


def test_secret_config_files_are_sensitive() -> None:
    for rel in (
        "config/database.json",
        "config/integrations.json",
        "config/email.json",
        "CONFIG/Database.JSON",
        "config/.database.k3j2_x.tmp",
        "config/.email.abc.tmp",
        "data/tmp/restore/config/integrations.json",
    ):
        assert fm.rel_is_sensitive(rel), rel
    for rel in (
        "config",
        "config/app.json",
        "config/auth.json",
        "config/ocr.json",
        "config/.app.x.tmp",
        "config.example/database.json",
        "scripts/config.example/email.json",
        "config/database.json.bak/readme.txt",
        "database.json",
    ):
        assert not fm.rel_is_sensitive(rel), rel
    assert fm.is_sensitive_name(".secret_key.0f3a9c.tmp")


def test_secret_config_files_locked(tmp_path: Path) -> None:
    fm.clear_size_cache()
    ctx = _ctx(tmp_path)
    cfg = _site_config(ctx)
    locked = ("database.json", "integrations.json", "email.json")

    listing = fm.list_directory("install", "config", ctx=ctx)
    names = {row.name: row for row in listing.entries}
    for name in locked:
        assert names[name].sensitive is True
        assert names[name].downloadable is False
        assert names[name].editable is False
    assert names["app.json"].sensitive is False
    assert names["app.json"].editable is True

    for name in locked:
        rel = f"config/{name}"
        attempts: list[tuple[object, tuple[object, ...]]] = [
            (fm.resolve_download, ("install", rel)),
            (fm.read_text, ("install", rel)),
            (fm.write_text, ("install", rel, "{}")),
            (fm.upload_file, ("install", "config", name, b"{}")),
            (fm.rename_entry, ("install", "config", name, "x.json")),
            (fm.rename_entry, ("install", "config", "app.json", name)),
            (fm.delete_entries, ("install", "config", [name])),
        ]
        for func, args in attempts:
            with pytest.raises(fm.FileManagerError) as blocked:
                func(*args, ctx=ctx)  # type: ignore[operator]
            assert blocked.value.status_code == 403, (func, args)
    (cfg / "email.json").unlink()
    with pytest.raises(fm.FileManagerError) as recreate:
        fm.create_file("install", "config", "email.json", "{}", ctx=ctx)
    assert recreate.value.status_code == 403
    with pytest.raises(fm.FileManagerError) as rename_dir:
        fm.rename_entry("install", "", "config", "config-old", ctx=ctx)
    assert rename_dir.value.status_code == 403

    deleted = fm.delete_entries("install", "", ["config"], ctx=ctx)
    assert deleted.kept_sensitive is True
    assert not (cfg / "app.json").exists()
    assert sorted(p.name for p in cfg.iterdir()) == ["database.json", "integrations.json"]
    assert "pw@db" in (cfg / "database.json").read_text(encoding="utf-8")


def test_symlink_inside_root_cannot_alias_sensitive(tmp_path: Path) -> None:
    fm.clear_size_cache()
    ctx = _ctx(tmp_path)
    cfg = _site_config(ctx)
    (cfg / "email.json").unlink()
    mdb_data = ctx.data_root / "mariadb" / "data"
    mdb_data.mkdir(parents=True)
    (mdb_data / "ibdata1").write_bytes(b"x" * 8)
    try:
        (ctx.install_dir / "cfglink").symlink_to(cfg, target_is_directory=True)
        (ctx.data_root / "dblink").symlink_to(mdb_data, target_is_directory=True)
        (ctx.install_dir / "dbjson").symlink_to(cfg / "database.json")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")

    listing = fm.list_directory("install", "cfglink", ctx=ctx)
    names = {row.name: row for row in listing.entries}
    assert names["database.json"].sensitive is True
    assert names["database.json"].downloadable is False
    assert names["app.json"].downloadable is True
    for action in (
        lambda: fm.resolve_download("install", "cfglink/database.json", ctx=ctx),
        lambda: fm.resolve_download("install", "dbjson", ctx=ctx),
        lambda: fm.write_text("install", "cfglink/integrations.json", "{}", ctx=ctx),
        lambda: fm.upload_file("install", "cfglink", "database.json", b"{}", ctx=ctx),
        lambda: fm.create_file("install", "cfglink", "email.json", "{}", ctx=ctx),
        lambda: fm.delete_entries("install", "cfglink", ["database.json"], ctx=ctx),
        lambda: fm.rename_entry("install", "cfglink", "database.json", "db.json", ctx=ctx),
        lambda: fm.list_directory("install", "data/dblink", ctx=ctx),
        lambda: fm.resolve_download("install", "data/dblink/ibdata1", ctx=ctx),
    ):
        with pytest.raises(fm.FileManagerError) as blocked:
            action()
        assert blocked.value.status_code == 403
    for link in ("cfglink", "dbjson"):
        with pytest.raises(fm.FileManagerError) as link_delete:
            fm.delete_entries("install", "", [link], ctx=ctx)
        assert link_delete.value.status_code == 400
    with pytest.raises(fm.FileManagerError):
        fm.delete_entries("install", "data", ["dblink"], ctx=ctx)
    assert (cfg / "database.json").is_file()
    assert (cfg / "integrations.json").read_text(encoding="utf-8") == '{"steam_api_key": "k"}\n'
    assert not (cfg / "email.json").exists()
    assert (mdb_data / "ibdata1").is_file()


def _leftovers(path: Path) -> list[str]:
    return sorted(p.name for p in path.iterdir() if p.name.endswith(".part"))


def test_upload_stream_caps_without_partial_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fm.clear_size_cache()
    ctx = _ctx(tmp_path)
    monkeypatch.setattr(fm, "MAX_UPLOAD_BYTES", 10)
    monkeypatch.setattr(fm, "_WRITE_CHUNK", 4)
    runtime = ctx.data_dir

    exact = fm.upload_stream("install", "data/runtime", "pack.bin", io.BytesIO(b"0123456789"), ctx=ctx)
    assert exact.name == "pack.bin"
    assert (runtime / "pack.bin").read_bytes() == b"0123456789"

    with pytest.raises(fm.FileManagerError) as too_big:
        fm.upload_stream("install", "data/runtime", "big.bin", io.BytesIO(b"x" * 11), ctx=ctx)
    assert too_big.value.status_code == 413
    assert not (runtime / "big.bin").exists()
    with pytest.raises(fm.FileManagerError) as overwrite_big:
        fm.upload_stream("install", "data/runtime", "pack.bin", io.BytesIO(b"y" * 64), ctx=ctx)
    assert overwrite_big.value.status_code == 413
    assert (runtime / "pack.bin").read_bytes() == b"0123456789"
    with pytest.raises(fm.FileManagerError) as bytes_big:
        fm.upload_file("install", "data/runtime", "pack.bin", b"z" * 11, ctx=ctx)
    assert bytes_big.value.status_code == 413

    class _Broken(io.RawIOBase):
        def __init__(self) -> None:
            self.calls = 0

        def readable(self) -> bool:
            return True

        def read(self, size: int = -1) -> bytes:
            self.calls += 1
            if self.calls > 1:
                raise OSError("disk gone")
            return b"new!"

    with pytest.raises(fm.FileManagerError) as broken:
        fm.upload_stream("install", "data/runtime", "pack.bin", _Broken(), ctx=ctx)
    assert broken.value.status_code == 500
    assert (runtime / "pack.bin").read_bytes() == b"0123456789"
    assert _leftovers(runtime) == []

    (runtime / "sub").mkdir()
    with pytest.raises(fm.FileManagerError) as onto_dir:
        fm.upload_stream("install", "data/runtime", "sub", io.BytesIO(b"x"), ctx=ctx)
    assert onto_dir.value.status_code == 409
    assert _leftovers(runtime) == []


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_overwrite_keeps_file_mode(tmp_path: Path) -> None:
    fm.clear_size_cache()
    ctx = _ctx(tmp_path)
    target = ctx.data_dir / "run.sh"
    target.write_text("echo old\n", encoding="utf-8")
    target.chmod(0o750)
    fm.upload_file("install", "data/runtime", "run.sh", b"echo new\n", ctx=ctx)
    assert stat.S_IMODE(target.stat().st_mode) == 0o750
    fm.write_text("install", "data/runtime/run.sh", "echo edited\n", ctx=ctx)
    assert stat.S_IMODE(target.stat().st_mode) == 0o750
    assert target.read_text(encoding="utf-8") == "echo edited\n"
    assert _leftovers(ctx.data_dir) == []


def test_upload_endpoint_streams_in_worker_thread(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import anyio
    import httpx
    from fastapi import FastAPI

    from app.api import files as files_api
    from app.core.deps import require_admin

    fm.clear_size_cache()
    ctx = _ctx(tmp_path)
    monkeypatch.setattr(fm, "context_from_settings", lambda: ctx)
    monkeypatch.setattr(fm, "MAX_UPLOAD_BYTES", 2 * 1024 * 1024)
    seen: list[tuple[bool, bool]] = []
    real_stream = fm.upload_stream

    def _spy(root_id: str, dir_rel: str, filename: str, source: object, **kwargs: object) -> fm.MutateResult:
        seen.append((threading.current_thread() is threading.main_thread(), isinstance(source, bytes)))
        return real_stream(root_id, dir_rel, filename, source, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(fm, "upload_stream", _spy)
    app = FastAPI()
    app.include_router(files_api.router, prefix="/api")
    app.dependency_overrides[require_admin] = lambda: object()
    payload = os.urandom(1024 * 1024 + 7)

    async def _run() -> tuple[httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            ok = await client.post(
                "/api/settings/files/upload",
                data={"root_id": "install", "path": "data/runtime"},
                files={"file": ("blob.bin", payload, "application/octet-stream")},
            )
            big = await client.post(
                "/api/settings/files/upload",
                data={"root_id": "install", "path": "data/runtime"},
                files={"file": ("huge.bin", b"h" * (2 * 1024 * 1024 + 1), "application/octet-stream")},
            )
        return ok, big

    ok, big = anyio.run(_run)
    assert ok.status_code == 200, ok.text
    assert ok.json()["name"] == "blob.bin"
    assert (ctx.data_dir / "blob.bin").read_bytes() == payload
    assert big.status_code == 413
    assert big.json()["detail"] == "上传不能超过 2MB"
    assert not (ctx.data_dir / "huge.bin").exists()
    assert _leftovers(ctx.data_dir) == []
    assert seen == [(False, False), (False, False)]
