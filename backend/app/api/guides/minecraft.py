"""Minecraft 单服：服况 / Pelican 代操。"""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.guides import minecraft_files as minecraft_files_api
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.platform_deps import require_feature
from app.models.user import User
from app.services.minecraft import console as console_svc
from app.services.minecraft import mod_tools as mod_tools_svc
from app.services.minecraft import perf as perf_svc
from app.services.minecraft import presence as presence_svc
from app.services.minecraft import profile as profile_svc
from app.services.minecraft import pelican as pelican
from app.services.integrations_config import get_pelican_credentials

router = APIRouter(prefix="/minecraft", tags=["minecraft"])
router.include_router(minecraft_files_api.router)

_FEATURE = Depends(require_feature("guides.minecraft"))


class MinecraftPlayerOut(BaseModel):
    name: str
    id: str = ""


class MinecraftRosterPlayerOut(MinecraftPlayerOut):
    online: bool = False


class MinecraftPresenceSegmentOut(BaseModel):
    status: str
    start_sec: int
    end_sec: int


class MinecraftPresenceRowOut(BaseModel):
    player_key: str
    name: str
    id: str = ""
    online: bool = False
    online_seconds: int = 0
    offline_seconds: int = 0
    segments: list[MinecraftPresenceSegmentOut] = Field(default_factory=list)


class MinecraftPresenceOut(BaseModel):
    range_start: str
    range_end: str
    span_seconds: int
    player_count: int = 0
    online_count: int = 0
    rows: list[MinecraftPresenceRowOut] = Field(default_factory=list)


class MinecraftAppliedModOut(BaseModel):
    project_title: str = ""
    filename: str
    version_number: str = ""
    project_id: str = ""
    slug: str = ""


class MinecraftOverviewModOut(BaseModel):
    filename: str
    version_number: str = ""
    project_id: str = ""
    slug: str = ""
    title: str = ""
    title_zh: str = ""
    icon_url: str = ""
    summary: str = ""
    downloads: int | None = None
    environment: str = ""
    modrinth_url: str = ""
    curseforge_url: str = ""
    mcmod_url: str = ""


class MinecraftAppliedOut(BaseModel):
    mc_version: str
    loader: str
    loader_version: str = ""
    mods: list[MinecraftAppliedModOut] = Field(default_factory=list)
    properties: dict[str, str] = Field(default_factory=dict)
    last_applied_at: str | None = None


class MinecraftStatusOut(BaseModel):
    pelican_configured: bool
    power_state: str | None = None
    ping_online: bool
    rcon_connected: bool | None = None
    latency_ms: int | None = None
    motd: str = ""
    motd_raw: str = ""
    favicon: str = ""
    version_name: str = ""
    players_online: int = 0
    players_max: int = 0
    players: list[MinecraftPlayerOut] = Field(default_factory=list)
    public_host: str = ""
    public_port: int = 25565
    address: str = ""
    message: str = ""
    applied: MinecraftAppliedOut | None = None
    properties: dict[str, str] = Field(default_factory=dict)
    mods: list[MinecraftOverviewModOut] = Field(default_factory=list)
    whitelist: list[MinecraftPlayerOut] = Field(default_factory=list)
    roster: list[MinecraftRosterPlayerOut] = Field(default_factory=list)


class MinecraftPowerIn(BaseModel):
    signal: Literal["start", "stop", "restart", "kill"]


class MinecraftPowerOut(BaseModel):
    ok: bool
    message: str
    power_state: str | None = None


class MinecraftModPinOut(BaseModel):
    project_id: str
    project_title: str = ""
    slug: str = ""
    version_id: str
    version_number: str = ""
    filename: str
    download_url: str
    sha512: str
    sha1: str = ""
    file_size: int = 0
    env_server: str = "required"


class MinecraftEntityTypeOut(BaseModel):
    id: str
    name: str = ""
    count: int = 0
    category: str = ""


class MinecraftEntityCategoryOut(BaseModel):
    key: str
    count: int = 0


class MinecraftEntityWorldOut(BaseModel):
    id: str
    total: int = 0


class MinecraftEntitiesOut(BaseModel):
    ok: bool = False
    message: str = ""
    total: int = 0
    command: str = ""
    categories: list[MinecraftEntityCategoryOut] = Field(default_factory=list)
    types: list[MinecraftEntityTypeOut] = Field(default_factory=list)
    type_count: int = 0
    worlds: list[MinecraftEntityWorldOut] = Field(default_factory=list)
    at: str = ""


class MinecraftPerfSampleOut(BaseModel):
    at: str = ""
    tps: float | None = None
    mspt: float | None = None
    entities: float | None = None
    chunks: float | None = None


class MinecraftPerfOut(BaseModel):
    enabled: bool = False
    ok: bool = False
    connected: bool = False
    message: str = ""
    tps: float | None = None
    mspt: float | None = None
    chunks: float | None = None
    range: Literal["30m", "1h", "12h", "24h", "30d", "all"] = "30m"
    range_start: str = ""
    range_end: str = ""
    samples: list[MinecraftPerfSampleOut] = Field(default_factory=list)
    entities: MinecraftEntitiesOut = Field(default_factory=MinecraftEntitiesOut)


class MinecraftModToolFileOut(BaseModel):
    filename: str
    directory: str = ""
    kind: str = ""


class MinecraftModToolLinksOut(BaseModel):
    modrinth_url: str = ""
    curseforge_url: str = ""
    wiki_url: str = ""
    github_url: str = ""
    mcmod_url: str = ""
    icon_url: str = ""


class MinecraftModToolCatalogOut(BaseModel):
    loader: str = ""
    mc_version: str = ""
    project_id: str = ""
    installed_version: str = ""
    latest_version: str = ""
    latest_filename: str = ""
    compatible: bool = False
    update_available: bool = False
    target_directory: str = ""
    message: str = ""


class MinecraftModToolPresetOut(BaseModel):
    id: str
    title: str = ""
    summary: str = ""


class MinecraftModCommandOptionOut(BaseModel):
    value: str
    label: str = ""


class MinecraftModCommandArgOut(BaseModel):
    id: str
    label: str = ""
    kind: str = "token"
    options: list[MinecraftModCommandOptionOut] = Field(default_factory=list)
    min_value: int | None = None
    max_value: int | None = None
    optional: bool = False


class MinecraftModCommandNodeOut(BaseModel):
    id: str
    label: str = ""
    confirm: str = ""
    show_in_bar: bool = True
    args: list[MinecraftModCommandArgOut] = Field(default_factory=list)


class MinecraftModToolOut(BaseModel):
    id: str
    title: str = ""
    summary: str = ""
    present: bool = False
    loaded: bool = False
    filename: str = ""
    directory: str = ""
    kind: str = ""
    files: list[MinecraftModToolFileOut] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    icon_url: str = ""
    links: MinecraftModToolLinksOut = Field(default_factory=MinecraftModToolLinksOut)
    catalog: MinecraftModToolCatalogOut = Field(default_factory=MinecraftModToolCatalogOut)
    presets: list[MinecraftModToolPresetOut] = Field(default_factory=list)
    config_directory: str = ""
    command_tree: list[MinecraftModCommandNodeOut] = Field(default_factory=list)


class MinecraftChunkyStatusOut(BaseModel):
    state: str = "idle"
    world: str = ""
    shape: str = ""
    pattern: str = ""
    center_x: int | None = None
    center_z: int | None = None
    radius: int | None = None
    percent: float | None = None
    chunks: int | None = None
    chunks_total: int | None = None
    rate: float | None = None
    eta: str = ""
    chunk_x: int | None = None
    chunk_z: int | None = None
    needs_confirm: bool = False
    raw: str = ""


class MinecraftModToolsOut(BaseModel):
    ok: bool = True
    pelican_configured: bool = False
    rcon_configured: bool = False
    rcon_connected: bool | None = None
    loader: str = ""
    mc_version: str = ""
    message: str = ""
    worlds: list[str] = Field(default_factory=list)
    tools: list[MinecraftModToolOut] = Field(default_factory=list)
    chunky: MinecraftChunkyStatusOut | None = None


class MinecraftModToolCommandIn(BaseModel):
    action: Literal[
        "progress",
        "selection",
        "start",
        "pause",
        "continue",
        "cancel",
        "confirm",
        "spawn",
        "worldborder",
        "apply",
    ]
    world: str = ""
    shape: str = ""
    pattern: str = ""
    center_x: int | None = None
    center_z: int | None = None
    radius: int | None = None


class MinecraftModToolExecIn(BaseModel):
    command_id: str
    args: dict[str, str | int | float | None] = Field(default_factory=dict)


class MinecraftModToolCommandOut(BaseModel):
    ok: bool = True
    action: str = ""
    commands: list[str] = Field(default_factory=list)
    message: str = ""
    raw: str = ""
    status: MinecraftChunkyStatusOut = Field(default_factory=MinecraftChunkyStatusOut)


class MinecraftModToolInstallIn(BaseModel):
    version_id: str = ""
    preset_id: str = ""
    restart: bool = False


class MinecraftModToolPresetIn(BaseModel):
    preset_id: str = ""


class MinecraftModToolInstallOut(BaseModel):
    ok: bool = True
    tool_id: str = ""
    filename: str = ""
    directory: str = ""
    version_number: str = ""
    config_path: str = ""
    restarted: bool = False
    restart_required: bool = True
    message: str = ""


class MinecraftModToolVersionsOut(BaseModel):
    ok: bool = True
    tool_id: str = ""
    source: str = "modrinth"
    loader: str = ""
    mc_version: str = ""
    message: str = ""
    versions: list[MinecraftModPinOut] = Field(default_factory=list)


class MinecraftModToolPresetApplyOut(BaseModel):
    ok: bool = True
    tool_id: str = ""
    preset_id: str = ""
    path: str = ""
    source: Literal["factory", "draft"] = "factory"
    reloaded: bool = False
    restart_required: bool = True
    message: str = ""


class MinecraftModToolPresetDraftIn(BaseModel):
    content: str | None = None
    restore: bool = False


class MinecraftModToolPresetDraftOut(BaseModel):
    ok: bool = True
    tool_id: str = ""
    preset_id: str = ""
    title: str = ""
    summary: str = ""
    source: Literal["factory", "draft"] = "factory"
    filename: str = ""
    content: str = ""


@router.get("/status", response_model=MinecraftStatusOut, dependencies=[_FEATURE])
def minecraft_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> MinecraftStatusOut:
    data = profile_svc.collect_status(db)
    return MinecraftStatusOut.model_validate(data)


@router.get("/presence", response_model=MinecraftPresenceOut, dependencies=[_FEATURE])
def minecraft_presence(
    date_str: str = Query(..., alias="date", description="起始日期 YYYY-MM-DD"),
    end_str: str | None = Query(
        None, alias="end", description="结束日期 YYYY-MM-DD；缺省则仅查询当日"
    ),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> MinecraftPresenceOut:
    try:
        start = date.fromisoformat(date_str)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date 格式应为 YYYY-MM-DD") from exc
    end = start
    if end_str:
        try:
            end = date.fromisoformat(end_str)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="end 格式应为 YYYY-MM-DD") from exc
    try:
        data = presence_svc.build_presence_range(db, start, end)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MinecraftPresenceOut.model_validate(data)


@router.get("/perf", response_model=MinecraftPerfOut, dependencies=[_FEATURE])
def minecraft_perf(
    range_key: Literal["30m", "1h", "12h", "24h", "30d", "all"] = Query(
        "30m",
        alias="range",
        description="折线时间窗：30m / 1h / 12h / 24h / 30d / all",
    ),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> MinecraftPerfOut:
    try:
        data = perf_svc.read_public_perf(db, range_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MinecraftPerfOut.model_validate(data)


@router.post("/power", response_model=MinecraftPowerOut, dependencies=[_FEATURE])
def minecraft_power(
    body: MinecraftPowerIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftPowerOut:
    base, token, uuid = get_pelican_credentials(db)
    if not pelican.pelican_configured(base, token, uuid):
        raise HTTPException(status_code=400, detail="未配置 Pelican")
    try:
        pelican.send_power(base, token, uuid, body.signal)
        state = None
        try:
            res = pelican.get_resources(base, token, uuid)
            state = pelican.power_state_from_resources(res)
        except pelican.PelicanError:
            state = None
        return MinecraftPowerOut(ok=True, message="已发送电源指令", power_state=state)
    except pelican.PelicanError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message) from exc


@router.websocket("/console")
async def minecraft_console(websocket: WebSocket) -> None:
    await websocket.accept()
    await console_svc.run_console_session(websocket)


def _raise_mod_tools(exc: mod_tools_svc.MinecraftModToolsError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/mod-tools", response_model=MinecraftModToolsOut, dependencies=[_FEATURE])
def minecraft_mod_tools(
    force: bool = Query(False, description="跳过短时文件扫描缓存"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftModToolsOut:
    try:
        data = mod_tools_svc.collect_mod_tools(db, force=force)
    except mod_tools_svc.MinecraftModToolsError as exc:
        _raise_mod_tools(exc)
        raise
    except pelican.PelicanError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message) from exc
    return MinecraftModToolsOut.model_validate(data)


@router.post(
    "/mod-tools/chunky",
    response_model=MinecraftModToolCommandOut,
    dependencies=[_FEATURE],
)
def minecraft_chunky_command(
    body: MinecraftModToolCommandIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftModToolCommandOut:
    try:
        data = mod_tools_svc.run_chunky_command(
            db,
            body.action,
            world=body.world,
            shape=body.shape,
            pattern=body.pattern,
            center_x=body.center_x,
            center_z=body.center_z,
            radius=body.radius,
        )
    except mod_tools_svc.MinecraftModToolsError as exc:
        _raise_mod_tools(exc)
        raise
    return MinecraftModToolCommandOut.model_validate(data)


@router.post(
    "/mod-tools/{tool_id}/command",
    response_model=MinecraftModToolCommandOut,
    dependencies=[_FEATURE],
)
def minecraft_mod_tool_command(
    tool_id: str,
    body: MinecraftModToolExecIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftModToolCommandOut:
    try:
        data = mod_tools_svc.run_tool_command(
            db,
            tool_id,
            body.command_id,
            body.args,
        )
    except mod_tools_svc.MinecraftModToolsError as exc:
        _raise_mod_tools(exc)
        raise
    return MinecraftModToolCommandOut.model_validate(data)


@router.post(
    "/mod-tools/{tool_id}/install",
    response_model=MinecraftModToolInstallOut,
    dependencies=[_FEATURE],
)
def minecraft_mod_tool_install(
    tool_id: str,
    body: MinecraftModToolInstallIn | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftModToolInstallOut:
    payload = body or MinecraftModToolInstallIn()
    try:
        data = mod_tools_svc.install_tool(
            db,
            tool_id,
            version_id=payload.version_id,
            preset_id=payload.preset_id,
            restart=payload.restart,
        )
    except mod_tools_svc.MinecraftModToolsError as exc:
        _raise_mod_tools(exc)
        raise
    except pelican.PelicanError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message) from exc
    return MinecraftModToolInstallOut.model_validate(data)


@router.get(
    "/mod-tools/{tool_id}/versions",
    response_model=MinecraftModToolVersionsOut,
    dependencies=[_FEATURE],
)
def minecraft_mod_tool_versions(
    tool_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftModToolVersionsOut:
    try:
        data = mod_tools_svc.list_tool_versions(db, tool_id)
    except mod_tools_svc.MinecraftModToolsError as exc:
        _raise_mod_tools(exc)
        raise
    except pelican.PelicanError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message) from exc
    return MinecraftModToolVersionsOut.model_validate(data)


@router.post(
    "/mod-tools/{tool_id}/config",
    response_model=MinecraftModToolPresetApplyOut,
    dependencies=[_FEATURE],
)
def minecraft_mod_tool_config(
    tool_id: str,
    body: MinecraftModToolPresetIn | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftModToolPresetApplyOut:
    payload = body or MinecraftModToolPresetIn()
    try:
        data = mod_tools_svc.apply_tool_preset(db, tool_id, payload.preset_id)
    except mod_tools_svc.MinecraftModToolsError as exc:
        _raise_mod_tools(exc)
        raise
    except pelican.PelicanError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message) from exc
    return MinecraftModToolPresetApplyOut.model_validate(data)


@router.get(
    "/mod-tools/{tool_id}/presets/{preset_id}",
    response_model=MinecraftModToolPresetDraftOut,
    dependencies=[_FEATURE],
)
def minecraft_mod_tool_preset_get(
    tool_id: str,
    preset_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftModToolPresetDraftOut:
    try:
        data = mod_tools_svc.get_tool_preset(db, tool_id, preset_id)
    except mod_tools_svc.MinecraftModToolsError as exc:
        _raise_mod_tools(exc)
        raise
    except pelican.PelicanError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message) from exc
    return MinecraftModToolPresetDraftOut.model_validate(data)


@router.put(
    "/mod-tools/{tool_id}/presets/{preset_id}",
    response_model=MinecraftModToolPresetDraftOut,
    dependencies=[_FEATURE],
)
def minecraft_mod_tool_preset_put(
    tool_id: str,
    preset_id: str,
    body: MinecraftModToolPresetDraftIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftModToolPresetDraftOut:
    try:
        data = mod_tools_svc.save_tool_preset(
            db,
            tool_id,
            preset_id,
            content=body.content,
            restore=body.restore,
        )
    except mod_tools_svc.MinecraftModToolsError as exc:
        _raise_mod_tools(exc)
        raise
    except pelican.PelicanError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message) from exc
    return MinecraftModToolPresetDraftOut.model_validate(data)
