#!/usr/bin/env python3
"""Backup / restore worker for scripts/linux/{backup,restore}.sh and scripts/win/{backup,restore}.ps1.

Stdlib only: runs on the system Python, with or without the backend venv. The shells pass
plain path arguments; the database connection is read from config/database.json here, and
the MySQL password reaches the client only through ``MYSQL_PWD``.

  backup  --root R --out A --work W   write A (manifest.json + zhange.sql | consistent SQLite copy + files)
  unpack  --archive A --dest D        safe extraction (no absolute / ``..`` / outside links)
  inspect --root R --dir D            compare the backup's VERSION / Alembic revision with the code
  load-db --root R --dir D            import zhange.sql; put a SQLite file kept outside data/ back
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Sequence
from urllib.parse import parse_qs, unquote, urlsplit

MANIFEST_NAME = "manifest.json"
MANIFEST_FORMAT = 1
SQL_DUMP_NAME = "zhange.sql"
DATA_TREES = ("data/runtime", "data/uploads", "data/models")
LEGACY_TREES = {"data/runtime": "var/data", "data/uploads": "var/uploads"}
# Transient or regenerated entries directly under data/runtime.
RUNTIME_SKIP = frozenset(
    {"update-tmp", "update.lock", "setup-token", "tmp", "cache", "tarkov_pw_profile"}
)
SQLITE_SIDECARS = ("-wal", "-shm", "-journal")
DUMP_TOOLS = ("mysqldump", "mariadb-dump")
CLIENT_TOOLS = ("mysql", "mariadb")
DEFAULT_SQLITE_REL = "data/runtime/zhange.sqlite"
_ALEMBIC_INSERT = b"INSERT INTO `alembic_version`"

_tag = "backup"


class BackupError(RuntimeError):
    pass


def log(message: str) -> None:
    print(f"[{_tag}] {message}", flush=True)


def warn(message: str) -> None:
    print(f"[{_tag}] WARN: {message}", flush=True)


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_version(root: Path) -> str:
    try:
        return (root / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


# ---------------------------------------------------------------- database target


@dataclass(frozen=True)
class DbTarget:
    engine: str
    url: str = ""
    sqlite_path: Optional[Path] = None


def sqlite_path_from_url(url: str, root: Path) -> Optional[Path]:
    head, sep, rest = url.partition(":///")
    if not sep or not head.startswith("sqlite"):
        return None
    raw = unquote(rest.split("?", 1)[0])
    if not raw or raw == ":memory:":
        return None
    path = Path(raw)
    # SQLAlchemy resolves relative sqlite URLs against the process cwd, which is backend/.
    return path if path.is_absolute() else root / "backend" / path


def resolve_db(config_dir: Path, root: Path) -> DbTarget:
    """Same precedence as ``app.core.file_config.resolve_database_url``."""
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        data = _read_json(config_dir / "database.json")
        url = str(data.get("url") or "").strip()
        if str(data.get("engine") or "").strip().lower() == "sqlite":
            raw_path = str(data.get("path") or "").strip()
            if raw_path or not url:
                path = Path(raw_path or DEFAULT_SQLITE_REL)
                return DbTarget("sqlite", sqlite_path=path if path.is_absolute() else root / path)
    if url.startswith("sqlite"):
        return DbTarget("sqlite", url=url, sqlite_path=sqlite_path_from_url(url, root))
    if url.startswith("mysql"):
        return DbTarget("mysql", url=url)
    return DbTarget("", url=url)


@dataclass(frozen=True)
class MysqlConn:
    user: str
    password: str
    host: str
    port: int
    database: str
    socket: str = ""

    @property
    def where(self) -> str:
        return self.socket or f"{self.host}:{self.port}"

    def client_args(self) -> list[str]:
        args = ["--default-character-set=utf8mb4"]
        if self.user:
            args += ["-u", self.user]
        if self.socket:
            args += ["--protocol=SOCKET", f"--socket={self.socket}"]
        else:
            # PyMySQL (the app) always uses TCP unless unix_socket is given; match it.
            args += ["--protocol=TCP", "-h", self.host, "-P", str(self.port)]
        return args

    def env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.pop("MYSQL_PWD", None)
        if self.password:
            env["MYSQL_PWD"] = self.password
        return env


def parse_mysql_url(url: str) -> MysqlConn:
    parts = urlsplit(url)
    try:
        port = parts.port or 3306
    except ValueError as exc:
        raise BackupError("MySQL 连接串端口无效") from exc
    database = unquote(parts.path.lstrip("/"))
    if not database:
        raise BackupError("无法从 MySQL 连接串解析库名")
    query = parse_qs(parts.query)
    return MysqlConn(
        user=unquote(parts.username or ""),
        password=unquote(parts.password or ""),
        host=parts.hostname or "127.0.0.1",
        port=port,
        database=database,
        socket=(query.get("unix_socket") or [""])[0],
    )


def find_tool(root: Path, names: Sequence[str]) -> str:
    for name in names:
        hit = shutil.which(name)
        if hit:
            return hit
    suffix = ".exe" if os.name == "nt" else ""
    for dist in (root / "data" / "mariadb" / "dist", root / "var" / "mariadb" / "dist"):
        if not dist.is_dir():
            continue
        for name in names:
            for candidate in sorted(dist.rglob(name + suffix)):
                if candidate.is_file():
                    return str(candidate)
    raise BackupError(
        f"缺少 {names[0]}：请安装 MariaDB/MySQL 客户端并加入 PATH"
        "（Windows 便携包放在 data/mariadb/dist 下也能找到）"
    )


# ---------------------------------------------------------------- Alembic revisions


def code_revisions(root: Path) -> tuple[set[str], set[str]]:
    """(all revisions, heads) of backend/alembic/versions, read without importing Alembic."""
    downs: dict[str, tuple[str, ...]] = {}
    for path in sorted((root / "backend" / "alembic" / "versions").glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        revision = ""
        down: tuple[str, ...] = ()
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target, value = node.targets[0], node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                target, value = node.target, node.value
            else:
                continue
            if not isinstance(target, ast.Name) or target.id not in ("revision", "down_revision"):
                continue
            try:
                literal = ast.literal_eval(value)
            except ValueError:
                continue
            if target.id == "revision" and isinstance(literal, str):
                revision = literal
            elif target.id == "down_revision":
                if isinstance(literal, str):
                    down = (literal,)
                elif isinstance(literal, (list, tuple)):
                    down = tuple(str(x) for x in literal)
        if revision:
            downs[revision] = down
    referenced = {d for parents in downs.values() for d in parents}
    return set(downs), set(downs) - referenced


def sqlite_revisions(path: Path) -> list[str]:
    try:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            rows = conn.execute("SELECT version_num FROM alembic_version").fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return []
    return sorted({str(row[0]) for row in rows if row and row[0]})


def dump_revisions(dump: Path) -> list[str]:
    found: set[str] = set()
    try:
        with dump.open("rb") as fh:
            for line in fh:
                if line.startswith(_ALEMBIC_INSERT):
                    found.update(
                        m.decode("utf-8", "replace") for m in re.findall(rb"'([^'\\]+)'", line)
                    )
    except OSError:
        return []
    return sorted(found)


# ---------------------------------------------------------------- backup


def sqlite_backup(src: Path, dest: Path) -> None:
    """Consistent copy of a live (WAL) database through the SQLite online backup API."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    last: Optional[BaseException] = None
    # Read-only first so a backup never writes to the live database.
    for read_only in (True, False):
        if dest.exists():
            dest.unlink()
        try:
            if read_only:
                source = sqlite3.connect(f"{src.resolve().as_uri()}?mode=ro", uri=True, timeout=30)
            else:
                source = sqlite3.connect(str(src), timeout=30)
        except sqlite3.Error as exc:
            last = exc
            continue
        try:
            target = sqlite3.connect(str(dest))
            try:
                source.backup(target)
                try:
                    target.execute("PRAGMA journal_mode=DELETE")
                except sqlite3.Error:
                    pass
            finally:
                target.close()
            return
        except sqlite3.Error as exc:
            last = exc
        finally:
            source.close()
    if dest.exists():
        dest.unlink()
    raise BackupError(f"SQLite 备份失败：{last}")


def _arcname_in_root(path: Path, root: Path) -> Optional[str]:
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None
    return rel if rel not in ("", ".") else None


def _member_filter(
    top: str, skip: frozenset[str]
) -> Callable[[tarfile.TarInfo], Optional[tarfile.TarInfo]]:
    def keep(info: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
        name = info.name
        if name in skip or info.issym() or info.isdev():
            return None
        base = name.rsplit("/", 1)[-1]
        if base == "__pycache__" or base.endswith(".pyc"):
            return None
        if top == "data/runtime" and name.startswith(top + "/"):
            if name[len(top) + 1 :].split("/", 1)[0] in RUNTIME_SKIP:
                return None
        if top == "data/models" and base.endswith(".part"):
            return None
        return info
    return keep


def write_archive(
    root: Path,
    out: Path,
    *,
    manifest: dict,
    dump: Optional[Path] = None,
    sqlite_copy: Optional[tuple[Path, str]] = None,
    skip: frozenset[str] = frozenset(),
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_name(out.name + ".part")
    try:
        with tarfile.open(part, "w:gz", compresslevel=6) as tf:
            blob = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            info = tarfile.TarInfo(MANIFEST_NAME)
            info.size = len(blob)
            info.mtime = int(time.time())
            info.mode = 0o600
            tf.addfile(info, io.BytesIO(blob))
            if dump is not None:
                tf.add(str(dump), arcname=SQL_DUMP_NAME)
            for name in ("config", ".env"):
                src = root / name
                if src.exists():
                    tf.add(str(src.resolve()), arcname=name, filter=_member_filter(name, skip))
            for top in DATA_TREES:
                src = root / top
                if not src.is_dir() and top in LEGACY_TREES:
                    src = root / LEGACY_TREES[top]
                if src.is_dir():
                    tf.add(str(src.resolve()), arcname=top, filter=_member_filter(top, skip))
            if sqlite_copy is not None:
                tf.add(str(sqlite_copy[0]), arcname=sqlite_copy[1])
        os.chmod(part, 0o600)
        os.replace(part, out)
    except BaseException:
        if part.exists():
            part.unlink()
        raise


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{size} B"
        value /= 1024
    return f"{size} B"


def cmd_backup(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    out = Path(args.out).resolve()
    work = Path(args.work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    target = resolve_db(root / "config", root)
    _, heads = code_revisions(root)
    manifest: dict = {
        "format": MANIFEST_FORMAT,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "version": _read_version(root),
        "engine": target.engine,
        "alembic_revisions": [],
        "code_heads": sorted(heads),
    }
    dump: Optional[Path] = None
    sqlite_copy: Optional[tuple[Path, str]] = None
    skip: set[str] = set()

    if target.engine == "mysql":
        conn = parse_mysql_url(target.url)
        tool = find_tool(root, DUMP_TOOLS)
        dump = work / SQL_DUMP_NAME
        log(f"mysqldump {conn.database} @ {conn.where}")
        proc = subprocess.run(
            [
                tool,
                *conn.client_args(),
                "--single-transaction",
                "--routines",
                "--events",
                "--no-tablespaces",
                f"--result-file={dump}",
                conn.database,
            ],
            env=conn.env(),
            check=False,
        )
        if proc.returncode != 0:
            raise BackupError(f"mysqldump 失败（exit={proc.returncode}），未写入备份")
        manifest["alembic_revisions"] = dump_revisions(dump)
    elif target.engine == "sqlite":
        db = target.sqlite_path
        if db is not None and db.is_file():
            arc = _arcname_in_root(db, root) or f"sqlite/{db.name}"
            copy = work / "sqlite" / db.name
            log(f"SQLite 在线备份 {db}")
            sqlite_backup(db, copy)
            skip.update(arc + suffix for suffix in ("", *SQLITE_SIDECARS))
            sqlite_copy = (copy, arc)
            manifest["sqlite"] = {"arcname": arc}
            manifest["alembic_revisions"] = sqlite_revisions(copy)
        else:
            warn(f"SQLite 库文件不存在（{db}），只打包 config/ 与 data/")
    elif target.url:
        warn("不支持备份该数据库引擎，只打包 config/ 与 data/")
    else:
        log("尚未选库，只打包 config/ 与 data/")

    write_archive(
        root, out, manifest=manifest, dump=dump, sqlite_copy=sqlite_copy, skip=frozenset(skip)
    )
    revs = ", ".join(manifest["alembic_revisions"]) or "-"
    log(f"已写入 {out}（{_human_size(out.stat().st_size)}；v{manifest['version']}，迁移 {revs}）")
    return 0


# ---------------------------------------------------------------- restore


def _inside(path: Path, base: Path) -> bool:
    return path == base or base in path.parents


def safe_extract(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:*") as tf:
        if hasattr(tarfile, "data_filter"):
            tf.extractall(dest, filter="data")
            return
        base = dest.resolve()
        members = []
        for member in tf.getmembers():
            if not (member.isfile() or member.isdir() or member.islnk()):
                continue
            if not _inside((base / member.name).resolve(), base):
                raise BackupError(f"归档成员越界：{member.name}")
            if member.islnk() and not _inside((base / member.linkname).resolve(), base):
                raise BackupError(f"归档硬链接越界：{member.name}")
            member.mode &= 0o755
            members.append(member)
        tf.extractall(dest, members=members)


def cmd_unpack(args: argparse.Namespace) -> int:
    archive = Path(args.archive)
    dest = Path(args.dest)
    if not archive.is_file():
        raise BackupError(f"找不到归档：{archive}")
    try:
        safe_extract(archive, dest)
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise BackupError(f"无法解开归档：{exc}") from exc
    if not any((dest / name).exists() for name in ("config", "data", "var", SQL_DUMP_NAME)):
        print(
            f"[{_tag}] ERROR: 归档里没有 config/、data/ 或 zhange.sql，不像 backup 产出的备份",
            file=sys.stderr,
        )
        return 3
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    work = Path(args.dir)
    manifest = _read_json(work / MANIFEST_NAME)
    if not manifest:
        log("旧格式备份（没有 manifest.json），跳过版本核对")
        return 0
    version = str(manifest.get("version") or "")
    engine = str(manifest.get("engine") or "") or "未选库"
    log(f"备份时间 {manifest.get('created_at') or '?'}，版本 v{version or '?'}，数据库 {engine}")
    current = _read_version(root)
    if version and current and version != current:
        warn(f"备份来自 v{version}，当前代码是 v{current}")
    revs = [str(r) for r in manifest.get("alembic_revisions") or []]
    known, heads = code_revisions(root)
    if revs and known:
        unknown = [r for r in revs if r not in known]
        if unknown:
            warn(
                f"备份库的迁移版本 {', '.join(unknown)} 不在当前代码里（备份比代码新），"
                f"恢复后应用会起不来；请先 update 到 v{version or '备份时的版本'} 或更新的版本"
            )
        elif set(revs) != heads:
            log(f"备份库迁移版本 {', '.join(revs)} 较旧；启动时会自动迁移到 {', '.join(sorted(heads))}")
    return 0


def _match_parent_owner(path: Path) -> None:
    if os.name != "posix" or os.geteuid() != 0:
        return
    st = path.parent.stat()
    os.chown(path, st.st_uid, st.st_gid)


def _place_sqlite(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".restore")
    shutil.copy2(src, tmp)
    for suffix in SQLITE_SIDECARS:
        stale = dest.with_name(dest.name + suffix)
        if stale.exists():
            stale.unlink()
    os.replace(tmp, dest)
    _match_parent_owner(dest)


def cmd_load_db(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    work = Path(args.dir).resolve()
    archived_config = work / "config"
    config_dir = archived_config if (archived_config / "database.json").is_file() else root / "config"
    target = resolve_db(config_dir, root)

    dump = work / SQL_DUMP_NAME
    if dump.is_file():
        if target.engine != "mysql":
            raise BackupError(
                "归档含 zhange.sql，但配置里不是 MySQL/MariaDB 连接（config/database.json 或 DATABASE_URL）"
            )
        conn = parse_mysql_url(target.url)
        tool = find_tool(root, CLIENT_TOOLS)
        log(f"导入 {conn.database} @ {conn.where}")
        with dump.open("rb") as fh:
            proc = subprocess.run(
                [tool, *conn.client_args(), conn.database], stdin=fh, env=conn.env(), check=False
            )
        if proc.returncode != 0:
            raise BackupError(f"mysql 导入失败（exit={proc.returncode}）")

    manifest = _read_json(work / MANIFEST_NAME)
    arc = str((manifest.get("sqlite") or {}).get("arcname") or "")
    if arc and not any(arc.startswith(top + "/") for top in DATA_TREES):
        src = (work / arc).resolve()
        if not _inside(src, work) or not src.is_file():
            raise BackupError(f"归档里的 SQLite 路径无效：{arc}")
        if target.engine != "sqlite" or target.sqlite_path is None:
            warn("归档带 SQLite 库，但配置里不是 SQLite，跳过")
        else:
            log(f"恢复 SQLite 库到 {target.sqlite_path}")
            _place_sqlite(src, target.sqlite_path)
    return 0


# ---------------------------------------------------------------- CLI


def main(argv: Optional[Sequence[str]] = None) -> int:
    global _tag
    parser = argparse.ArgumentParser(description="战鸽数据备份 / 恢复（由 backup / restore 脚本调用）")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("backup")
    p.add_argument("--root", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--work", required=True)
    p.set_defaults(func=cmd_backup, tag="backup")
    p = sub.add_parser("unpack")
    p.add_argument("--archive", required=True)
    p.add_argument("--dest", required=True)
    p.set_defaults(func=cmd_unpack, tag="restore")
    p = sub.add_parser("inspect")
    p.add_argument("--root", required=True)
    p.add_argument("--dir", required=True)
    p.set_defaults(func=cmd_inspect, tag="restore")
    p = sub.add_parser("load-db")
    p.add_argument("--root", required=True)
    p.add_argument("--dir", required=True)
    p.set_defaults(func=cmd_load_db, tag="restore")
    args = parser.parse_args(argv)
    _tag = args.tag
    try:
        return int(args.func(args))
    except BackupError as exc:
        print(f"[{_tag}] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
