#!/usr/bin/env python3
"""Ensure a local MariaDB is reachable and write ``config/database.json``.

Does **not** run inside the FastAPI process. Hand-run only (``install`` /
``run`` will not call this). Writes the URL into ``config/database.json``,
not a root ``.env``. Leftover ``.env`` is still read as a fallback.

Linux (root + apt): install mariadb-server and bootstrap a dedicated user.
Windows (amd64): portable MariaDB 11.4 under data/mariadb/ (no admin / winget).
Existing loopback server: CREATE DATABASE / USER only, do not overwrite a
hand-written database URL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import socket
import string
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen

MARIADB_VERSION = "11.4.13"
MARIADB_ZIP = f"mariadb-{MARIADB_VERSION}-winx64.zip"
MARIADB_SHA256 = "d62986d433eeebfde218560b276103831604a61e929e87f1a17f5aebd80257e2"
APP_USER = "zhange"
MAX_PACKET = 64 * 1024 * 1024


class ProvisionError(Exception):
    """User-facing install failure."""


@dataclass(frozen=True)
class DbUrl:
    user: str
    password: str
    host: str
    port: int
    database: str


def log(message: str, *, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    print(f"[mariadb] {message}", file=stream, flush=True)


def should_skip() -> bool:
    raw = (os.environ.get("ZHANGE_SKIP_MARIADB") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def is_loopback_host(host: str) -> bool:
    text = (host or "").strip().lower().strip("[]")
    return text in {"127.0.0.1", "localhost", "::1"}


def parse_database_url(url: str) -> DbUrl:
    text = (url or "").strip().strip('"').strip("'")
    if not text:
        raise ProvisionError("DATABASE_URL 为空")
    normalized = text.replace("mysql+pymysql://", "mysql://", 1)
    parsed = urlparse(normalized)
    if parsed.scheme not in {"mysql", "mariadb"}:
        raise ProvisionError(f"不支持的 DATABASE_URL 协议: {parsed.scheme or '(空)'}")
    database = (parsed.path or "").lstrip("/").split("?")[0]
    return DbUrl(
        user=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        host=(parsed.hostname or "127.0.0.1"),
        port=int(parsed.port or 3306),
        database=database,
    )


def build_database_url(
    user: str, password: str, host: str, port: int, database: str
) -> str:
    return (
        f"mysql+pymysql://{quote(user, safe='')}:{quote(password, safe='')}"
        f"@{host}:{int(port)}/{database}"
    )


def is_placeholder_url(url: str) -> bool:
    text = (url or "").strip()
    if not text:
        return True
    try:
        parsed = parse_database_url(text)
    except ProvisionError:
        return True
    return (
        parsed.user == "root"
        and parsed.password == "password"
        and is_loopback_host(parsed.host)
    )


def read_env_map(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def set_env_value(path: Path, key: str, value: str) -> None:
    """Rewrite a leftover ``.env`` key. New installs write ``config/database.json``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    prefix = f"{key}="
    replaced = False
    new_lines: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#") or not stripped.startswith(prefix):
            new_lines.append(line)
            continue
        new_lines.append(f"{key}={value}")
        replaced = True
    if not replaced:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        new_lines.append(f"{key}={value}")
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def read_configured_database_url(root: Path) -> str:
    env = (os.environ.get("DATABASE_URL") or "").strip()
    if env:
        return env
    url = str(read_json_file(root / "config" / "database.json").get("url") or "").strip()
    if url:
        return url
    return (read_env_map(root / ".env").get("DATABASE_URL") or "").strip()


def write_database_url(root: Path, url: str) -> None:
    path = root / "config" / "database.json"
    data = read_json_file(path)
    data["engine"] = "mysql"
    data["url"] = url
    if "_version" not in data:
        data["_version"] = 1
    write_json_file(path, data)


def sql_ident(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", name or ""):
        raise ProvisionError(f"非法标识符: {name!r}")
    return f"`{name}`"


def sql_str(value: str) -> str:
    return "'" + (value or "").replace("\\", "\\\\").replace("'", "\\'") + "'"


def generate_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(32))


def tcp_open(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def wait_port(host: str, port: int, timeout: float = 45.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if tcp_open(host, port, timeout=0.5):
            return True
        time.sleep(0.4)
    return False


def choose_database_name(env: dict[str, str], parsed: DbUrl | None, *, placeholder: bool) -> str:
    """Keep this tree's URL database name. APP_ENV does not pick a second catalog."""
    _ = (env, placeholder)
    if parsed and parsed.database:
        return parsed.database
    return "zhange_stats"


def zip_urls() -> list[str]:
    extra = (os.environ.get("ZHANGE_MARIADB_MIRROR") or "").strip()
    version_rel = f"mariadb-{MARIADB_VERSION}/winx64-packages/{MARIADB_ZIP}"
    urls: list[str] = []
    if extra:
        urls.append(extra if extra.lower().endswith(".zip") else extra.rstrip("/") + "/" + MARIADB_ZIP)
    urls.extend(
        [
            f"https://mirrors.tuna.tsinghua.edu.cn/mariadb/{version_rel}",
            f"https://mirrors.ustc.edu.cn/mariadb/{version_rel}",
            f"https://archive.mariadb.org/{version_rel}",
            f"https://archive.mariadb.org/mariadb-11.4/winx64-packages/{MARIADB_ZIP}",
        ]
    )
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    log(f"下载 {url}")
    request = Request(url, headers={"User-Agent": "zhange-stats-mariadb-provision"})
    last_report = 0
    with urlopen(request, timeout=60) as resp, tmp.open("wb") as handle:
        total = int(resp.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = resp.read(256 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            got += len(chunk)
            if got - last_report >= 8 * 1024 * 1024:
                if total:
                    log(f"已下载 {got // (1024 * 1024)}/{max(total // (1024 * 1024), 1)} MB")
                else:
                    log(f"已下载 {got // (1024 * 1024)} MB")
                last_report = got
    tmp.replace(dest)


def safe_extract_zip(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    resolved_dest = dest.resolve()
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            parts = Path(name).parts
            if name.startswith("/") or ".." in parts:
                raise ProvisionError(f"压缩包路径不合法: {name}")
            target = (dest / name).resolve()
            try:
                target.relative_to(resolved_dest)
            except ValueError as exc:
                raise ProvisionError(f"压缩包路径不合法: {name}") from exc
        zf.extractall(dest)


def find_bin(root: Path, names: tuple[str, ...]) -> Path | None:
    if not root.exists():
        return None
    found: list[Path] = []
    for name in names:
        found.extend(root.rglob(name))
    for path in found:
        if path.is_file() and path.parent.name.lower() == "bin":
            return path
    for path in found:
        if path.is_file():
            return path
    return None


def ini_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def write_my_ini(*, ini: Path, basedir: Path, datadir: Path, port: int) -> None:
    plugin = basedir / "lib" / "plugin"
    share = basedir / "share"
    lines = [
        "[mysqld]",
        f"basedir={ini_path(basedir)}",
        f"datadir={ini_path(datadir)}",
        f"port={int(port)}",
        "bind-address=127.0.0.1",
        "max_allowed_packet=64M",
        "character-set-server=utf8mb4",
        "collation-server=utf8mb4_unicode_ci",
        "innodb_buffer_pool_size=128M",
        "skip-log-bin",
    ]
    if plugin.is_dir():
        lines.append(f"plugin-dir={ini_path(plugin)}")
    if share.is_dir():
        lines.append(f"lc-messages-dir={ini_path(share)}")
    ini.parent.mkdir(parents=True, exist_ok=True)
    ini.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_secret_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_secret_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def start_mysqld(mysqld: Path, ini: Path, pid_file: Path, err_log: Path) -> None:
    err_log.parent.mkdir(parents=True, exist_ok=True)
    err_handle = err_log.open("ab", buffering=0)
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )
    proc = subprocess.Popen(
        [str(mysqld), f"--defaults-file={ini}"],
        stdout=err_handle,
        stderr=subprocess.STDOUT,
        cwd=str(mysqld.parent),
        creationflags=creationflags,
        close_fds=True,
    )
    pid_file.write_text(str(proc.pid) + "\n", encoding="ascii")
    log(f"已启动 mysqld pid={proc.pid}")


def ensure_portable_running(
    *,
    mysqld: Path,
    ini: Path,
    pid_file: Path,
    err_log: Path,
    host: str,
    port: int,
) -> None:
    if tcp_open(host, port):
        return
    if pid_file.is_file():
        try:
            old = int(pid_file.read_text(encoding="ascii").strip() or "0")
        except ValueError:
            old = 0
        if old and pid_alive(old) and wait_port(host, port, timeout=8):
            return
    start_mysqld(mysqld, ini, pid_file, err_log)
    if not wait_port(host, port, timeout=45):
        tail = ""
        if err_log.is_file():
            tail = err_log.read_text(encoding="utf-8", errors="replace")[-1500:]
        raise ProvisionError(f"mysqld 未在 :{port} 监听。日志:\n{tail}")


def find_mysql_client(extra_roots: list[Path] | None = None) -> Path | None:
    for name in ("mariadb", "mysql", "mariadb.exe", "mysql.exe"):
        found = shutil.which(name)
        if found:
            return Path(found)
    for root in extra_roots or []:
        hit = find_bin(root, ("mariadb.exe", "mysql.exe", "mariadb", "mysql"))
        if hit:
            return hit
    return None


def run_sql(
    client: Path,
    sql: str,
    *,
    user: str,
    password: str = "",
    host: str = "127.0.0.1",
    port: int = 3306,
    socket: bool = False,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    cmd = [str(client)]
    if socket:
        cmd += ["--protocol=socket", "-u", user]
    else:
        cmd += [
            "--protocol=tcp",
            "-h",
            host,
            "-P",
            str(int(port)),
            "-u",
            user,
        ]
    cmd += ["-N", "-s", "-e", sql]
    env = os.environ.copy()
    if password:
        env["MYSQL_PWD"] = password
    else:
        env.pop("MYSQL_PWD", None)
    return subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def ping_creds(
    host: str,
    port: int,
    user: str,
    password: str,
    *,
    clients: list[Path] | None = None,
) -> bool:
    try:
        import pymysql
    except ImportError:
        pymysql = None  # type: ignore[assignment]
    if pymysql is not None:
        try:
            conn = pymysql.connect(
                host=host,
                port=int(port),
                user=user,
                password=password,
                connect_timeout=3,
                charset="utf8mb4",
            )
            try:
                conn.ping(reconnect=False)
            finally:
                conn.close()
            return True
        except Exception:
            pass
    for client in clients or []:
        result = run_sql(
            client,
            "SELECT 1",
            user=user,
            password=password,
            host=host,
            port=port,
        )
        if result.returncode == 0:
            return True
    return False


def ping_url(url: str, *, clients: list[Path] | None = None) -> bool:
    try:
        parsed = parse_database_url(url)
    except ProvisionError:
        return False
    return ping_creds(
        parsed.host,
        parsed.port,
        parsed.user,
        parsed.password,
        clients=clients,
    )


def ping_socket_root(client: Path) -> bool:
    result = run_sql(client, "SELECT 1", user="root", socket=True)
    return result.returncode == 0


def bootstrap_sql(database: str, app_user: str, app_password: str) -> str:
    db = sql_ident(database)
    if not re.fullmatch(r"[A-Za-z0-9_]+", app_user):
        raise ProvisionError(f"非法用户名: {app_user!r}")
    user = sql_str(app_user)
    password = sql_str(app_password)
    return (
        f"CREATE DATABASE IF NOT EXISTS {db} "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        f"CREATE USER IF NOT EXISTS {user}@'127.0.0.1' IDENTIFIED BY {password};"
        f"CREATE USER IF NOT EXISTS {user}@'localhost' IDENTIFIED BY {password};"
        f"ALTER USER {user}@'127.0.0.1' IDENTIFIED BY {password};"
        f"ALTER USER {user}@'localhost' IDENTIFIED BY {password};"
        f"GRANT ALL PRIVILEGES ON {db}.* TO {user}@'127.0.0.1';"
        f"GRANT ALL PRIVILEGES ON {db}.* TO {user}@'localhost';"
        "FLUSH PRIVILEGES;"
        f"SET GLOBAL max_allowed_packet = {MAX_PACKET};"
    )


def exec_bootstrap(
    client: Path,
    sql: str,
    *,
    user: str,
    password: str = "",
    host: str = "127.0.0.1",
    port: int = 3306,
    socket: bool = False,
) -> None:
    result = run_sql(
        client,
        sql,
        user=user,
        password=password,
        host=host,
        port=port,
        socket=socket,
        timeout=60,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise ProvisionError(f"初始化库/用户失败: {detail or 'mysql 退出码 ' + str(result.returncode)}")


def linux_has_server_pkg() -> bool:
    if not shutil.which("dpkg"):
        return False
    result = subprocess.run(
        ["dpkg", "-s", "mariadb-server"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True
    result = subprocess.run(
        ["dpkg", "-s", "mysql-server"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def linux_install_mariadb() -> bool:
    """Install via apt. Returns True if this call performed the install."""
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        raise ProvisionError("自动安装 MariaDB 需要 root：sudo bash scripts/linux/install.sh")
    if not shutil.which("apt-get"):
        raise ProvisionError("当前系统没有 apt，请自备 MariaDB 并填写 config/database.json")
    already = linux_has_server_pkg()
    if already:
        log("已检测到 mariadb/mysql 软件包")
        _linux_start_service()
        return False
    log("apt 安装 mariadb-server")
    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"
    update = subprocess.run(
        ["apt-get", "update"],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if update.returncode != 0:
        raise ProvisionError(update.stderr.strip() or "apt-get update 失败")
    install = subprocess.run(
        ["apt-get", "install", "-y", "mariadb-server", "mariadb-client"],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if install.returncode != 0:
        raise ProvisionError(install.stderr.strip() or "apt-get install mariadb-server 失败")
    _linux_start_service()
    return True


def _linux_start_service() -> None:
    if not shutil.which("systemctl"):
        return
    for name in ("mariadb", "mysql", "mariadb.service", "mysql.service"):
        subprocess.run(
            ["systemctl", "enable", "--now", name],
            check=False,
            capture_output=True,
        )


def write_linux_tune_cnf() -> None:
    path = Path("/etc/mysql/mariadb.conf.d/zz-zhange.cnf")
    directory = path.parent
    if not directory.is_dir():
        alt = Path("/etc/mysql/conf.d/zz-zhange.cnf")
        if alt.parent.is_dir():
            path = alt
        else:
            return
    if path.is_file():
        return
    path.write_text(
        "[mysqld]\n"
        "bind-address=127.0.0.1\n"
        "max_allowed_packet=64M\n"
        "character-set-server=utf8mb4\n"
        "collation-server=utf8mb4_unicode_ci\n",
        encoding="utf-8",
    )
    log(f"已写入 {path}")
    if shutil.which("systemctl"):
        subprocess.run(
            ["systemctl", "restart", "mariadb"],
            check=False,
            capture_output=True,
        )
        subprocess.run(
            ["systemctl", "restart", "mysql"],
            check=False,
            capture_output=True,
        )


def windows_machine_ok() -> bool:
    machine = platform.machine().lower()
    return machine in {"amd64", "x86_64"}


def portable_layout(root: Path) -> dict[str, Path]:
    new = root / "data" / "mariadb"
    old = root / "var" / "mariadb"
    if old.is_dir() and not new.exists():
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)
    base = new
    return {
        "base": base,
        "dist": base / "dist",
        "data": base / "data",
        "ini": base / "my.ini",
        "pid": base / "mysqld.pid",
        "err": base / "mysqld.err",
        "zip": base / "tmp" / MARIADB_ZIP,
        "provision": base / "provision.json",
    }


def ensure_windows_dist(paths: dict[str, Path]) -> Path:
    mysqld = find_bin(paths["dist"], ("mysqld.exe", "mariadbd.exe"))
    if mysqld:
        return mysqld.parent.parent
    if not windows_machine_ok():
        raise ProvisionError(
            "当前 Windows 不是 amd64，便携 MariaDB 无对应包。请自备库并填写 config/database.json"
        )
    archive = paths["zip"]
    if not archive.is_file() or sha256_file(archive) != MARIADB_SHA256:
        if archive.is_file():
            archive.unlink()
        last_error = "没有可用镜像"
        for url in zip_urls():
            try:
                download_file(url, archive)
                digest = sha256_file(archive)
                if digest != MARIADB_SHA256:
                    archive.unlink(missing_ok=True)
                    last_error = f"校验失败 {digest}"
                    continue
                last_error = ""
                break
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                archive.unlink(missing_ok=True)
                log(f"镜像失败: {url} ({exc})")
        if last_error:
            raise ProvisionError(
                f"无法下载 MariaDB {MARIADB_VERSION} Windows 包。{last_error}。"
                "可设置 ZHANGE_MARIADB_MIRROR 为 zip 地址，或自备库填写 config/database.json"
            )
    log("解压 MariaDB")
    if paths["dist"].exists():
        shutil.rmtree(paths["dist"])
    paths["dist"].mkdir(parents=True, exist_ok=True)
    safe_extract_zip(archive, paths["dist"])
    mysqld = find_bin(paths["dist"], ("mysqld.exe", "mariadbd.exe"))
    if not mysqld:
        raise ProvisionError("解压后未找到 mysqld.exe")
    return mysqld.parent.parent


def init_windows_datadir(basedir: Path, datadir: Path, root_password: str, port: int) -> None:
    if (datadir / "mysql").is_dir():
        return
    datadir.mkdir(parents=True, exist_ok=True)
    install_db = find_bin(
        basedir,
        ("mariadb-install-db.exe", "mysql_install_db.exe"),
    )
    if install_db is None:
        raise ProvisionError("发行包里没有 mariadb-install-db.exe")
    log("初始化数据目录")
    result = subprocess.run(
        [
            str(install_db),
            f"--datadir={datadir}",
            f"--password={root_password}",
            f"--port={int(port)}",
        ],
        cwd=str(install_db.parent),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not (datadir / "mysql").is_dir():
        detail = (result.stderr or result.stdout or "").strip()
        raise ProvisionError(f"mariadb-install-db 失败: {detail or result.returncode}")


def pick_windows_port(preferred: int) -> int:
    override = (os.environ.get("ZHANGE_MARIADB_PORT") or "").strip()
    if override:
        return int(override)
    if not tcp_open("127.0.0.1", preferred):
        return preferred
    for port in (3307, 3308, 3309):
        if not tcp_open("127.0.0.1", port):
            log(f"本机 :{preferred} 已被占用，便携实例改用 :{port}")
            return port
    raise ProvisionError("3306–3309 均被占用，请关闭冲突服务或设置 ZHANGE_MARIADB_PORT")


def provision_windows_portable(
    root: Path,
    *,
    database: str,
    rewrite_url: bool,
    clients: list[Path],
) -> None:
    paths = portable_layout(root)
    secret = load_secret_json(paths["provision"])
    basedir = ensure_windows_dist(paths)
    mysqld = find_bin(basedir, ("mysqld.exe", "mariadbd.exe"))
    client = find_bin(basedir, ("mariadb.exe", "mysql.exe"))
    if mysqld is None or client is None:
        raise ProvisionError("便携 MariaDB 缺少 mysqld / mysql 客户端")
    extra_clients = [client, *clients]
    port = int(secret.get("port") or pick_windows_port(3306))
    if (paths["data"] / "mysql").is_dir() and tcp_open("127.0.0.1", port):
        pass
    elif (paths["data"] / "mysql").is_dir():
        pass
    else:
        port = pick_windows_port(3306)
    root_password = str(secret.get("root_password") or generate_password())
    app_password = str(secret.get("app_password") or generate_password())
    init_windows_datadir(basedir, paths["data"], root_password, port)
    write_my_ini(ini=paths["ini"], basedir=basedir, datadir=paths["data"], port=port)
    ensure_portable_running(
        mysqld=mysqld,
        ini=paths["ini"],
        pid_file=paths["pid"],
        err_log=paths["err"],
        host="127.0.0.1",
        port=port,
    )
    if not ping_creds("127.0.0.1", port, "root", root_password, clients=extra_clients):
        raise ProvisionError("便携 MariaDB 已启动，但 root 密码不匹配（见 data/mariadb/provision.json）")
    exec_bootstrap(
        client,
        bootstrap_sql(database, APP_USER, app_password),
        user="root",
        password=root_password,
        host="127.0.0.1",
        port=port,
    )
    write_secret_json(
        paths["provision"],
        {
            "version": MARIADB_VERSION,
            "port": port,
            "database": database,
            "app_user": APP_USER,
            "root_password": root_password,
            "app_password": app_password,
        },
    )
    new_url = build_database_url(APP_USER, app_password, "127.0.0.1", port, database)
    if rewrite_url:
        write_database_url(root, new_url)
        log(f"已写入 config/database.json（{APP_USER}@127.0.0.1:{port}/{database}）")
    if not ping_creds("127.0.0.1", port, APP_USER, app_password, clients=extra_clients):
        raise ProvisionError("应用账号创建后仍无法连接")


def provision_linux(
    root: Path,
    *,
    database: str,
    rewrite_url: bool,
    clients: list[Path],
) -> None:
    installed_now = False
    client = clients[0] if clients else None
    socket_ok = bool(client and ping_socket_root(client))
    if not socket_ok and not tcp_open("127.0.0.1", 3306):
        installed_now = linux_install_mariadb()
        deadline = time.time() + 40
        while time.time() < deadline:
            client = find_mysql_client() or client
            if client and ping_socket_root(client):
                socket_ok = True
                break
            if tcp_open("127.0.0.1", 3306):
                break
            time.sleep(0.5)
        clients = [p for p in [find_mysql_client(), *(clients or [])] if p]
        client = clients[0] if clients else None
        socket_ok = bool(client and ping_socket_root(client))
    elif not socket_ok:
        _linux_start_service()
        client = find_mysql_client() or client
        socket_ok = bool(client and ping_socket_root(client))
    if client is None:
        raise ProvisionError("未找到 mysql/mariadb 客户端")
    if not socket_ok:
        raise ProvisionError(
            "本机 :3306 已有服务，但无法用 unix_socket 以 root 登录。"
            "请填写正确的 config/database.json，或 ZHANGE_SKIP_MARIADB=1"
        )
    if installed_now:
        write_linux_tune_cnf()
        if not wait_port("127.0.0.1", 3306, timeout=30) and not ping_socket_root(client):
            raise ProvisionError("MariaDB 服务启动后仍不可用")
    app_password = generate_password()
    exec_bootstrap(
        client,
        bootstrap_sql(database, APP_USER, app_password),
        user="root",
        socket=True,
    )
    new_url = build_database_url(APP_USER, app_password, "127.0.0.1", 3306, database)
    if rewrite_url:
        write_database_url(root, new_url)
        log(f"已写入 config/database.json（{APP_USER}@127.0.0.1:3306/{database}）")
    extra = [client]
    if not ping_creds("127.0.0.1", 3306, APP_USER, app_password, clients=extra):
        raise ProvisionError("应用账号创建后仍无法连接")


def try_reuse_loopback(
    root: Path,
    *,
    port: int,
    database: str,
    rewrite_url: bool,
    clients: list[Path],
) -> bool:
    if not tcp_open("127.0.0.1", port):
        return False
    pairs = [("root", "password"), ("root", "")]
    for user, password in pairs:
        if not ping_creds("127.0.0.1", port, user, password, clients=clients):
            continue
        client = clients[0] if clients else find_mysql_client()
        if client is None:
            try:
                import pymysql
            except ImportError as exc:
                raise ProvisionError("已有本机库可登录，但缺少 mysql 客户端与 pymysql") from exc
            app_password = generate_password()
            conn = pymysql.connect(
                host="127.0.0.1",
                port=port,
                user=user,
                password=password,
                connect_timeout=5,
                charset="utf8mb4",
                autocommit=True,
            )
            try:
                with conn.cursor() as cur:
                    for statement in bootstrap_sql(database, APP_USER, app_password).split(";"):
                        text = statement.strip()
                        if text:
                            cur.execute(text)
            finally:
                conn.close()
            if rewrite_url:
                write_database_url(
                    root,
                    build_database_url(APP_USER, app_password, "127.0.0.1", port, database),
                )
                log(f"已复用本机 :{port} 并写入 config/database.json")
            return True
        app_password = generate_password()
        exec_bootstrap(
            client,
            bootstrap_sql(database, APP_USER, app_password),
            user=user,
            password=password,
            host="127.0.0.1",
            port=port,
        )
        if rewrite_url:
            write_database_url(
                root,
                build_database_url(APP_USER, app_password, "127.0.0.1", port, database),
            )
            log(f"已复用本机 :{port} 并写入 config/database.json")
        return True
    return False


def resolve_root(explicit: str) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    here = Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        if (candidate / "VERSION").is_file():
            return candidate
    return here.parents[1]


def provision(root: Path) -> None:
    url = read_configured_database_url(root)
    env = read_env_map(root / ".env")
    paths = portable_layout(root)
    clients = [p for p in [find_mysql_client([paths["dist"]])] if p]
    if should_skip():
        log("ZHANGE_SKIP_MARIADB=1，跳过自动安装")
        return
    if url and not is_placeholder_url(url) and ping_url(url, clients=clients):
        log("数据库已可连接，跳过")
        return

    placeholder = is_placeholder_url(url)
    parsed: DbUrl | None = None
    if url:
        try:
            parsed = parse_database_url(url)
        except ProvisionError:
            parsed = None

    if parsed and not placeholder and not is_loopback_host(parsed.host):
        raise ProvisionError(
            f"无法连接 {parsed.host}:{parsed.port}（非本机），未自动安装。请修正 config/database.json"
        )

    if parsed and not placeholder and is_loopback_host(parsed.host):
        if tcp_open(parsed.host, parsed.port):
            raise ProvisionError(
                f"本机 :{parsed.port} 已有服务，但当前连接串连不上。"
                "请改正 config/database.json，或设置 ZHANGE_SKIP_MARIADB=1"
            )
        paths = portable_layout(root)
        if (paths["data"] / "mysql").is_dir():
            basedir = find_bin(paths["dist"], ("mysqld.exe", "mariadbd.exe"))
            if basedir:
                write_my_ini(
                    ini=paths["ini"],
                    basedir=basedir.parent.parent,
                    datadir=paths["data"],
                    port=parsed.port,
                )
                ensure_portable_running(
                    mysqld=basedir,
                    ini=paths["ini"],
                    pid_file=paths["pid"],
                    err_log=paths["err"],
                    host="127.0.0.1",
                    port=parsed.port,
                )
                if ping_url(url, clients=clients):
                    log("已拉起本机便携 MariaDB")
                    return
        if sys.platform.startswith("linux"):
            _linux_start_service()
            if wait_port("127.0.0.1", parsed.port, timeout=15) and ping_url(url, clients=clients):
                log("已拉起系统 MariaDB")
                return
        raise ProvisionError(
            "当前连接串不是空/占位值且库未运行。请先启动已有 MariaDB，"
            "或清空 config/database.json 的 url 后再自动安装"
        )

    database = choose_database_name(env, parsed, placeholder=placeholder)
    rewrite_url = placeholder or not url
    port = parsed.port if parsed else 3306

    if try_reuse_loopback(
        root,
        port=port,
        database=database,
        rewrite_url=rewrite_url,
        clients=clients,
    ):
        return

    if os.name == "nt":
        provision_windows_portable(
            root,
            database=database,
            rewrite_url=rewrite_url,
            clients=clients,
        )
        return
    if sys.platform.startswith("linux"):
        provision_linux(
            root,
            database=database,
            rewrite_url=rewrite_url,
            clients=clients,
        )
        return
    raise ProvisionError("仅支持 Linux apt 安装或 Windows 便携包。请自备 MariaDB 并填写 config/database.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="为本机准备 MariaDB 并写回 config/database.json")
    parser.add_argument("--root", default="", help="安装根（默认仓库根）")
    args = parser.parse_args(argv)
    try:
        provision(resolve_root(args.root))
    except ProvisionError as exc:
        log(str(exc), error=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
