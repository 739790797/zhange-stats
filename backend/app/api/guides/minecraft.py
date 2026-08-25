"""Minecraft 单服：服况 / Pelican 代操 / 目标档案。"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.guides import minecraft_files as minecraft_files_api
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.platform_deps import require_feature
from app.models.user import User
from app.services import minecraft_console as console_svc
from app.services import minecraft_mod_tools as mod_tools_svc
from app.services import minecraft_modrinth as modrinth
from app.services import minecraft_perf as perf_svc
from app.services import minecraft_presence as presence_svc
from app.services import minecraft_profile as profile_svc
from app.services import pelican_client as pelican
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
    playbook_dirty: bool = False
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


class MinecraftOverrideOut(BaseModel):
    path: str
    content: str = ""


class MinecraftPlaybookOut(BaseModel):
    mc_version: str
    loader: str
    loader_version: str = ""
    egg_id: int = 0
    startup: str = ""
    mods: list[MinecraftModPinOut] = Field(default_factory=list)
    properties: dict[str, str] = Field(default_factory=dict)
    overrides: list[MinecraftOverrideOut] = Field(default_factory=list)


class MinecraftPlaybookStagesOut(BaseModel):
    bootstrap: str = "pending"
    mods: str = "pending"
    config: str = "pending"


class MinecraftProfileOut(MinecraftPlaybookOut):
    last_applied_at: str | None = None
    last_apply_message: str | None = None
    pelican_configured: bool = False
    startup_hint: str = ""
    playbook_dirty: bool = False
    applied: MinecraftPlaybookOut | None = None
    stages: MinecraftPlaybookStagesOut = Field(
        default_factory=MinecraftPlaybookStagesOut
    )


class MinecraftProfileUpdate(BaseModel):
    mc_version: str
    loader: str
    loader_version: str = ""
    egg_id: int = 0
    startup: str = ""
    mods: list[MinecraftModPinOut] = Field(default_factory=list)
    properties: dict[str, str] = Field(default_factory=dict)
    overrides: list[MinecraftOverrideOut] = Field(default_factory=list)


class MinecraftApplyOut(BaseModel):
    ok: bool
    message: str
    boot_in_startup: bool = False
    mod_count: int = 0
    startup_hint: str = ""
    stage: str = ""
    power_state: str = ""
    ping_online: bool = False
    ready: bool = False
    pulled: int = 0
    skipped: int = 0
    removed: int = 0
    egg_match: bool = False
    egg_name: str = ""
    inferred_loader: str = ""
    stages: MinecraftPlaybookStagesOut = Field(
        default_factory=MinecraftPlaybookStagesOut
    )


class MinecraftEggVariableOut(BaseModel):
    key: str
    name: str = ""
    value: str = ""


class MinecraftEggCurrentOut(BaseModel):
    command: str = ""
    docker_images: list[str] = Field(default_factory=list)
    variables: list[MinecraftEggVariableOut] = Field(default_factory=list)
    inferred_loader: str = ""
    matches_loader: bool = False
    egg_id: int = 0
    egg_name: str = ""
    docker_image: str = ""
    desired_command: str = ""
    can_write: bool = False


class MinecraftEggOut(BaseModel):
    egg_id: int | None = None
    uuid: str = ""
    name: str = ""
    description: str = ""
    nest: str = ""
    nest_id: int | None = None
    docker_images: list[str] = Field(default_factory=list)
    startup: str = ""
    source: str = "catalog"
    loaders: list[str] = Field(default_factory=list)
    key: str = ""
    reason: str = ""


class MinecraftEggsOut(BaseModel):
    ok: bool = True
    application_configured: bool = False
    current: MinecraftEggCurrentOut = Field(default_factory=MinecraftEggCurrentOut)
    recommended: MinecraftEggOut | None = None
    eggs: list[MinecraftEggOut] = Field(default_factory=list)
    catalog: list[MinecraftEggOut] = Field(default_factory=list)
    message: str = ""
    boot_in_startup: bool = False


class MinecraftEggSyncIn(BaseModel):
    startup: str = ""
    egg_id: int | None = None


class MinecraftLiveConfigOut(BaseModel):
    path: str
    size: int = 0
    modified_at: str | None = None
    kind: str = "mod"


class MinecraftGameVersionOut(BaseModel):
    version: str
    stable: bool = False
    version_type: str = "release"
    release_time: str | None = None


class MinecraftLoaderVersionOut(BaseModel):
    versions: list[str]


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


class MinecraftModSearchHitOut(BaseModel):
    project_id: str
    slug: str = ""
    title: str = ""
    description: str = ""
    icon_url: str = ""


class MinecraftModSearchOut(BaseModel):
    hits: list[MinecraftModSearchHitOut]


class MinecraftModPinIn(BaseModel):
    project_id: str
    version_id: str


class MinecraftModUpdateOut(BaseModel):
    current: MinecraftModPinOut
    latest: MinecraftModPinOut


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


def _raise_profile(exc: profile_svc.MinecraftProfileError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def _profile_out(db: Session, row: Any) -> MinecraftProfileOut:
    base, token, uuid = get_pelican_credentials(db)
    data = profile_svc.profile_to_dict(
        row,
        pelican_ok=pelican.pelican_configured(base, token, uuid),
    )
    return MinecraftProfileOut.model_validate(data)


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


@router.get("/profile", response_model=MinecraftProfileOut, dependencies=[_FEATURE])
def minecraft_get_profile(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftProfileOut:
    row = profile_svc.get_or_create_profile(db)
    return _profile_out(db, row)


@router.put("/profile", response_model=MinecraftProfileOut, dependencies=[_FEATURE])
def minecraft_put_profile(
    body: MinecraftProfileUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftProfileOut:
    try:
        row = profile_svc.save_profile(db, body.model_dump())
    except (profile_svc.MinecraftProfileError, ValueError) as exc:
        if isinstance(exc, profile_svc.MinecraftProfileError):
            _raise_profile(exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _profile_out(db, row)


def _run_apply(db: Session, fn: Any) -> MinecraftApplyOut:
    try:
        result = fn(db)
    except profile_svc.MinecraftProfileError as exc:
        _raise_profile(exc)
        raise
    except pelican.PelicanError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message) from exc
    return MinecraftApplyOut.model_validate(result)


@router.post("/apply", response_model=MinecraftApplyOut, dependencies=[_FEATURE])
def minecraft_apply(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftApplyOut:
    return _run_apply(db, profile_svc.apply_profile)


@router.post("/bootstrap", response_model=MinecraftApplyOut, dependencies=[_FEATURE])
def minecraft_bootstrap(
    body: MinecraftEggSyncIn | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftApplyOut:
    payload = body or MinecraftEggSyncIn()

    def _fn(session: Session) -> dict[str, Any]:
        return profile_svc.bootstrap_profile(
            session,
            startup=payload.startup,
            egg_id=payload.egg_id,
        )

    return _run_apply(db, _fn)


@router.post("/sync-egg", response_model=MinecraftEggsOut, dependencies=[_FEATURE])
def minecraft_sync_egg(
    body: MinecraftEggSyncIn | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftEggsOut:
    from app.services import minecraft_eggs as eggs_svc

    payload = body or MinecraftEggSyncIn()
    row = profile_svc.get_or_create_profile(db)
    try:
        data = eggs_svc.sync_server_egg(
            db,
            loader=row.loader,
            mc_version=row.mc_version,
            loader_version=row.loader_version or "",
            startup=payload.startup or row.startup or "",
            egg_id=payload.egg_id or row.egg_id or None,
        )
    except eggs_svc.EggSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except pelican.PelicanError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message) from exc
    return MinecraftEggsOut.model_validate(data)


@router.post("/sync-mods", response_model=MinecraftApplyOut, dependencies=[_FEATURE])
def minecraft_sync_mods(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftApplyOut:
    return _run_apply(db, profile_svc.sync_profile_mods)


@router.post("/apply-config", response_model=MinecraftApplyOut, dependencies=[_FEATURE])
def minecraft_apply_config(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftApplyOut:
    return _run_apply(db, profile_svc.apply_profile_config)


@router.get("/eggs", response_model=MinecraftEggsOut, dependencies=[_FEATURE])
def minecraft_eggs(
    loader: str = "",
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftEggsOut:
    from app.services import minecraft_eggs as eggs_svc

    return MinecraftEggsOut.model_validate(eggs_svc.collect_eggs(db, loader=loader))


@router.get(
    "/live-configs",
    response_model=list[MinecraftLiveConfigOut],
    dependencies=[_FEATURE],
)
def minecraft_live_configs(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[MinecraftLiveConfigOut]:
    try:
        rows = profile_svc.list_live_configs(db)
    except profile_svc.MinecraftProfileError as exc:
        _raise_profile(exc)
        raise
    except pelican.PelicanError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message) from exc
    return [MinecraftLiveConfigOut.model_validate(row) for row in rows]


@router.get(
    "/game-versions",
    response_model=list[MinecraftGameVersionOut],
    dependencies=[_FEATURE],
)
def minecraft_game_versions(
    _: User = Depends(require_admin),
) -> list[MinecraftGameVersionOut]:
    try:
        rows = profile_svc.list_game_versions()
    except profile_svc.MinecraftProfileError as exc:
        _raise_profile(exc)
        raise
    return [MinecraftGameVersionOut.model_validate(r) for r in rows]


@router.get(
    "/loader-versions",
    response_model=MinecraftLoaderVersionOut,
    dependencies=[_FEATURE],
)
def minecraft_loader_versions(
    loader: str,
    mc_version: str = "",
    _: User = Depends(require_admin),
) -> MinecraftLoaderVersionOut:
    try:
        versions = profile_svc.list_loader_versions(loader, mc_version)
    except (profile_svc.MinecraftProfileError, ValueError) as exc:
        if isinstance(exc, profile_svc.MinecraftProfileError):
            _raise_profile(exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MinecraftLoaderVersionOut(versions=versions)


@router.get("/mods/search", response_model=MinecraftModSearchOut, dependencies=[_FEATURE])
def minecraft_mod_search(
    q: str = "",
    loader: str = "fabric",
    mc_version: str = "",
    _: User = Depends(require_admin),
) -> MinecraftModSearchOut:
    try:
        hits = modrinth.search_mods(q, loader=loader, mc_version=mc_version)
    except modrinth.ModrinthError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc
    return MinecraftModSearchOut(hits=[MinecraftModSearchHitOut.model_validate(h) for h in hits])


@router.get(
    "/mods/versions",
    response_model=list[MinecraftModPinOut],
    dependencies=[_FEATURE],
)
def minecraft_mod_versions(
    project_id: str = Query(..., min_length=1),
    loader: str = "fabric",
    mc_version: str = "",
    _: User = Depends(require_admin),
) -> list[MinecraftModPinOut]:
    try:
        rows = modrinth.list_versions(project_id, loader=loader, mc_version=mc_version)
    except modrinth.ModrinthError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc
    return [MinecraftModPinOut.model_validate(r) for r in rows]


@router.post("/mods/pin", response_model=MinecraftModPinOut, dependencies=[_FEATURE])
def minecraft_mod_pin(
    body: MinecraftModPinIn,
    _: User = Depends(require_admin),
) -> MinecraftModPinOut:
    try:
        pin = modrinth.pin_version(body.project_id, body.version_id)
    except modrinth.ModrinthError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return MinecraftModPinOut.model_validate(pin)


@router.get(
    "/mods/updates",
    response_model=list[MinecraftModUpdateOut],
    dependencies=[_FEATURE],
)
def minecraft_mod_updates(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[MinecraftModUpdateOut]:
    try:
        rows = profile_svc.check_mod_updates(db)
    except modrinth.ModrinthError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc
    return [MinecraftModUpdateOut.model_validate(r) for r in rows]


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
