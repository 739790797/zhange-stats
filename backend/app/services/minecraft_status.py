"""Minecraft Java 服务器列表 Ping（1.7+ JSON status）。"""

from __future__ import annotations

import json
import socket
import struct
from typing import Any


class MinecraftPingError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def pack_varint(value: int) -> bytes:
    if value < 0:
        value &= (1 << 32) - 1
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            break
    return bytes(out)


def read_varint(sock: socket.socket) -> int:
    result = 0
    shift = 0
    while True:
        chunk = sock.recv(1)
        if not chunk:
            raise MinecraftPingError("连接已关闭")
        byte = chunk[0]
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result
        shift += 7
        if shift >= 35:
            raise MinecraftPingError("VarInt 过长")


def pack_string(text: str) -> bytes:
    data = text.encode("utf-8")
    return pack_varint(len(data)) + data


_NAMED_COLORS = {
    "black": "0",
    "dark_blue": "1",
    "dark_green": "2",
    "dark_aqua": "3",
    "dark_red": "4",
    "dark_purple": "5",
    "gold": "6",
    "gray": "7",
    "dark_gray": "8",
    "blue": "9",
    "green": "a",
    "aqua": "b",
    "red": "c",
    "light_purple": "d",
    "yellow": "e",
    "white": "f",
}

_MAX_FAVICON_B64 = 96_000
_B64_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")


def flatten_chat(obj: Any) -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        return "".join(flatten_chat(x) for x in obj)
    if isinstance(obj, dict):
        extra = "".join(flatten_chat(x) for x in (obj.get("extra") or []))
        return str(obj.get("text") or "") + extra
    return str(obj)


def strip_section_codes(text: str) -> str:
    raw = text or ""
    out: list[str] = []
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == "§" and i + 1 < len(raw):
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out).strip()


def _hex_legacy(color: str) -> str:
    h = color.removeprefix("#")
    if len(h) != 6 or any(c not in "0123456789abcdefABCDEF" for c in h):
        return ""
    return "§x" + "".join(f"§{c}" for c in h)


def _style_prefix(style: dict[str, Any]) -> str:
    color = str(style.get("color") or "").strip()
    has_format = any(
        style.get(key)
        for key in ("bold", "italic", "underlined", "strikethrough", "obfuscated")
    )
    if not color and not has_format:
        return ""
    parts = ["§r"]
    if color.startswith("#"):
        hx = _hex_legacy(color)
        if hx:
            parts.append(hx)
    else:
        code = _NAMED_COLORS.get(color.lower())
        if code:
            parts.append(f"§{code}")
    if style.get("obfuscated"):
        parts.append("§k")
    if style.get("bold"):
        parts.append("§l")
    if style.get("italic"):
        parts.append("§o")
    if style.get("underlined"):
        parts.append("§n")
    if style.get("strikethrough"):
        parts.append("§m")
    return "".join(parts)


def flatten_legacy_motd(obj: Any, parent_style: dict[str, Any] | None = None) -> str:
    """JSON chat / 纯字符串 → 带 § 的 MOTD（给前端按客户端色码渲染）。"""
    style = dict(parent_style or {})
    if obj is None:
        return ""
    if isinstance(obj, str):
        return _style_prefix(style) + obj
    if isinstance(obj, list):
        return "".join(flatten_legacy_motd(item, style) for item in obj)
    if isinstance(obj, dict):
        for key in ("color", "bold", "italic", "underlined", "strikethrough", "obfuscated"):
            if key in obj:
                style[key] = obj[key]
        text = str(obj.get("text") or "")
        out = (_style_prefix(style) + text) if text else ""
        extra = obj.get("extra")
        if isinstance(extra, list):
            out += "".join(flatten_legacy_motd(item, style) for item in extra)
        return out
    return str(obj)


def sanitize_favicon(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    raw = "".join(value.split())
    prefix = "data:image/png;base64,"
    if raw.startswith(prefix):
        b64 = raw[len(prefix) :]
    elif raw.startswith("iVBORw"):
        b64 = raw
    else:
        return ""
    if not b64 or len(b64) > _MAX_FAVICON_B64:
        return ""
    if any(ch not in _B64_CHARS for ch in b64):
        return ""
    return prefix + b64


def parse_status_json(data: dict[str, Any]) -> dict[str, Any]:
    description = data.get("description")
    version = data.get("version") if isinstance(data.get("version"), dict) else {}
    players = data.get("players") if isinstance(data.get("players"), dict) else {}
    sample = players.get("sample") if isinstance(players.get("sample"), list) else []
    names: list[dict[str, str]] = []
    for row in sample:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        names.append({"name": name, "id": str(row.get("id") or "")})
    motd_raw = flatten_legacy_motd(description)
    motd = strip_section_codes(motd_raw)
    return {
        "motd": motd,
        "motd_raw": motd_raw,
        "favicon": sanitize_favicon(data.get("favicon")),
        "version_name": str(version.get("name") or ""),
        "players_online": int(players.get("online") or 0),
        "players_max": int(players.get("max") or 0),
        "players": names,
    }


def ping_server(host: str, port: int, *, timeout: float = 3.0) -> dict[str, Any]:
    host = (host or "").strip()
    if not host:
        raise MinecraftPingError("未设置公开地址")
    if port < 1 or port > 65535:
        raise MinecraftPingError("端口无效")

    handshake_payload = (
        pack_varint(0)
        + pack_varint(760)
        + pack_string(host)
        + struct.pack(">H", port)
        + pack_varint(1)
    )
    handshake = pack_varint(len(handshake_payload)) + handshake_payload
    status_req = pack_varint(1) + b"\x00"

    sock = socket.create_connection((host, port), timeout=timeout)
    try:
        sock.settimeout(timeout)
        sock.sendall(handshake + status_req)
        _length = read_varint(sock)
        packet_id = read_varint(sock)
        if packet_id != 0:
            raise MinecraftPingError("意外的 status 包")
        json_len = read_varint(sock)
        buf = bytearray()
        while len(buf) < json_len:
            chunk = sock.recv(json_len - len(buf))
            if not chunk:
                raise MinecraftPingError("status JSON 不完整")
            buf.extend(chunk)
        try:
            data = json.loads(buf.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise MinecraftPingError("status JSON 无效") from exc
        if not isinstance(data, dict):
            raise MinecraftPingError("status JSON 无效")
        parsed = parse_status_json(data)
        parsed["online"] = True
        return parsed
    finally:
        sock.close()
