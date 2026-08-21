"""Pelican Minecraft Egg 目录：内置预设 + 当前服启动项 + Application API 双向同步。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services import pelican_client as pelican
from app.services.integrations_config import (
    get_pelican_application_token,
    get_pelican_credentials,
)


class EggSyncError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


CATALOG: tuple[dict[str, Any], ...] = (
    {
        "key": "neoforge",
        "name": "NeoForge",
        "loaders": ("neoforge",),
        "include": ("neoforge",),
        "exclude": (),
    },
    {
        "key": "fabric",
        "name": "Fabric",
        "loaders": ("fabric",),
        "include": ("fabric",),
        "exclude": ("quilt", "forge", "neoforge"),
    },
    {
        "key": "quilt",
        "name": "Quilt",
        "loaders": ("quilt",),
        "include": ("quilt",),
        "exclude": (),
    },
    {
        "key": "forge",
        "name": "Forge",
        "loaders": ("forge",),
        "include": ("forge",),
        "exclude": ("neoforge", "fabric"),
    },
    {
        "key": "paper",
        "name": "Paper / Spigot",
        "loaders": (),
        "include": ("paper", "spigot", "purpur", "bukkit"),
        "exclude": ("forge", "fabric", "quilt"),
    },
    {
        "key": "vanilla",
        "name": "Vanilla",
        "loaders": (),
        "include": ("vanilla", "minecraft java"),
        "exclude": ("forge", "fabric", "paper", "quilt", "spigot"),
    },
)

_MC_HINTS = (
    "minecraft",
    "fabric",
    "forge",
    "neoforge",
    "quilt",
    "paper",
    "spigot",
    "purpur",
    "vanilla",
    "bukkit",
    "mohist",
    "arclight",
)

BOOT_WRAPPER = "bash zhange/boot.sh"
DEFAULT_JAVA = "java -Xms128M -XX:MaxRAMPercentage=95.0 -jar {{SERVER_JARFILE}}"
_VERSION_KEYS = ("MINECRAFT_VERSION", "MC_VERSION", "VERSION")
_LOADER_KEYS = {
    "fabric": ("FABRIC_LOADER_VERSION", "FABRIC_VERSION", "LOADER_VERSION"),
    "quilt": ("QUILT_LOADER_VERSION", "QUILT_VERSION", "LOADER_VERSION"),
    "forge": ("FORGE_VERSION", "LOADER_VERSION"),
    "neoforge": ("NEOFORGE_VERSION", "FORGE_VERSION", "LOADER_VERSION"),
}


def _blob(*parts: Any) -> str:
    return " ".join(str(p or "") for p in parts).lower()


def wrap_boot_command(command: str, *, fallback: str = "") -> str:
    cmd = (command or "").strip() or (fallback or "").strip() or DEFAULT_JAVA
    if "zhange/boot.sh" in cmd:
        return cmd
    return f"{BOOT_WRAPPER} {cmd}"


def infer_loader(blob: str) -> str:
    text = (blob or "").lower()
    if "neoforge" in text:
        return "neoforge"
    if "quilt" in text:
        return "quilt"
    if "fabric" in text:
        return "fabric"
    if "forge" in text:
        return "forge"
    return ""


def is_minecraft_egg(egg: dict[str, Any]) -> bool:
    text = _blob(
        egg.get("name"),
        egg.get("description"),
        egg.get("nest"),
        egg.get("startup"),
        " ".join(egg.get("docker_images") or []),
    )
    return any(hint in text for hint in _MC_HINTS)


def score_egg(egg: dict[str, Any], loader: str) -> int:
    loader = (loader or "").strip().lower()
    text = _blob(
        egg.get("name"),
        egg.get("description"),
        egg.get("nest"),
        egg.get("startup"),
        " ".join(egg.get("docker_images") or []),
        egg.get("key"),
    )
    preset = next((row for row in CATALOG if loader in row["loaders"]), None)
    if not preset:
        return 1 if is_minecraft_egg(egg) else 0
    if any(token in text for token in preset["exclude"]):
        return 0
    hits = sum(1 for token in preset["include"] if token in text)
    if not hits:
        return 0
    return 10 + hits * 3


def pick_egg(eggs: list[dict[str, Any]], loader: str) -> dict[str, Any] | None:
    ranked = sorted(
        ((score_egg(egg, loader), egg) for egg in eggs),
        key=lambda row: row[0],
        reverse=True,
    )
    if not ranked or ranked[0][0] <= 0:
        return None
    return ranked[0][1]


def overlay_loader_env(
    env: dict[str, str],
    *,
    mc_version: str,
    loader: str,
    loader_version: str,
) -> dict[str, str]:
    out = {str(key): "" if value is None else str(value) for key, value in (env or {}).items()}
    for key in _VERSION_KEYS:
        if key in out and mc_version:
            out[key] = mc_version
            break
    for key in _LOADER_KEYS.get(loader, ()):
        if key in out and loader_version:
            out[key] = loader_version
            break
    return out


def inspect_current_egg(base: str, token: str, uuid: str) -> dict[str, Any]:
    startup = pelican.get_startup(base, token, uuid)
    details = pelican.startup_details(startup)
    blob = _blob(
        details.get("command"),
        " ".join(details.get("docker_images") or []),
        " ".join(f"{row.get('key')}={row.get('value')}" for row in details.get("variables") or []),
    )
    images = list(details.get("docker_images") or [])
    return {
        **details,
        "inferred_loader": infer_loader(blob),
        "matches_loader": False,
        "egg_id": 0,
        "egg_name": "",
        "docker_image": images[0] if images else "",
        "desired_command": wrap_boot_command(str(details.get("command") or "")),
        "can_write": False,
    }


def _resolve_application_server(
    base: str,
    client_token: str,
    app_token: str,
    uuid: str,
) -> dict[str, Any]:
    internal_id = 0
    try:
        internal_id = pelican.parse_internal_id(pelican.get_server(base, client_token, uuid))
    except pelican.PelicanError:
        internal_id = 0
    if internal_id:
        try:
            return pelican.get_application_server(base, app_token, internal_id)
        except pelican.PelicanError:
            pass
    found = pelican.find_application_server(base, app_token, uuid)
    if not found:
        raise EggSyncError(
            "找不到这台服的 Application 记录，请确认 Application API Token 有权管理该服。",
            status_code=400,
        )
    return found


def collect_eggs(db: Session, *, loader: str = "") -> dict[str, Any]:
    """列出 Panel 里的 Minecraft Egg，供开服剧本草稿挑选；不读取当前服。"""
    base, _token, _uuid = get_pelican_credentials(db)
    app_token = get_pelican_application_token(db)
    application_configured = bool(app_token and base)
    current: dict[str, Any] = {
        "command": "",
        "docker_images": [],
        "variables": [],
        "inferred_loader": "",
        "matches_loader": False,
        "egg_id": 0,
        "egg_name": "",
        "docker_image": "",
        "desired_command": "",
        "can_write": application_configured,
    }
    error = ""
    panel_eggs: list[dict[str, Any]] = []
    if application_configured:
        try:
            raw = pelican.list_application_eggs(base, app_token)
            panel_eggs = [
                {**egg, "source": "pelican"} for egg in raw if is_minecraft_egg(egg)
            ]
        except pelican.PelicanError as exc:
            error = exc.message
    elif not base:
        error = "请到集成密钥填写 Panel 地址"
    elif not app_token:
        error = "列出 Egg 需要 Application API Token"

    catalog = [
        {
            "key": row["key"],
            "name": row["name"],
            "source": "catalog",
            "loaders": list(row["loaders"]),
        }
        for row in CATALOG
        if row["loaders"]
    ]
    recommended = pick_egg(panel_eggs, loader) if panel_eggs else None
    if recommended is None:
        hit = next((row for row in catalog if loader in row.get("loaders", [])), None)
        if hit:
            recommended = {**hit, "reason": "按加载器匹配内置目录"}
    elif loader:
        recommended = {
            **recommended,
            "source": "pelican",
            "reason": f"Panel 里最接近 {loader} 的 Egg",
        }
    return {
        "application_configured": application_configured,
        "current": current,
        "recommended": recommended,
        "eggs": panel_eggs,
        "catalog": catalog,
        "message": error,
    }


def apply_egg_variables(
    base: str,
    token: str,
    uuid: str,
    *,
    mc_version: str,
    loader: str,
    loader_version: str,
    variables: list[dict[str, str]],
) -> list[str]:
    """按当前 Egg 已有环境变量写入版本 / 加载器，不存在的键跳过。"""
    notes: list[str] = []
    have = {str(row.get("key") or "") for row in variables}
    pairs: list[tuple[str, str]] = []
    for key in _VERSION_KEYS:
        if key in have and mc_version:
            pairs.append((key, mc_version))
            break
    for key in _LOADER_KEYS.get(loader, ()):
        if key in have and loader_version:
            pairs.append((key, loader_version))
            break
    for key, value in pairs:
        try:
            pelican.update_startup_variable(base, token, uuid, key, value)
            notes.append(f"已写 Egg 变量 {key}={value}")
        except pelican.PelicanError as exc:
            notes.append(f"写 {key}：{exc.message}")
    return notes


def sync_server_egg(
    db: Session,
    *,
    loader: str,
    mc_version: str,
    loader_version: str,
    startup: str = "",
    egg_id: int | None = None,
) -> dict[str, Any]:
    """把战鸽选定的 Egg / 启动命令写回 Pelican，并读回当前值。"""
    base, token, uuid = get_pelican_credentials(db)
    app_token = get_pelican_application_token(db)
    if not pelican.pelican_configured(base, token, uuid):
        raise EggSyncError("未配置 Pelican Client Token / Server UUID")
    if not app_token:
        raise EggSyncError(
            "写 Egg 启动命令需要 Application API Token。请到集成密钥填写，权限含 servers 读写。",
            status_code=400,
        )

    info = collect_eggs(db, loader=loader)
    notes: list[str] = []
    recommended = info.get("recommended") if isinstance(info.get("recommended"), dict) else {}
    current = info.get("current") if isinstance(info.get("current"), dict) else {}
    panel_eggs = list(info.get("eggs") or [])

    try:
        app_server = _resolve_application_server(base, token, app_token, uuid)
    except pelican.PelicanError as exc:
        raise EggSyncError(exc.message, status_code=exc.status_code or 502) from exc

    target_id = int(egg_id or 0) or int(recommended.get("egg_id") or 0) or int(
        app_server.get("egg_id") or 0
    )
    if not target_id:
        raise EggSyncError("没有可写入的 Egg。请先在 Panel 创建 Minecraft Egg，并确认 Application Token 能列出。")

    target_egg = next((egg for egg in panel_eggs if egg.get("egg_id") == target_id), None)
    switching = target_id != int(app_server.get("egg_id") or 0)
    environment = dict(app_server.get("environment") or {})
    image = str(app_server.get("image") or "")
    base_command = str(app_server.get("startup") or current.get("command") or "")

    if switching:
        notes.append(f"切换 Egg 为 {target_egg.get('name') if target_egg else target_id}")
        try:
            egg_payload = pelican.get_application_egg(base, app_token, target_id)
            defaults = pelican.parse_egg_variable_defaults(egg_payload)
            egg_startup, egg_image = pelican.parse_egg_startup_and_image(egg_payload)
            if defaults:
                merged = dict(defaults)
                for key, value in environment.items():
                    if key in merged:
                        merged[key] = value
                environment = merged
            if egg_startup:
                base_command = egg_startup
            if egg_image:
                image = egg_image
        except pelican.PelicanError as exc:
            notes.append(f"读取目标 Egg：{exc.message}")
            if target_egg:
                if target_egg.get("startup"):
                    base_command = str(target_egg.get("startup") or base_command)
                images = list(target_egg.get("docker_images") or [])
                if images:
                    image = str(images[0])
    elif target_egg and not base_command:
        base_command = str(target_egg.get("startup") or "")

    if not image and target_egg:
        images = list(target_egg.get("docker_images") or [])
        if images:
            image = str(images[0])
    if not image:
        image = str(current.get("docker_image") or "")
    if not image:
        raise EggSyncError("当前 Egg 没有 Docker 镜像，无法写入启动配置")

    command = wrap_boot_command(startup, fallback=base_command)
    environment = overlay_loader_env(
        environment,
        mc_version=mc_version,
        loader=loader,
        loader_version=loader_version,
    )
    try:
        pelican.update_application_startup(
            base,
            app_token,
            int(app_server["id"]),
            startup=command,
            environment=environment,
            egg_id=target_id,
            image=image,
            skip_scripts=True,
        )
    except pelican.PelicanError as exc:
        raise EggSyncError(exc.message, status_code=exc.status_code or 502) from exc

    if switching:
        notes.append("已写入 Egg 与启动命令")
    else:
        notes.append("已同步启动命令")
    notes.append(f"启动：{command}")

    refreshed = collect_eggs(db, loader=loader)
    refreshed["ok"] = True
    refreshed["message"] = "；".join(notes)
    refreshed["boot_in_startup"] = "zhange/boot.sh" in command
    return refreshed
