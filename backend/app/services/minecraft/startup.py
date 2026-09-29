"""读取服内核心与 Pelican 启动项，拼好且文件齐全时写回。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.ephemeral_kv import ephemeral_get, ephemeral_set
from app.services.integrations_config import get_pelican_credentials
from app.services.minecraft import pelican
from app.services.minecraft import startup_cmd as cmd
from app.services.minecraft.files import require_pelican

_BOOT = "minecraft:startup:booted"
_HOLD = "minecraft:startup:hold"
_TTL = 30 * 86400
_ARGS_FILE = "user_jvm_args.txt"


class StartupError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _names(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("name") or "") for row in rows if row.get("name")]


def _list_names(base: str, token: str, uuid: str, directory: str) -> list[dict[str, Any]]:
    try:
        return pelican.list_files(base, token, uuid, directory)
    except pelican.PelicanError:
        return []


def _unix_paths(base: str, token: str, uuid: str) -> list[str]:
    found: list[str] = []
    roots = (
        "libraries/net/neoforged/neoforge",
        "libraries/net/minecraftforge/forge",
    )
    for root in roots:
        for row in _list_names(base, token, uuid, root):
            if row.get("is_file"):
                continue
            version = str(row.get("name") or "")
            if not version:
                continue
            kids = _list_names(base, token, uuid, f"{root}/{version}")
            if any(str(item.get("name") or "") == "unix_args.txt" for item in kids):
                found.append(f"{root}/{version}/unix_args.txt")
    return found


def _read_args_file(base: str, token: str, uuid: str) -> str:
    try:
        return pelican.get_file_contents(base, token, uuid, _ARGS_FILE)
    except pelican.PelicanError:
        return ""


def _image_label(image: str) -> str:
    major = cmd.image_java_major(image)
    if major:
        return f"Java {major}"
    return image or "默认镜像"


def _observe_boot(power: str, command: str, live: str, *, wrote: bool) -> bool:
    """当前这条指令真正跑起来过才算启动过。改指令时若进程还在，要先停再开。"""
    if not command:
        return False
    if wrote:
        if ephemeral_get(_BOOT) == command:
            return True
        ephemeral_set(_BOOT, "", ttl_sec=_TTL)
        if power == "running":
            ephemeral_set(_HOLD, command, ttl_sec=_TTL)
        else:
            ephemeral_set(_HOLD, "", ttl_sec=_TTL)
        return False
    if live != command:
        return False
    if ephemeral_get(_HOLD) == command:
        if power in {"offline", "stopped"}:
            ephemeral_set(_HOLD, "", ttl_sec=_TTL)
        return False
    if power == "running":
        ephemeral_set(_BOOT, command, ttl_sec=_TTL)
        return True
    return ephemeral_get(_BOOT) == command


def _empty(configured: bool, message: str = "") -> dict[str, Any]:
    return {
        "pelican_configured": configured,
        "loader": "",
        "loader_label": "未识别",
        "loader_version": "",
        "mc_version": "",
        "loader_locked": False,
        "loader_choices": list(cmd.LOADER_CHOICES),
        "cores": [],
        "selected_id": "",
        "java_images": [],
        "java_image": "",
        "java_warning": "",
        "launch": "jar",
        "jvm_args": "",
        "user_jvm_args": "",
        "suggested_heap": cmd.suggest_heap_flags(0),
        "command": "",
        "complete": False,
        "synced": False,
        "message": message,
        "kind": "",
        "plugins_visible": False,
        "plugins_ready": False,
    }


def _view(
    *,
    detected: dict[str, Any],
    loader: str,
    choices: list[dict[str, Any]],
    selected: dict[str, Any] | None,
    details: dict[str, Any],
    memory_mb: int,
    power: str,
    jvm_args: str,
    user_jvm_args: str,
    java_image: str,
    wrote: bool,
    write_message: str,
) -> dict[str, Any]:
    locked = bool(detected.get("loader"))
    use_loader = detected.get("loader") or loader
    launch = str((selected or {}).get("launch") or "jar")
    jar = str((selected or {}).get("jar") or "")
    unix_args = str((selected or {}).get("unix_args") or "")
    server_args = str((selected or {}).get("server_args") or "")
    jars = set(detected.get("jars") or [])
    if launch == "args":
        command = cmd.build_args_command(unix_args)
        complete, why = cmd.assess_command(
            "args",
            jar="",
            jar_exists=False,
            unix_args=unix_args,
            unix_exists=bool(unix_args),
        )
    else:
        command = cmd.build_jar_command(jvm_args, jar, server_args)
        complete, why = cmd.assess_command(
            "jar",
            jar=jar,
            jar_exists=jar in jars,
            unix_args="",
            unix_exists=False,
        )
    live = cmd.live_startup_command(details)
    images = [str(item) for item in (details.get("docker_images") or []) if item]
    major = cmd.java_major_for_mc(str(detected.get("mc_version") or ""))
    warning = cmd.java_warning(java_image, major) if java_image and detected.get("mc_version") else ""
    kind = str((selected or {}).get("kind") or "")
    plugins_visible = kind in {"plugin", "hybrid"}
    has_slot = bool(cmd.startup_variable_key(details.get("variables") or []))
    synced = bool(complete and command and live == command and has_slot)
    ready = (
        _observe_boot(power, command, live, wrote=wrote) if complete and synced else False
    )
    if not plugins_visible:
        ready = False
    message = write_message or ("" if complete else why)
    if complete and not has_slot and "指令先不写入" not in message:
        message = "Egg 的启动模板还不是 {{STARTUP_CMD}}，指令先不写入"
        synced = False
    return {
        "pelican_configured": True,
        "loader": use_loader,
        "loader_label": cmd.loader_label(
            use_loader,
            str(detected.get("loader_version") or ""),
            str(detected.get("mc_version") or ""),
        ),
        "loader_version": str(detected.get("loader_version") or ""),
        "mc_version": str(detected.get("mc_version") or ""),
        "loader_locked": locked,
        "loader_choices": [] if locked else list(cmd.LOADER_CHOICES),
        "cores": [
            {
                "id": row["id"],
                "label": row["label"],
                "kind": row["kind"],
                "launch": row["launch"],
                "bundled": bool(row["bundled"]),
                "jar": row["jar"],
                "unix_args": row["unix_args"],
                "server_args": row["server_args"],
            }
            for row in choices
        ],
        "selected_id": str((selected or {}).get("id") or ""),
        "java_images": [{"image": image, "label": _image_label(image)} for image in images],
        "java_image": java_image,
        "java_warning": warning,
        "launch": launch if launch in {"jar", "args"} else "jar",
        "jvm_args": jvm_args,
        "user_jvm_args": user_jvm_args,
        "suggested_heap": cmd.suggest_heap_flags(memory_mb),
        "command": command,
        "complete": complete,
        "synced": synced,
        "message": message,
        "kind": kind if kind in {"mod", "plugin", "hybrid"} else "",
        "plugins_visible": plugins_visible,
        "plugins_ready": bool(plugins_visible and ready and synced),
    }


def _pick_selected(
    choices: list[dict[str, Any]],
    selected_id: str,
    live: str,
) -> dict[str, Any] | None:
    if selected_id:
        for row in choices:
            if row["id"] == selected_id:
                return row
    parsed = cmd.parse_command(live)
    if parsed["launch"] == "jar" and parsed["jar"]:
        for row in choices:
            if row.get("jar") == parsed["jar"]:
                return row
    if parsed["launch"] == "args" and parsed["unix_args"]:
        for row in choices:
            if row.get("unix_args") == parsed["unix_args"]:
                return row
    return choices[0] if choices else None


def read_startup(
    db: Session,
    *,
    loader: str = "",
    core_id: str = "",
    java_image: str = "",
    jvm_args: str | None = None,
    user_jvm_args: str | None = None,
    wrote: bool = False,
    write_message: str = "",
) -> dict[str, Any]:
    try:
        base, token, uuid = require_pelican(db)
    except Exception as exc:
        message = getattr(exc, "message", None) or "未配置 Pelican"
        return _empty(False, message)

    root = _list_names(base, token, uuid, "/")
    detected = cmd.detect_install(_names(root), _unix_paths(base, token, uuid))
    use_loader = str(detected.get("loader") or loader or "")
    choices = cmd.core_choices(detected, use_loader) if use_loader else []
    try:
        details = pelican.startup_details(pelican.get_startup(base, token, uuid))
    except pelican.PelicanError as exc:
        return _empty(True, exc.message)
    try:
        meta = pelican.parse_server_meta(pelican.get_server(base, token, uuid))
        memory_mb = int(meta.get("memory_limit_mb") or 0)
    except pelican.PelicanError:
        memory_mb = 0
    try:
        power = pelican.power_state_from_resources(
            pelican.get_resources(base, token, uuid)
        )
    except pelican.PelicanError:
        power = "unknown"
    file_args = user_jvm_args if user_jvm_args is not None else _read_args_file(base, token, uuid)
    live = cmd.live_startup_command(details)
    parsed = cmd.parse_command(live)
    selected = _pick_selected(choices, core_id, live)
    heap = cmd.suggest_heap_flags(memory_mb)
    if jvm_args is None:
        if parsed["launch"] == "jar" and parsed["jvm"]:
            jvm = parsed["jvm"]
        else:
            carried = cmd.heap_flags_from_text(file_args)
            jvm = carried or heap
    else:
        jvm = jvm_args
    if user_jvm_args is None and not str(file_args or "").strip():
        file_args = heap
    images = [str(item) for item in (details.get("docker_images") or []) if item]
    current_image = str(details.get("docker_image") or "") or (images[0] if images else "")
    chosen_image = java_image or current_image
    if chosen_image and chosen_image not in images and images:
        chosen_image = cmd.suggest_image(
            images, cmd.java_major_for_mc(str(detected.get("mc_version") or ""))
        ) or current_image
    return _view(
        detected=detected,
        loader=use_loader,
        choices=choices,
        selected=selected,
        details=details,
        memory_mb=memory_mb,
        power=power,
        jvm_args=jvm,
        user_jvm_args=str(file_args or ""),
        java_image=chosen_image,
        wrote=wrote,
        write_message=write_message,
    )


def apply_startup(
    db: Session,
    *,
    loader: str = "",
    core_id: str,
    java_image: str = "",
    jvm_args: str = "",
    user_jvm_args: str = "",
) -> dict[str, Any]:
    if not (core_id or "").strip():
        return read_startup(
            db,
            loader=loader,
            java_image=java_image,
            jvm_args=jvm_args,
            user_jvm_args=user_jvm_args,
        )
    base, token, uuid = require_pelican(db)
    preview = read_startup(
        db,
        loader=loader,
        core_id=core_id,
        java_image=java_image,
        jvm_args=jvm_args,
        user_jvm_args=user_jvm_args,
    )
    if not preview["pelican_configured"]:
        raise StartupError(preview["message"] or "未配置 Pelican")
    messages: list[str] = []
    wrote_command = False
    image = str(preview.get("java_image") or "")
    allowed = {row["image"] for row in preview.get("java_images") or []}
    if image and image in allowed:
        try:
            pelican.update_docker_image(base, token, uuid, image)
        except pelican.PelicanError as exc:
            messages.append(exc.message)
    if preview["launch"] == "args":
        try:
            pelican.write_file(base, token, uuid, _ARGS_FILE, str(user_jvm_args or ""))
        except pelican.PelicanError as exc:
            messages.append(exc.message)
    if preview["complete"] and preview["command"]:
        try:
            details = pelican.startup_details(pelican.get_startup(base, token, uuid))
        except pelican.PelicanError as exc:
            messages.append(exc.message)
            details = {"variables": []}
        key = cmd.startup_variable_key(details.get("variables") or [])
        if not key:
            messages.append("Egg 的启动模板还不是 {{STARTUP_CMD}}，指令先不写入")
        else:
            try:
                pelican.update_startup_variable(
                    base, token, uuid, key, preview["command"]
                )
                wrote_command = True
            except pelican.PelicanError as exc:
                messages.append(exc.message)
    return read_startup(
        db,
        loader=loader,
        core_id=core_id,
        java_image=java_image,
        jvm_args=jvm_args,
        user_jvm_args=user_jvm_args,
        wrote=wrote_command,
        write_message="；".join(messages),
    )
