"""server.properties 解析 / 脱敏 / 合并。"""

from __future__ import annotations

COMMON_PROPERTY_KEYS = (
    "motd",
    "max-players",
    "difficulty",
    "gamemode",
    "white-list",
    "enforce-whitelist",
    "view-distance",
    "simulation-distance",
    "pvp",
    "online-mode",
    "spawn-protection",
    "enable-command-block",
)

SECRET_PROPERTY_KEYS = frozenset({"rcon.password"})
RCON_DEFAULT_PORT = 25575


def redact_properties(props: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in (props or {}).items()
        if key not in SECRET_PROPERTY_KEYS
    }


def merge_rcon_properties(
    text: str,
    *,
    enabled: bool,
    port: int,
    password: str,
) -> str:
    listen = port if 1 <= int(port or 0) <= 65535 else RCON_DEFAULT_PORT
    updates = {
        "enable-rcon": "true" if enabled else "false",
        "rcon.port": str(listen),
        "broadcast-rcon-to-ops": "false",
    }
    secret = (password or "").strip()
    if secret:
        updates["rcon.password"] = secret
    elif not enabled:
        updates["rcon.password"] = ""
    return merge_properties(text, updates)


def parse_properties(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key:
            out[key] = value
    return out


def merge_properties(text: str, updates: dict[str, str]) -> str:
    """按原文件顺序改值；新键追加在末尾。"""
    updates_clean = {
        str(k).strip(): str(v)
        for k, v in (updates or {}).items()
        if str(k).strip()
    }
    if not text and not updates_clean:
        return ""
    seen: set[str] = set()
    lines: list[str] = []
    for raw_line in (text or "").splitlines():
        stripped = raw_line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, _, _ = stripped.partition("=")
            key = key.strip()
            if key in updates_clean:
                lines.append(f"{key}={updates_clean[key]}")
                seen.add(key)
                continue
        lines.append(raw_line)
    for key, value in updates_clean.items():
        if key not in seen:
            lines.append(f"{key}={value}")
            seen.add(key)
    return "\n".join(lines).rstrip() + ("\n" if lines else "")
