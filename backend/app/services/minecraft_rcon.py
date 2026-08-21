"""Minecraft Source RCON 客户端，以及 Spark / tick / Paper TPS 文本解析。"""

from __future__ import annotations

import re
import select
import socket
import struct
import threading
import time
from typing import Any

from app.services.minecraft_status import strip_section_codes

TYPE_RESPONSE = 0
TYPE_EXEC = 2
TYPE_AUTH = 3
_MAX_PACKET = 4096
_COMMANDS = ("spark tps", "tick query", "tps")
_CHUNK_COMMANDS = ("gc", "essentials:gc")
_DEAD_HINTS = ("关闭", "超时", "连接", "Reset", "refused", "timed out")


class MinecraftRconError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def pack_packet(req_id: int, ptype: int, body: str) -> bytes:
    payload = body.encode("utf-8") + b"\x00\x00"
    inner = struct.pack("<ii", req_id, ptype) + payload
    return struct.pack("<i", len(inner)) + inner


def _recvall(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise MinecraftRconError("连接已关闭")
        buf.extend(chunk)
    return bytes(buf)


def unpack_packet(sock: socket.socket) -> tuple[int, int, str]:
    header = _recvall(sock, 4)
    length = struct.unpack("<i", header)[0]
    if length < 10 or length > _MAX_PACKET:
        raise MinecraftRconError("RCON 包长度异常")
    data = _recvall(sock, length)
    req_id, ptype = struct.unpack("<ii", data[:8])
    body = data[8:-2].decode("utf-8", errors="replace") if length >= 10 else ""
    return req_id, ptype, body


def _enable_keepalive(sock: socket.socket) -> None:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    ioctl = getattr(socket, "SIO_KEEPALIVE_VALS", None)
    if ioctl is not None:
        try:
            sock.ioctl(ioctl, (1, 30_000, 10_000))
            return
        except OSError:
            pass
    proto = getattr(socket, "IPPROTO_TCP", 6)
    for name, value in (
        ("TCP_KEEPIDLE", 30),
        ("TCP_KEEPALIVE", 30),
        ("TCP_KEEPINTVL", 10),
        ("TCP_KEEPCNT", 3),
    ):
        opt = getattr(socket, name, None)
        if opt is None:
            continue
        try:
            sock.setsockopt(proto, opt, value)
        except OSError:
            pass


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, OSError):
        return True
    message = getattr(exc, "message", None) or str(exc)
    if "密码" in message or "未设置" in message or "端口无效" in message:
        return False
    return any(hint in message for hint in _DEAD_HINTS)


def _first_float(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)", text or "")
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def parse_perf_text(raw: str) -> dict[str, float | None]:
    """从 spark tps / tick query / Paper TPS 输出里抽出瞬时 TPS 与 MSPT。"""
    text = strip_section_codes(raw or "").replace("*", "")
    tps: float | None = None
    mspt: float | None = None

    header = re.search(r"TPS from last[^:\n]*:(.*)", text, re.I | re.S)
    if header:
        tps = _first_float(header.group(1))
    if tps is None:
        for match in re.finditer(
            r"(\d+(?:\.\d+)?)\s*(?:tps|ticks per second)",
            text,
            re.I,
        ):
            window = text[max(0, match.start() - 32) : match.start()].lower()
            if "target" in window:
                continue
            tps = float(match.group(1))
            break

    mean = re.search(
        r"(?:average time per tick|mean tick time)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*ms",
        text,
        re.I,
    )
    if mean:
        mspt = float(mean.group(1))
    if mspt is None:
        dur = re.search(
            r"(?:Tick durations|Full tick)[^\n]*\n?[^\n]*?"
            r"(\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?){3})",
            text,
            re.I,
        )
        if dur:
            parts = [p.strip() for p in dur.group(1).split("/") if p.strip()]
            pick = parts[1] if len(parts) >= 2 else (parts[0] if parts else "")
            mspt = _first_float(pick)

    if tps is None and mspt and mspt > 0:
        tps = min(20.0, round(1000.0 / mspt, 2))
    if tps is not None:
        tps = max(0.0, min(20.0, tps))
    if mspt is not None:
        mspt = max(0.0, mspt)
    return {"tps": tps, "mspt": mspt}


def parse_chunks_text(raw: str) -> int | None:
    """从 Essentials `/gc` 等文本里汇总已加载区块数。

    Spark / 原版 NeoForge 没有轻量 RCON 接口给出区块数；常见回落是
    EssentialsX 的 `World "x": N chunks, …`。找不到则返回 None。
    """
    text = strip_section_codes(raw or "").replace("\r", "\n")
    if not text.strip():
        return None
    totals = [
        int(match.group(1))
        for match in re.finditer(r"(\d+)\s+chunks?\b", text, re.I)
    ]
    if totals:
        return int(sum(totals))
    single = re.search(r"\bchunks?\s*[:=]\s*(\d+)\b", text, re.I)
    if single:
        return int(single.group(1))
    return None


class RconSession:
    """进程内复用一条已认证的 RCON TCP；凭证变化或对端断开后再建连。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sock: socket.socket | None = None
        self._key: tuple[str, int, str] | None = None
        self._req = 0
        self._preferred_command: str | None = None
        self._preferred_chunk_command: str | None = None
        self._chunks_unsupported = False

    def reset(self) -> None:
        with self._lock:
            self._drop()
            self._preferred_command = None
            self._preferred_chunk_command = None
            self._chunks_unsupported = False

    def connected(self) -> bool:
        with self._lock:
            return self._alive()

    def remember_perf_command(self, command: str) -> None:
        with self._lock:
            self._preferred_command = command

    def remember_chunk_command(self, command: str) -> None:
        with self._lock:
            self._preferred_chunk_command = command
            self._chunks_unsupported = False

    def mark_chunks_unsupported(self) -> None:
        with self._lock:
            self._chunks_unsupported = True

    @property
    def preferred_command(self) -> str | None:
        with self._lock:
            return self._preferred_command

    @property
    def preferred_chunk_command(self) -> str | None:
        with self._lock:
            return self._preferred_chunk_command

    @property
    def chunks_unsupported(self) -> bool:
        with self._lock:
            return self._chunks_unsupported

    def execute(
        self,
        host: str,
        port: int,
        password: str,
        command: str,
        *,
        timeout: float = 3.0,
    ) -> str:
        host = (host or "").strip()
        if not host:
            raise MinecraftRconError("未设置 RCON 地址")
        if not (1 <= int(port) <= 65535):
            raise MinecraftRconError("RCON 端口无效")
        secret = (password or "").strip()
        if not secret:
            raise MinecraftRconError("未设置 RCON 密码")
        with self._lock:
            retry = True
            while True:
                try:
                    sock = self._ensure(host, int(port), secret, timeout)
                    return self._run_command(sock, command, timeout)
                except MinecraftRconError as exc:
                    self._drop()
                    if retry and _retryable(exc):
                        retry = False
                        continue
                    raise
                except OSError as exc:
                    self._drop()
                    if retry:
                        retry = False
                        continue
                    raise MinecraftRconError(str(exc) or "无法连接 RCON") from exc

    def _next_id(self) -> int:
        self._req += 1
        if self._req <= 0 or self._req > 0x7FFFFFF0:
            self._req = 1
        return self._req

    def _drop(self) -> None:
        sock = self._sock
        self._sock = None
        self._key = None
        if sock is None:
            return
        try:
            sock.close()
        except OSError:
            pass

    def _alive(self) -> bool:
        sock = self._sock
        if sock is None:
            return False
        try:
            readable, _, _ = select.select([sock], [], [], 0)
            if not readable:
                return True
            peek = sock.recv(1, socket.MSG_PEEK)
            if peek:
                return True
        except (OSError, ValueError):
            pass
        self._drop()
        return False

    def _ensure(
        self,
        host: str,
        port: int,
        password: str,
        timeout: float,
    ) -> socket.socket:
        key = (host, port, password)
        if self._sock is not None and self._key == key and self._alive():
            return self._sock
        self._drop()
        sock = socket.create_connection((host, port), timeout=timeout)
        try:
            _enable_keepalive(sock)
            self._authenticate(sock, password, timeout)
        except Exception:
            try:
                sock.close()
            except OSError:
                pass
            raise
        self._sock = sock
        self._key = key
        return sock

    def _authenticate(self, sock: socket.socket, password: str, timeout: float) -> None:
        req_id = self._next_id()
        sock.settimeout(timeout)
        sock.sendall(pack_packet(req_id, TYPE_AUTH, password))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            got_id, ptype, _body = unpack_packet(sock)
            if got_id == -1:
                raise MinecraftRconError("RCON 密码错误")
            if ptype == TYPE_EXEC:
                return
        raise MinecraftRconError("RCON 认证超时")

    def _run_command(self, sock: socket.socket, command: str, timeout: float) -> str:
        req_id = self._next_id()
        sock.settimeout(timeout)
        sock.sendall(pack_packet(req_id, TYPE_EXEC, command.strip()))
        deadline = time.monotonic() + timeout
        bodies: list[str] = []
        while time.monotonic() < deadline:
            got_id, ptype, body = unpack_packet(sock)
            if got_id == -1:
                raise MinecraftRconError("RCON 密码错误")
            if got_id != req_id:
                continue
            bodies.append(body)
            if ptype != TYPE_RESPONSE:
                continue
            sock.settimeout(0.2)
            try:
                extra_id, _ptype, extra = unpack_packet(sock)
                if extra_id == req_id:
                    bodies.append(extra)
            except (TimeoutError, socket.timeout):
                pass
            except MinecraftRconError as exc:
                if "关闭" in exc.message:
                    self._drop()
            except OSError:
                self._drop()
            if self._sock is sock:
                sock.settimeout(timeout)
            return "".join(bodies).strip()
        raise MinecraftRconError("RCON 执行超时")


_SESSION = RconSession()


def reset_session() -> None:
    _SESSION.reset()


def session_connected() -> bool:
    return _SESSION.connected()


def rcon_exec(
    host: str,
    port: int,
    password: str,
    command: str,
    *,
    timeout: float = 3.0,
    persist: bool = True,
) -> str:
    session = _SESSION if persist else RconSession()
    try:
        return session.execute(host, port, password, command, timeout=timeout)
    finally:
        if not persist:
            session.reset()


_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,16}$")


def parse_list_names(raw: str) -> list[str]:
    """从 `list` 命令输出抽出玩家名（vanilla / Paper 一行名单）。"""
    text = strip_section_codes(raw or "").replace("\r", "\n").strip()
    if not text:
        return []
    idx = max(text.rfind(":"), text.rfind("："))
    payload = text[idx + 1 :] if idx >= 0 else ""
    payload = payload.replace(" and ", ",").replace("、", ",")
    names: list[str] = []
    seen: set[str] = set()
    for part in payload.split(","):
        name = part.strip()
        if not _NAME_RE.match(name):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def query_list(host: str, port: int, password: str, *, timeout: float = 3.0) -> list[str]:
    text = rcon_exec(host, port, password, "list", timeout=timeout)
    return parse_list_names(text)


def query_perf(host: str, port: int, password: str, *, timeout: float = 3.0) -> dict[str, Any]:
    last_error = "无法读取 TPS"
    commands = list(_COMMANDS)
    preferred = _SESSION.preferred_command
    if preferred in commands:
        commands = [preferred, *[item for item in commands if item != preferred]]
    for command in commands:
        try:
            text = rcon_exec(host, port, password, command, timeout=timeout)
        except MinecraftRconError as exc:
            last_error = exc.message
            if any(key in exc.message for key in ("密码", "连接", "超时", "地址", "端口")):
                raise
            continue
        except OSError as exc:
            last_error = str(exc) or "无法连接 RCON"
            raise MinecraftRconError(last_error) from exc
        parsed = parse_perf_text(text)
        if parsed["tps"] is not None or parsed["mspt"] is not None:
            _SESSION.remember_perf_command(command)
            return {**parsed, "raw": text, "command": command}
        last_error = "RCON 已连通，但输出里没有 TPS/MSPT（NeoForge 请安装 Spark）"
    raise MinecraftRconError(last_error)


def query_chunks(
    host: str, port: int, password: str, *, timeout: float = 3.0
) -> dict[str, Any] | None:
    """尽力读取已加载区块总数；Spark/原版无轻量命令时返回 None。"""
    if _SESSION.chunks_unsupported:
        return None
    commands = list(_CHUNK_COMMANDS)
    preferred = _SESSION.preferred_chunk_command
    if preferred in commands:
        commands = [preferred, *[item for item in commands if item != preferred]]
    for command in commands:
        try:
            text = rcon_exec(host, port, password, command, timeout=timeout)
        except MinecraftRconError as exc:
            if any(key in exc.message for key in ("密码", "连接", "超时", "地址", "端口")):
                raise
            continue
        except OSError:
            continue
        chunks = parse_chunks_text(text)
        if chunks is not None:
            _SESSION.remember_chunk_command(command)
            return {"chunks": chunks, "raw": text, "command": command}
    _SESSION.mark_chunks_unsupported()
    return None
