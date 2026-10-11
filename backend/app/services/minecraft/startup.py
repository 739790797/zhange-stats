"""读取服内核心与 Pelican 启动项，拼好且文件齐全时写回。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.ephemeral_kv import ephemeral_get, ephemeral_set
from app.services.integrations_config import get_pelican_application_token
from app.services.minecraft import pelican
from app.services.minecraft import startup_cmd as cmd
from app.services.minecraft.files import require_pelican
from app.services.minecraft.jar_manifest import JarManifestError, verify_jar_archive

_BOOT = "minecraft:startup:booted"
_HOLD = "minecraft:startup:hold"
_TTL = 30 * 86400
_ARGS_FILE = "user_jvm_args.txt"
MAX_CORE_JAR_BYTES = 128 * 1024 * 1024


class StartupError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _verify_core_jar(data: bytes) -> None:
    """Arclight 构建站不给校验值：至少确认拉下来的是完整、可启动的 jar，再改启动指令。"""
    try:
        verify_jar_archive(data)
    except JarManifestError as exc:
        raise pelican.PelicanError(f"核心下载校验失败：{exc.message}") from exc


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
        "current_selected_id": "",
        "java_images": [],
        "java_image": "",
        "java_warning": "",
        "current_java_image": "",
        "current_java_warning": "",
        "launch": "jar",
        "current_launch": "",
        "jvm_args": "",
        "user_jvm_args": "",
        "current_jvm_args": "",
        "current_user_jvm_args": "",
        "suggested_heap": cmd.suggest_heap_flags(0),
        "command": "",
        "current_command": "",
        "complete": False,
        "synced": False,
        "message": message,
        "kind": "",
        "plugins_visible": False,
        "plugins_ready": False,
        "application_token_set": False,
        "build_channel": "",
        "build_name": "",
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
    current_java_image: str,
    current_command: str,
    current_jvm_args: str,
    current_user_jvm_args: str,
    current_selected_id: str,
    current_launch: str,
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
    mc_version = str(detected.get("mc_version") or "")
    current_warning = (
        cmd.java_warning(current_java_image, major)
        if current_java_image and mc_version
        else ""
    )
    edit_warning = ""
    if java_image and mc_version and java_image != current_java_image:
        edit_warning = cmd.java_warning(java_image, major, edited=True)
    kind = str((selected or {}).get("kind") or "")
    plugins_visible = kind in {"plugin", "hybrid"}
    synced = bool(complete and command and live == command)
    ready = (
        _observe_boot(power, command, live, wrote=wrote) if complete and synced else False
    )
    if not plugins_visible:
        ready = False
    message = write_message or ("" if complete else why)
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
        "current_selected_id": current_selected_id,
        "java_images": [{"image": image, "label": _image_label(image)} for image in images],
        "java_image": java_image,
        "java_warning": edit_warning,
        "current_java_image": current_java_image,
        "current_java_warning": current_warning,
        "launch": launch if launch in {"jar", "args"} else "jar",
        "current_launch": current_launch if current_launch in {"jar", "args"} else "",
        "jvm_args": jvm_args,
        "user_jvm_args": user_jvm_args,
        "current_jvm_args": current_jvm_args,
        "current_user_jvm_args": current_user_jvm_args,
        "suggested_heap": cmd.suggest_heap_flags(memory_mb),
        "command": command,
        "current_command": current_command,
        "complete": complete,
        "synced": synced,
        "message": message,
        "kind": kind if kind in {"mod", "plugin", "hybrid"} else "",
        "plugins_visible": plugins_visible,
        "plugins_ready": bool(plugins_visible and ready and synced),
        "application_token_set": False,
        "build_channel": "",
        "build_name": "",
    }


def _match_live(choices: list[dict[str, Any]], live: str) -> dict[str, Any] | None:
    """只在启动指令对得上某个核心时返回，不用列表第一项冒充当前核心。"""
    parsed = cmd.parse_command(live)
    if parsed["launch"] == "jar" and parsed["jar"]:
        for row in choices:
            if row.get("jar") == parsed["jar"]:
                return row
    if parsed["launch"] == "args" and parsed["unix_args"]:
        for row in choices:
            if row.get("unix_args") == parsed["unix_args"]:
                return row
    return None


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


def _finish(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    payload["application_token_set"] = bool(get_pelican_application_token(db))
    return payload


def read_startup(
    db: Session,
    *,
    loader: str = "",
    core_id: str = "",
    java_image: str = "",
    jvm_args: str | None = None,
    user_jvm_args: str | None = None,
    build_channel: str = "",
    build_name: str = "",
    wrote: bool = False,
    write_message: str = "",
) -> dict[str, Any]:
    try:
        base, token, uuid = require_pelican(db)
    except Exception as exc:
        message = getattr(exc, "message", None) or "未配置 Pelican"
        return _finish(db, _empty(False, message))

    root = _list_names(base, token, uuid, "/")
    detected = cmd.detect_install(_names(root), _unix_paths(base, token, uuid))
    use_loader = str(detected.get("loader") or loader or "")
    choices = cmd.core_choices(detected, use_loader) if use_loader else []
    try:
        details = pelican.startup_details(pelican.get_startup(base, token, uuid))
    except pelican.PelicanError as exc:
        return _finish(db, _empty(True, exc.message))
    try:
        meta = pelican.parse_server_meta(pelican.get_server(base, token, uuid))
        memory_mb = int(meta.get("memory_limit_mb") or 0)
        server_image = str(meta.get("docker_image") or "")
    except pelican.PelicanError:
        memory_mb = 0
        server_image = ""
    try:
        power = pelican.power_state_from_resources(
            pelican.get_resources(base, token, uuid)
        )
    except pelican.PelicanError:
        power = "unknown"
    disk_args = _read_args_file(base, token, uuid)
    file_args = disk_args if user_jvm_args is None else user_jvm_args
    live = cmd.live_startup_command(details)
    parsed = cmd.parse_command(live)
    current_row = _match_live(choices, live)
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
    if server_image and server_image not in images:
        images.insert(0, server_image)
    details = dict(details)
    details["docker_images"] = images
    chosen_image = cmd.resolve_java_image(
        java_image,
        server_image,
        images,
        str(detected.get("mc_version") or ""),
    )
    current_launch = ""
    if current_row and current_row.get("launch") in {"jar", "args"}:
        current_launch = str(current_row["launch"])
    elif parsed["launch"] in {"jar", "args"}:
        current_launch = parsed["launch"]
    if (
        selected
        and not selected.get("jar")
        and selected.get("id") == "arclight"
        and build_name
    ):
        from app.services.minecraft.core_builds import arclight_jar_name, is_build_name

        if is_build_name(build_name.strip()):
            selected = dict(selected)
            selected["jar"] = arclight_jar_name(
                use_loader,
                str(detected.get("mc_version") or ""),
                build_name.strip(),
            )
    view = _view(
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
        current_java_image=server_image,
        current_command=live,
        current_jvm_args=parsed["jvm"] if parsed["launch"] == "jar" else "",
        current_user_jvm_args=str(disk_args or ""),
        current_selected_id=str((current_row or {}).get("id") or ""),
        current_launch=current_launch,
        wrote=wrote,
        write_message=write_message,
    )
    view["build_channel"] = (build_channel or "").strip()
    view["build_name"] = (build_name or "").strip()
    return _finish(db, view)


def list_core_builds(db: Session, core_id: str) -> dict[str, Any]:
    from app.services.minecraft.core_builds import (
        CoreBuildError,
        list_arclight_builds,
        supports_remote_builds,
    )

    if not supports_remote_builds(core_id):
        raise StartupError("这个核心没有可下载的版本", status_code=400)
    try:
        base, token, uuid = require_pelican(db)
    except Exception as exc:
        message = getattr(exc, "message", None) or "未配置 Pelican"
        raise StartupError(message) from exc
    detected = cmd.detect_install(
        _names(_list_names(base, token, uuid, "/")),
        _unix_paths(base, token, uuid),
    )
    loader = str(detected.get("loader") or "")
    mc_version = str(detected.get("mc_version") or "")
    if not mc_version:
        raise StartupError("还没认出 Minecraft 版本")
    try:
        options = list_arclight_builds(loader, mc_version)
    except CoreBuildError as exc:
        raise StartupError(exc.message, status_code=exc.status_code) from exc
    return {
        "core_id": core_id,
        "loader": loader,
        "mc_version": mc_version,
        "options": options,
    }


def apply_startup(
    db: Session,
    *,
    loader: str = "",
    core_id: str,
    java_image: str = "",
    jvm_args: str = "",
    user_jvm_args: str = "",
    build_channel: str = "",
    build_name: str = "",
) -> dict[str, Any]:
    if not (core_id or "").strip():
        return read_startup(
            db,
            loader=loader,
            java_image=java_image,
            jvm_args=jvm_args,
            user_jvm_args=user_jvm_args,
            build_channel=build_channel,
            build_name=build_name,
        )
    base, token, uuid = require_pelican(db)
    preview = read_startup(
        db,
        loader=loader,
        core_id=core_id,
        java_image=java_image,
        jvm_args=jvm_args,
        user_jvm_args=user_jvm_args,
        build_channel=build_channel,
        build_name=build_name,
    )
    if not preview["pelican_configured"]:
        raise StartupError(preview["message"] or "未配置 Pelican")
    messages: list[str] = []
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
    return read_startup(
        db,
        loader=loader,
        core_id=core_id,
        java_image=java_image,
        jvm_args=jvm_args,
        user_jvm_args=user_jvm_args,
        build_channel=build_channel,
        build_name=build_name,
        write_message="；".join(messages),
    )


def sync_startup_command(
    db: Session,
    *,
    loader: str = "",
    core_id: str,
    java_image: str = "",
    jvm_args: str = "",
    user_jvm_args: str = "",
    build_channel: str = "",
    build_name: str = "",
) -> dict[str, Any]:
    """下载所选服务端核心，并把启动指令写到 Pelican。"""
    if not get_pelican_application_token(db):
        raise StartupError("未配置管理端 API Token")
    if not (core_id or "").strip():
        raise StartupError("还没有选择服务端")
    base, token, uuid = require_pelican(db)
    preview = read_startup(
        db,
        loader=loader,
        core_id=core_id,
        java_image=java_image,
        jvm_args=jvm_args,
        user_jvm_args=user_jvm_args,
        build_channel=build_channel,
        build_name=build_name,
    )
    command = str(preview.get("command") or "").strip()
    if not command:
        raise StartupError(preview.get("message") or "指令还不完整")
    image = str(preview.get("java_image") or "")
    allowed = {row["image"] for row in preview.get("java_images") or []}
    if image and image in allowed:
        pelican.update_docker_image(base, token, uuid, image)
    if preview.get("launch") == "args":
        pelican.write_file(base, token, uuid, _ARGS_FILE, str(user_jvm_args or ""))
    elif core_id == "arclight" and build_name:
        from app.services.minecraft.core_builds import (
            CoreBuildError,
            arclight_download_url,
            arclight_jar_name,
        )

        try:
            filename = arclight_jar_name(
                str(preview.get("loader") or ""),
                str(preview.get("mc_version") or ""),
                build_name.strip(),
            )
            download = arclight_download_url(
                str(preview.get("mc_version") or ""),
                str(preview.get("loader") or ""),
                build_channel.strip(),
                build_name.strip(),
            )
        except CoreBuildError as exc:
            raise StartupError(exc.message, status_code=exc.status_code) from exc
        pelican.pull_file_verified(
            base,
            token,
            uuid,
            url=download,
            directory="/",
            filename=filename,
            verify=_verify_core_jar,
            max_bytes=MAX_CORE_JAR_BYTES,
        )
    elif not preview.get("complete"):
        raise StartupError(preview.get("message") or "指令还不完整")
    app_token = get_pelican_application_token(db)
    server = pelican.find_application_server(base, app_token, uuid)
    pelican.update_application_startup(
        base,
        app_token,
        int(server["id"]),
        int(server["egg"]),
        command,
        skip_scripts=bool(server.get("skip_scripts")),
    )
    return read_startup(
        db,
        loader=loader,
        core_id=core_id,
        java_image=java_image,
        jvm_args=jvm_args,
        user_jvm_args=user_jvm_args,
        build_channel=build_channel,
        build_name=build_name,
        wrote=True,
    )
