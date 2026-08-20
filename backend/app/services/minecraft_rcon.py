"""Minecraft Source RCON 客户端，以及 Spark / tick / Paper TPS 文本解析。"""

from __future__ import annotations

import re
import socket
import struct
import time
from typing import Any

from app.services.minecraft_status import strip_section_codes

TYPE_RESPONSE = 0
TYPE_EXEC = 2
TYPE_AUTH = 3
_MAX_PACKET = 4096
_COMMANDS = ("spark tps", "tick query", "tps")


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


def _first_float(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)", text or "")
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def parse_perf_text(raw: str) -> dict[str, float | None]:
    """从 spark tps / tick query / Paper tps 输出里抽出瞬时 TPS 与 MSPT。"""
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


def rcon_exec(
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
    if not (password or "").strip():
        raise MinecraftRconError("未设置 RCON 密码")
    sock = socket.create_connection((host, int(port)), timeout=timeout)
    try:
        sock.settimeout(timeout)
        sock.sendall(pack_packet(1, TYPE_AUTH, password.strip()))
        deadline = time.monotonic() + timeout
        authed = False
        while time.monotonic() < deadline:
            req_id, ptype, _body = unpack_packet(sock)
            if req_id == -1:
                raise MinecraftRconError("RCON 密码错误")
            if ptype == TYPE_EXEC:
                authed = True
                break
        if not authed:
            raise MinecraftRconError("RCON 认证超时")
        sock.sendall(pack_packet(2, TYPE_EXEC, command.strip()))
        bodies: list[str] = []
        while time.monotonic() < deadline:
            req_id, ptype, body = unpack_packet(sock)
            if req_id == -1:
                raise MinecraftRconError("RCON 密码错误")
            if req_id != 2:
                continue
            bodies.append(body)
            if ptype == TYPE_RESPONSE:
                sock.settimeout(0.2)
                try:
                    extra_id, _ptype, extra = unpack_packet(sock)
                    if extra_id == 2:
                        bodies.append(extra)
                except (TimeoutError, socket.timeout, MinecraftRconError, OSError):
                    pass
                break
        return "".join(bodies).strip()
    finally:
        sock.close()


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
    for command in _COMMANDS:
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
            return {**parsed, "raw": text, "command": command}
        last_error = "RCON 已连通，但输出里没有 TPS/MSPT（NeoForge 请安装 Spark）"
    raise MinecraftRconError(last_error)
