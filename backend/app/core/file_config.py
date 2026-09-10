"""Install-root ``config/*.json`` — site settings written by the admin UI / setup wizard.

Not for user data. Secrets in these files are plaintext; the directory is chmod 700.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from app.core.paths import resolve_install_dir

logger = logging.getLogger("zhange.config")

CONFIG_NAMES = (
    "database",
    "app",
    "auth",
    "integrations",
    "email",
    "ocr",
    "jobs",
)
VERSION_KEY = "_version"
# 向导写库配置；模板里的 sqlite 默认值不能抢先落盘，否则会跳过选库。
SKIP_CREATE_FROM_EXAMPLE = frozenset({"database"})

_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_config_dir_override: Path | None = None


def set_config_dir_for_tests(path: Path | None) -> None:
    global _config_dir_override
    _config_dir_override = path
    clear_cache()


def config_dir() -> Path:
    if _config_dir_override is not None:
        return _config_dir_override
    return resolve_install_dir() / "config"


def example_config_dir(install: Path | None = None) -> Path:
    base = install if install is not None else resolve_install_dir()
    nested = base / "scripts" / "config.example"
    if nested.is_dir():
        return nested
    return base / "config.example"


def read_example(name: str, *, install: Path | None = None) -> dict[str, Any] | None:
    if name not in CONFIG_NAMES:
        raise ValueError(f"unknown config file: {name}")
    path = example_config_dir(install) / f"{name}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def config_schema_version(data: dict[str, Any] | None) -> int:
    if not data:
        return 0
    try:
        return int(data.get(VERSION_KEY) or 0)
    except (TypeError, ValueError):
        return 0


def config_path(name: str) -> Path:
    if name not in CONFIG_NAMES:
        raise ValueError(f"unknown config file: {name}")
    return config_dir() / f"{name}.json"


def clear_cache(name: str | None = None) -> None:
    if name is None:
        _cache.clear()
        return
    _cache.pop(name, None)


def ensure_config_dir() -> Path:
    path = config_dir()
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


def read_json(name: str) -> dict[str, Any] | None:
    path = config_path(name)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    hit = _cache.get(name)
    if hit and hit[0] == mtime:
        return dict(hit[1])
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw or "{}")
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("failed to read %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        return None
    _cache[name] = (mtime, dict(data))
    return dict(data)


def write_json(name: str, data: dict[str, Any]) -> None:
    ensure_config_dir()
    path = config_path(name)
    payload = dict(data)
    if VERSION_KEY not in payload:
        existing: dict[str, Any] | None = None
        try:
            raw = json.loads(path.read_text(encoding="utf-8") or "{}")
            if isinstance(raw, dict):
                existing = raw
        except (OSError, json.JSONDecodeError):
            existing = None
        if existing is not None and VERSION_KEY in existing:
            payload[VERSION_KEY] = existing[VERSION_KEY]
        else:
            example = read_example(name)
            if example is not None and VERSION_KEY in example:
                payload[VERSION_KEY] = example[VERSION_KEY]
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.replace(path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    clear_cache(name)


def parse_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            continue
        key, _, value = s.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip().strip('"').strip("'")
        out[key] = value
    return out


def sqlite_file_url(path: Path) -> str:
    return "sqlite:///" + path.resolve().as_posix()


def default_sqlite_path() -> Path:
    return resolve_install_dir() / "data" / "runtime" / "zhange.sqlite"


def default_sqlite_rel() -> str:
    install = resolve_install_dir()
    path = default_sqlite_path()
    try:
        return path.resolve().relative_to(install.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def ping_mysql_url(url: str, *, connect_timeout: int = 5) -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": connect_timeout},
    )
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    finally:
        engine.dispose()


def ping_sqlite_path(path: Path) -> None:
    from sqlalchemy import create_engine, text

    dest = path if path.is_absolute() else resolve_install_dir() / path
    if not dest.parent.exists():
        raise DatabaseSettingsError(f"目录不存在：{dest.parent.as_posix()}")
    engine = create_engine(sqlite_file_url(dest))
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    finally:
        engine.dispose()


class DatabaseSettingsError(ValueError):
    """Invalid engine / URL, or MySQL ping failed."""


def load_database_settings() -> dict[str, str]:
    data = read_json("database") or {}
    engine = str(data.get("engine") or "").strip().lower()
    path = str(data.get("path") or "").strip()
    url = str(data.get("url") or "").strip()
    if engine not in {"sqlite", "mysql"}:
        live = url or (os.environ.get("DATABASE_URL") or "").strip()
        if live.startswith("mysql"):
            engine = "mysql"
            url = url or live
        else:
            engine = "sqlite"
    if not path:
        path = default_sqlite_rel()
    return {"db_engine": engine, "db_path": path, "db_url": url}


def save_database_settings(*, engine: str, path: str = "", url: str = "") -> dict[str, str]:
    engine_name = (engine or "").strip().lower()
    if engine_name not in {"sqlite", "mysql"}:
        raise DatabaseSettingsError("数据库引擎只能是 sqlite 或 mysql")
    current = read_json("database") or {}
    if engine_name == "sqlite":
        rel = (path or "").strip() or default_sqlite_rel()
        current["engine"] = "sqlite"
        current["path"] = rel
        current["url"] = ""
        dest = Path(rel)
        if not dest.is_absolute():
            dest = resolve_install_dir() / dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        write_json("database", current)
        return load_database_settings()
    mysql_url = (url or "").strip()
    if not mysql_url.startswith("mysql"):
        raise DatabaseSettingsError("请填写 mysql+pymysql:// 连接串")
    try:
        ping_mysql_url(mysql_url)
    except DatabaseSettingsError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DatabaseSettingsError(f"无法连接数据库：{exc}") from exc
    current["engine"] = "mysql"
    current["url"] = mysql_url
    current["path"] = ""
    write_json("database", current)
    return load_database_settings()


def resolve_database_url() -> str:
    env = (os.environ.get("DATABASE_URL") or "").strip()
    if env:
        return env
    data = read_json("database") or {}
    engine = str(data.get("engine") or "").strip().lower()
    if engine == "sqlite":
        raw_path = str(data.get("path") or "").strip()
        if raw_path:
            path = Path(raw_path)
            if not path.is_absolute():
                path = resolve_install_dir() / path
            return sqlite_file_url(path)
        url = str(data.get("url") or "").strip()
        if url:
            return url
        return sqlite_file_url(default_sqlite_path())
    if engine in {"mysql", "mariadb", "postgresql"}:
        url = str(data.get("url") or "").strip()
        return url
    url = str(data.get("url") or "").strip()
    return url


def database_is_configured() -> bool:
    return bool(resolve_database_url())


def database_engine_name() -> str:
    url = resolve_database_url()
    if url.startswith("sqlite"):
        return "sqlite"
    if url.startswith("mysql"):
        return "mysql"
    if url.startswith("postgresql"):
        return "postgresql"
    data = read_json("database") or {}
    return str(data.get("engine") or "").strip().lower()
