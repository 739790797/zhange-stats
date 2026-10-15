"""用战鸽根目录里的 SteamCMD 更新已购买的《雨中冒险 2》。

可执行文件固定在安装根 ``steamcmd/``。没有就从 Valve 的安装包下载并解压，不走 apt / winget。
不指定安装目录，游戏落在该目录自己的 ``steamapps/common``。
"""

from __future__ import annotations

import io
import logging
import os
import re
import stat
import subprocess
import tarfile
import zipfile
from collections.abc import Iterator
from pathlib import Path

from app.core.http_client import HttpRequestError, http_request

log = logging.getLogger("zhange.ror2")

ROR2_APP_ID = "632360"
LANG_DIR_PARTS = ("Risk of Rain 2_Data", "StreamingAssets", "Language", "zh-CN")
UPDATE_TIMEOUT_SEC = 45 * 60
_ARCHIVE_MAX_BYTES = 8 * 1024 * 1024
_UNPACKED_MAX_BYTES = 64 * 1024 * 1024
_WIN_URL = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"
_LINUX_URL = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz"
_USER_AGENT = "zhange-stats/1.0"


class SteamCmdError(Exception):
    pass


_USERNAME = re.compile(r"^[^\s\x00-\x1f\"]{1,64}$")
RELOGIN_MESSAGE = "Steam 登录已失效，请在集成密钥里重新登录 Steam"


def steamcmd_ready(cfg: dict[str, str]) -> bool:
    return bool((cfg.get("steamcmd_username") or "").strip())


def clean_username(value: str) -> str:
    text = (value or "").strip()
    if _USERNAME.fullmatch(text) is None:
        raise SteamCmdError("账号无效")
    return text


def steamcmd_home() -> Path:
    from app.core.paths import resolve_install_dir

    home = resolve_install_dir() / "steamcmd"
    if home.is_symlink():
        raise SteamCmdError("steamcmd 目录不能是符号链接")
    return home


def lang_dir_from_steamcmd(executable: Path) -> Path:
    """游戏落在 SteamCMD 自己的 steamapps 里。"""
    return (
        executable.resolve().parent
        / "steamapps"
        / "common"
        / "Risk of Rain 2"
    ).joinpath(*LANG_DIR_PARTS)


def ensure_steamcmd() -> Path:
    """根目录已有可执行文件就用它，没有则下载官方安装包并解压。"""
    home = steamcmd_home()
    found = _existing_executable(home)
    if found is not None:
        return found
    log.info("战鸽根目录没有 SteamCMD，开始下载")
    home.mkdir(parents=True, exist_ok=True)
    if home.is_symlink():
        raise SteamCmdError("steamcmd 目录不能是符号链接")
    _install_bootstrap(home)
    found = _existing_executable(home)
    if found is None:
        raise SteamCmdError("SteamCMD 下载后仍找不到可执行文件")
    log.info("SteamCMD 已放到 %s", found)
    return found


def build_argv(executable: Path, username: str) -> list[str]:
    """更新只带账号。口令和令牌留在 SteamCMD 自己的登录缓存里。"""
    return [
        str(executable),
        "+@ShutdownOnFailedCommand",
        "1",
        "+@NoPromptForPassword",
        "1",
        "+login",
        clean_username(username),
        "+app_update",
        ROR2_APP_ID,
        "+quit",
    ]


def run_ror2_update(cfg: dict[str, str]) -> Path:
    executable = ensure_steamcmd()
    username = clean_username(cfg.get("steamcmd_username") or "")
    argv = build_argv(executable, username)
    log.info("steamcmd 更新雨中冒险2 app %s -> %s", ROR2_APP_ID, executable.parent)
    flags = {}
    if os.name == "nt":
        flags["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=UPDATE_TIMEOUT_SEC,
            check=False,
            **flags,
        )
    except subprocess.TimeoutExpired as exc:
        raise SteamCmdError("steamcmd 超时") from exc
    except OSError as exc:
        raise SteamCmdError("无法启动 steamcmd") from exc
    if completed.returncode != 0:
        output = (completed.stdout or "") + (completed.stderr or "")
        raise SteamCmdError(_update_failure(output, completed.returncode))
    return executable


def cached_account() -> str:
    """config.vdf 里记下的账号名。读不到令牌内容。"""
    home = steamcmd_home()
    config_dir = home / "config"
    path = config_dir / "config.vdf"
    if config_dir.is_symlink() or path.is_symlink() or not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:1_000_000]
    except OSError:
        return ""
    accounts = _top_keys(_block_after(text, "Accounts") or "")
    cache = _block_after(text, "ConnectCache") or ""
    if not accounts or '"' not in cache:
        return ""
    return accounts[0]


_UPDATE_PROGRESS = re.compile(
    r"progress:\s*([0-9]+(?:\.[0-9]+)?)\s*\(\s*(\d+)\s*/\s*(\d+)\s*\)"
)


def console_log_tail(max_lines: int = 30) -> tuple[str, dict[str, float | int | str] | None]:
    """最近一次 SteamCMD 控制台输出，以及其中最后一条进度。"""
    home = steamcmd_home()
    logs = home / "logs"
    path = logs / "console_log.txt"
    if logs.is_symlink() or path.is_symlink() or not path.is_file():
        return "", None
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            handle.seek(max(0, size - 48_000))
            raw = handle.read()
    except OSError:
        return "", None
    text = raw.decode("utf-8", "replace")
    if size > 48_000 and "\n" in text:
        text = text.split("\n", 1)[1]
    marker = text.rfind("Client version:")
    if marker >= 0:
        text = text[marker:]
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    progress = _latest_progress(lines)
    return "\n".join(lines[-max_lines:]), progress


def _latest_progress(lines: list[str]) -> dict[str, float | int | str] | None:
    for line in reversed(lines):
        match = _UPDATE_PROGRESS.search(line)
        if match is None:
            continue
        low = line.lower()
        if "verifying" in low:
            phase = "steamcmd_verify"
        elif "committing" in low:
            phase = "steamcmd_commit"
        else:
            phase = "steamcmd_download"
        return {
            "phase": phase,
            "percent": float(match.group(1)),
            "bytes": int(match.group(2)),
            "total_bytes": int(match.group(3)),
        }
    return None


def _update_failure(output: str, returncode: int) -> str:
    low = output.lower()
    if any(
        bit in low
        for bit in (
            "invalid password",
            "no password",
            "steam guard",
            "two-factor",
            "two factor",
            "logon denied",
            "password is required",
            "invalid login auth code",
        )
    ):
        return RELOGIN_MESSAGE
    tail = [line.strip() for line in output.splitlines() if line.strip()][-6:]
    detail = " | ".join(tail) if tail else f"退出码 {returncode}"
    return f"steamcmd 失败：{detail}"


def _block_after(text: str, key: str) -> str | None:
    marker = f'"{key}"'
    start = text.find(marker)
    if start < 0:
        return None
    brace = text.find("{", start + len(marker))
    if brace < 0:
        return None
    depth = 0
    for index in range(brace, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[brace + 1 : index]
    return None


def _top_keys(block: str) -> list[str]:
    keys: list[str] = []
    depth = 0
    index = 0
    while index < len(block):
        char = block[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth = max(0, depth - 1)
        elif char == '"' and depth == 0:
            end = block.find('"', index + 1)
            if end < 0:
                break
            keys.append(block[index + 1 : end])
            index = end
        index += 1
    return keys


def _executable_names() -> tuple[str, ...]:
    if os.name == "nt":
        return ("steamcmd.exe",)
    return ("steamcmd.sh", "steamcmd")


def _existing_executable(home: Path) -> Path | None:
    for name in _executable_names():
        candidate = home / name
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    return None


def _archive_url() -> str:
    return _WIN_URL if os.name == "nt" else _LINUX_URL


def _install_bootstrap(home: Path) -> None:
    try:
        response = http_request(
            "GET",
            _archive_url(),
            headers={"User-Agent": _USER_AGENT},
            timeout=30,
            max_bytes=_ARCHIVE_MAX_BYTES,
            deadline=120,
        )
    except HttpRequestError as exc:
        raise SteamCmdError("SteamCMD 下载失败") from exc
    if response.status_code != 200 or not response.content:
        raise SteamCmdError(f"SteamCMD 下载失败：HTTP {response.status_code}")
    budget = _UnpackBudget()
    if os.name == "nt":
        _extract_zip(home, response.content, budget)
    else:
        _extract_tar(home, response.content, budget)


class _UnpackBudget:
    def __init__(self) -> None:
        self.used = 0


def _extract_zip(home: Path, payload: bytes, budget: _UnpackBudget) -> None:
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise SteamCmdError("SteamCMD 压缩包无法打开") from exc
    with archive:
        for info in archive.infolist():
            if info.is_dir():
                _dest_for(home, info.filename).mkdir(parents=True, exist_ok=True)
                continue
            dest = _dest_for(home, info.filename)
            with archive.open(info) as src:
                _write_regular(dest, _chunks(src, budget))


def _extract_tar(home: Path, payload: bytes, budget: _UnpackBudget) -> None:
    try:
        archive = tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz")
    except tarfile.TarError as exc:
        raise SteamCmdError("SteamCMD 压缩包无法打开") from exc
    with archive:
        for member in archive.getmembers():
            if member.issym() or member.islnk():
                raise SteamCmdError("SteamCMD 压缩包含有符号链接")
            if member.isdir():
                _dest_for(home, member.name).mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise SteamCmdError("SteamCMD 压缩包含有不支持的条目")
            dest = _dest_for(home, member.name)
            src = archive.extractfile(member)
            if src is None:
                raise SteamCmdError("SteamCMD 压缩包无法打开")
            with src:
                _write_regular(dest, _chunks(src, budget))
            if dest.name in {"steamcmd.sh", "steamcmd"}:
                dest.chmod(dest.stat().st_mode | stat.S_IEXEC)


def _chunks(src: io.BufferedIOBase, budget: _UnpackBudget) -> Iterator[bytes]:
    while True:
        block = src.read(64 * 1024)
        if not block:
            break
        budget.used += len(block)
        if budget.used > _UNPACKED_MAX_BYTES:
            raise SteamCmdError("SteamCMD 压缩包过大")
        yield block


def _safe_relative(name: str) -> Path:
    normalized = name.replace("\\", "/").lstrip("/")
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise SteamCmdError("SteamCMD 压缩包路径不安全")
    return Path(*parts)


def _dest_for(home: Path, name: str) -> Path:
    rel = _safe_relative(name)
    dest = home.joinpath(rel)
    home_resolved = home.resolve()
    try:
        dest.resolve().relative_to(home_resolved)
    except ValueError as exc:
        raise SteamCmdError("SteamCMD 压缩包路径不安全") from exc
    current = home
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise SteamCmdError("steamcmd 目录里不能有符号链接")
    return dest


def _write_regular(dest: Path, chunks: Iterator[bytes]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".zhange-part")
    try:
        with partial.open("wb") as out:
            for block in chunks:
                out.write(block)
        os.replace(partial, dest)
    finally:
        if partial.exists():
            partial.unlink()


