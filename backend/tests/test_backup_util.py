"""scripts/common/backup_util.py: DB resolution, consistent SQLite copy, manifest checks, safe restore."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sqlite3
import stat
import sys
import tarfile
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "common" / "backup_util.py"


def _load():
    spec = importlib.util.spec_from_file_location("backup_util", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


bu = _load()


def _write_revision(versions: Path, rev: str, down: object) -> None:
    versions.mkdir(parents=True, exist_ok=True)
    (versions / f"{rev}.py").write_text(
        "from typing import Sequence, Union\n"
        f"revision: str = {rev!r}\n"
        f"down_revision: Union[str, Sequence[str], None] = {down!r}\n",
        encoding="utf-8",
    )


def _install(tmp_path: Path, *, version: str = "0.6.0", db: dict | None = None) -> Path:
    root = tmp_path / "install"
    (root / "config").mkdir(parents=True)
    (root / "VERSION").write_text(version + "\n", encoding="utf-8")
    (root / "config" / "app.json").write_text('{"APP_ENV": "production"}', encoding="utf-8")
    if db is not None:
        (root / "config" / "database.json").write_text(json.dumps(db), encoding="utf-8")
    versions = root / "backend" / "alembic" / "versions"
    _write_revision(versions, "r1", None)
    _write_revision(versions, "r2", "r1")
    return root


def _wal_db(path: Path, revision: str = "r2") -> sqlite3.Connection:
    """Live database whose newest rows sit only in the -wal file (connection kept open)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    conn.execute("INSERT INTO alembic_version VALUES (?)", (revision,))
    conn.execute("CREATE TABLE users (name TEXT)")
    conn.executemany("INSERT INTO users VALUES (?)", [("a",), ("b",), ("c",)])
    conn.commit()
    return conn


def _names(archive: Path) -> set[str]:
    with tarfile.open(archive) as tf:
        return set(tf.getnames())


def _manifest(archive: Path) -> dict:
    with tarfile.open(archive) as tf:
        fh = tf.extractfile("manifest.json")
        assert fh is not None
        return json.loads(fh.read().decode("utf-8"))


@pytest.fixture(autouse=True)
def _no_env_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)


def test_resolve_db_follows_app_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path
    cfg = tmp_path / "config"
    cfg.mkdir()
    assert bu.resolve_db(cfg, root).engine == ""

    (cfg / "database.json").write_text('{"engine": "sqlite", "path": "", "url": ""}', encoding="utf-8")
    t = bu.resolve_db(cfg, root)
    assert (t.engine, t.sqlite_path) == ("sqlite", root / "data" / "runtime" / "zhange.sqlite")

    (cfg / "database.json").write_text('{"engine": "sqlite", "path": "db/x.sqlite"}', encoding="utf-8")
    assert bu.resolve_db(cfg, root).sqlite_path == root / "db" / "x.sqlite"

    url = "mysql+pymysql://u:p@db:3307/zh?charset=utf8mb4"
    (cfg / "database.json").write_text(json.dumps({"engine": "mysql", "url": url}), encoding="utf-8")
    assert bu.resolve_db(cfg, root) == bu.DbTarget("mysql", url=url)

    monkeypatch.setenv("DATABASE_URL", "sqlite:////srv/zhange.sqlite")
    t = bu.resolve_db(cfg, root)
    assert (t.engine, t.sqlite_path) == ("sqlite", Path("/srv/zhange.sqlite"))


def test_sqlite_url_paths(tmp_path: Path) -> None:
    assert bu.sqlite_path_from_url("sqlite:////abs/z.db", tmp_path) == Path("/abs/z.db")
    assert bu.sqlite_path_from_url("sqlite:///rel.db?x=1", tmp_path) == tmp_path / "backend" / "rel.db"
    assert bu.sqlite_path_from_url("sqlite://", tmp_path) is None
    assert bu.sqlite_path_from_url("sqlite:///:memory:", tmp_path) is None


def test_parse_mysql_url_and_client_args() -> None:
    conn = bu.parse_mysql_url("mysql+pymysql://zh%40ng:p%24%28x%29%22%27@db.local:3307/zhange_stats?charset=utf8mb4")
    assert (conn.user, conn.password, conn.host, conn.port, conn.database) == (
        "zh@ng",
        "p$(x)\"'",
        "db.local",
        3307,
        "zhange_stats",
    )
    args = conn.client_args()
    assert args[0] == "--default-character-set=utf8mb4"
    assert "--protocol=TCP" in args and "db.local" in args and "3307" in args
    assert all(conn.password not in a for a in args)
    assert conn.env()["MYSQL_PWD"] == "p$(x)\"'"

    sock = bu.parse_mysql_url("mysql+pymysql://root@localhost/zh?unix_socket=/run/mysqld/mysqld.sock")
    assert "--socket=/run/mysqld/mysqld.sock" in sock.client_args()
    assert "MYSQL_PWD" not in sock.env()

    with pytest.raises(bu.BackupError):
        bu.parse_mysql_url("mysql+pymysql://u:p@db:3306/")


def test_code_revisions_heads_handle_merges(tmp_path: Path) -> None:
    versions = tmp_path / "backend" / "alembic" / "versions"
    _write_revision(versions, "a", None)
    _write_revision(versions, "b", "a")
    _write_revision(versions, "c", "a")
    known, heads = bu.code_revisions(tmp_path)
    assert known == {"a", "b", "c"} and heads == {"b", "c"}
    _write_revision(versions, "m", ("b", "c"))
    assert bu.code_revisions(tmp_path)[1] == {"m"}


def test_dump_revisions(tmp_path: Path) -> None:
    dump = tmp_path / "zhange.sql"
    dump.write_bytes(
        b"-- dump\nINSERT INTO `users` VALUES ('x');\n"
        b"INSERT INTO `alembic_version` VALUES ('20261010_0119');\n"
    )
    assert bu.dump_revisions(dump) == ["20261010_0119"]
    assert bu.dump_revisions(tmp_path / "missing.sql") == []


def test_sqlite_backup_is_consistent_and_skips_transient_files(tmp_path: Path) -> None:
    root = _install(tmp_path, db={"engine": "sqlite", "path": "data/runtime/zhange.sqlite", "url": ""})
    runtime = root / "data" / "runtime"
    live = _wal_db(runtime / "zhange.sqlite")
    try:
        assert (runtime / "zhange.sqlite-wal").stat().st_size > 0
        (runtime / ".secret_key").write_text("k", encoding="utf-8")
        (runtime / "logs").mkdir()
        (runtime / "logs" / "app.jsonl").write_text("{}\n", encoding="utf-8")
        (runtime / "update-tmp" / "rollback-src").mkdir(parents=True)
        (runtime / "update-tmp" / "rollback-src" / "big").write_text("x", encoding="utf-8")
        (runtime / "update.lock").write_text("1", encoding="utf-8")
        (runtime / "setup-token").write_text("tok", encoding="utf-8")
        (root / "data" / "uploads" / "avatars").mkdir(parents=True)
        (root / "data" / "uploads" / "avatars" / "1.jpg").write_bytes(b"jpg")
        (root / "data" / "models" / "easyocr").mkdir(parents=True)
        (root / "data" / "models" / "easyocr" / "m.pth").write_bytes(b"m")
        (root / "data" / "models" / "easyocr" / "m.pth.part").write_bytes(b"partial")
        (root / "data" / "cache").mkdir()
        (root / "data" / "cache" / "junk").write_text("x", encoding="utf-8")

        archive = tmp_path / "backups" / "zhange-1.tar.gz"
        rc = bu.main(["backup", "--root", str(root), "--out", str(archive), "--work", str(tmp_path / "w")])
    finally:
        live.close()

    assert rc == 0
    assert stat.S_IMODE(archive.stat().st_mode) == 0o600
    assert not archive.with_name(archive.name + ".part").exists()
    names = _names(archive)
    assert {
        "manifest.json",
        "config/app.json",
        "config/database.json",
        "data/runtime/.secret_key",
        "data/runtime/logs/app.jsonl",
        "data/runtime/zhange.sqlite",
        "data/uploads/avatars/1.jpg",
        "data/models/easyocr/m.pth",
    } <= names
    for gone in (
        "data/runtime/zhange.sqlite-wal",
        "data/runtime/zhange.sqlite-shm",
        "data/runtime/update-tmp",
        "data/runtime/update.lock",
        "data/runtime/setup-token",
        "data/models/easyocr/m.pth.part",
        "data/cache/junk",
    ):
        assert gone not in names
    assert sum(1 for n in names if n == "data/runtime/zhange.sqlite") == 1

    manifest = _manifest(archive)
    assert manifest["version"] == "0.6.0"
    assert manifest["engine"] == "sqlite"
    assert manifest["alembic_revisions"] == ["r2"]
    assert manifest["code_heads"] == ["r2"]
    assert manifest["sqlite"] == {"arcname": "data/runtime/zhange.sqlite"}

    copied = tmp_path / "copy.sqlite"
    with tarfile.open(archive) as tf:
        fh = tf.extractfile("data/runtime/zhange.sqlite")
        assert fh is not None
        copied.write_bytes(fh.read())
    copy = sqlite3.connect(str(copied))
    try:
        assert copy.execute("SELECT COUNT(*) FROM users").fetchone() == (3,)
        assert copy.execute("PRAGMA journal_mode").fetchone() == ("delete",)
    finally:
        copy.close()


def test_restore_flow_for_sqlite_kept_outside_data(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src_root = _install(tmp_path / "a", db={"engine": "sqlite", "path": "db/custom.sqlite"})
    _wal_db(src_root / "db" / "custom.sqlite").close()
    archive = tmp_path / "b.tar.gz"
    assert bu.main(["backup", "--root", str(src_root), "--out", str(archive), "--work", str(tmp_path / "w")]) == 0
    assert _manifest(archive)["sqlite"] == {"arcname": "db/custom.sqlite"}

    dest_root = _install(tmp_path / "b", version="0.6.1")
    stale = dest_root / "db" / "custom.sqlite-wal"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"stale wal from the old database")
    work = tmp_path / "restore"
    assert bu.main(["unpack", "--archive", str(archive), "--dest", str(work)]) == 0
    assert bu.main(["inspect", "--root", str(dest_root), "--dir", str(work)]) == 0
    assert "备份来自 v0.6.0，当前代码是 v0.6.1" in capsys.readouterr().out
    assert bu.main(["load-db", "--root", str(dest_root), "--dir", str(work)]) == 0

    restored = dest_root / "db" / "custom.sqlite"
    assert not stale.exists()
    conn = sqlite3.connect(str(restored))
    try:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone() == (3,)
    finally:
        conn.close()


def test_inspect_warns_when_backup_is_newer_than_code(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _install(tmp_path)
    work = tmp_path / "w"
    work.mkdir()
    (work / "manifest.json").write_text(
        json.dumps({"format": 1, "version": "0.7.0", "engine": "mysql", "alembic_revisions": ["r9"]}),
        encoding="utf-8",
    )
    assert bu.main(["inspect", "--root", str(root), "--dir", str(work)]) == 0
    out = capsys.readouterr().out
    assert "WARN: 备份来自 v0.7.0" in out
    assert "r9 不在当前代码里" in out

    (work / "manifest.json").write_text(
        json.dumps({"format": 1, "version": "0.6.0", "alembic_revisions": ["r1"]}), encoding="utf-8"
    )
    bu.main(["inspect", "--root", str(root), "--dir", str(work)])
    assert "启动时会自动迁移到 r2" in capsys.readouterr().out

    (work / "manifest.json").unlink()
    bu.main(["inspect", "--root", str(root), "--dir", str(work)])
    assert "旧格式备份" in capsys.readouterr().out


def _tar_with(path: Path, members: dict[str, bytes]) -> None:
    with tarfile.open(path, "w:gz") as tf:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))


def test_unpack_refuses_traversal_and_foreign_archives(tmp_path: Path) -> None:
    evil = tmp_path / "evil.tar.gz"
    _tar_with(evil, {"config/app.json": b"{}", "../escaped.txt": b"x"})
    assert bu.main(["unpack", "--archive", str(evil), "--dest", str(tmp_path / "d1")]) == 1
    assert not (tmp_path / "escaped.txt").exists()

    foreign = tmp_path / "foreign.tar.gz"
    _tar_with(foreign, {"README.md": b"hi"})
    assert bu.main(["unpack", "--archive", str(foreign), "--dest", str(tmp_path / "d2")]) == 3

    legacy = tmp_path / "legacy.tar.gz"
    _tar_with(legacy, {"var/data/.secret_key": b"k", "config/app.json": b"{}"})
    assert bu.main(["unpack", "--archive", str(legacy), "--dest", str(tmp_path / "d3")]) == 0


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_unpack_without_tarfile_data_filter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Python builds without PEP 706 (e.g. Debian 12's 3.11.2) take the manual checks."""
    monkeypatch.delattr(bu.tarfile, "data_filter", raising=False)
    evil = tmp_path / "evil.tar.gz"
    _tar_with(evil, {"config/app.json": b"{}", "../escaped.txt": b"x"})
    assert bu.main(["unpack", "--archive", str(evil), "--dest", str(tmp_path / "d1")]) == 1
    assert not (tmp_path / "escaped.txt").exists()

    ok = tmp_path / "ok.tar.gz"
    with tarfile.open(ok, "w:gz") as tf:
        info = tarfile.TarInfo("config/app.json")
        info.size = 2
        info.mode = 0o4777
        tf.addfile(info, io.BytesIO(b"{}"))
        link = tarfile.TarInfo("data/runtime/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        tf.addfile(link)
    dest = tmp_path / "d2"
    assert bu.main(["unpack", "--archive", str(ok), "--dest", str(dest)]) == 0
    assert (dest / "config" / "app.json").read_bytes() == b"{}"
    assert stat.S_IMODE((dest / "config" / "app.json").stat().st_mode) & 0o7022 == 0
    assert not (dest / "data" / "runtime" / "link").is_symlink()


_FAKE_CLIENT = """#!{python}
import json, os, sys
args = sys.argv[1:]
result = [a.split("=", 1)[1] for a in args if a.startswith("--result-file=")]
if result:
    with open(result[0], "wb") as fh:
        fh.write(b"INSERT INTO `alembic_version` VALUES ('r2');\\n")
    data = b""
else:
    data = sys.stdin.buffer.read()
with open({record!r}, "w") as fh:
    json.dump({{"args": args, "pwd": os.environ.get("MYSQL_PWD"), "stdin": data.decode()}}, fh)
"""


def _fake_tool(bin_dir: Path, name: str, record: Path) -> None:
    """Records argv, MYSQL_PWD and stdin; writes --result-file like mysqldump."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = bin_dir / name
    script.write_text(_FAKE_CLIENT.format(python=sys.executable, record=str(record)), encoding="utf-8")
    script.chmod(0o755)


@pytest.mark.skipif(os.name == "nt", reason="fake client is a POSIX executable script")
def test_mysql_backup_and_import_pass_password_only_via_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    password = "p$(touch pwned)\"'`;x"
    url = "mysql+pymysql://zhange:p%24%28touch%20pwned%29%22%27%60%3Bx@127.0.0.1:3306/zhange_stats"
    root = _install(tmp_path, db={"engine": "mysql", "url": url})
    bin_dir = tmp_path / "bin"
    dump_record = tmp_path / "dump.json"
    load_record = tmp_path / "load.json"
    _fake_tool(bin_dir, "mysqldump", dump_record)
    _fake_tool(bin_dir, "mysql", load_record)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.chdir(tmp_path)

    archive = tmp_path / "m.tar.gz"
    assert bu.main(["backup", "--root", str(root), "--out", str(archive), "--work", str(tmp_path / "w")]) == 0
    dumped = json.loads(dump_record.read_text(encoding="utf-8"))
    assert dumped["pwd"] == password
    assert all(password not in a for a in dumped["args"])
    for flag in ("--default-character-set=utf8mb4", "--single-transaction", "--protocol=TCP"):
        assert flag in dumped["args"]
    assert dumped["args"][-1] == "zhange_stats"
    assert "zhange.sql" in _names(archive)
    assert _manifest(archive)["alembic_revisions"] == ["r2"]
    assert not (tmp_path / "pwned").exists()

    work = tmp_path / "restore"
    assert bu.main(["unpack", "--archive", str(archive), "--dest", str(work)]) == 0
    assert bu.main(["load-db", "--root", str(root), "--dir", str(work)]) == 0
    loaded = json.loads(load_record.read_text(encoding="utf-8"))
    assert loaded["pwd"] == password
    assert loaded["args"][0] == "--default-character-set=utf8mb4"
    assert loaded["args"][-1] == "zhange_stats"
    assert "alembic_version" in loaded["stdin"]
    assert not (tmp_path / "pwned").exists()


def test_load_db_refuses_dump_without_mysql_config(tmp_path: Path) -> None:
    root = _install(tmp_path, db={"engine": "sqlite", "path": ""})
    work = tmp_path / "w"
    work.mkdir()
    (work / "zhange.sql").write_text("SELECT 1;", encoding="utf-8")
    assert bu.main(["load-db", "--root", str(root), "--dir", str(work)]) == 1


def test_find_tool_falls_back_to_portable_mariadb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    suffix = ".exe" if os.name == "nt" else ""
    tool = tmp_path / "data" / "mariadb" / "dist" / "mariadb-11.4" / "bin" / f"mysqldump{suffix}"
    tool.parent.mkdir(parents=True)
    tool.write_bytes(b"")
    assert bu.find_tool(tmp_path, bu.DUMP_TOOLS) == str(tool)
    with pytest.raises(bu.BackupError):
        bu.find_tool(tmp_path, ("definitely-not-a-tool",))
