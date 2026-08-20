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
    mods: list[MinecraftModPinOut] = Field(default_factory=list)
    properties: dict[str, str] = Field(default_factory=dict)
    overrides: list[MinecraftOverrideOut] = Field(default_factory=list)
    public_host: str = ""
    public_port: int = 25565


class MinecraftProfileOut(MinecraftPlaybookOut):
    last_applied_at: str | None = None
    last_apply_message: str | None = None
    pelican_configured: bool = False
    startup_hint: str = ""
    playbook_dirty: bool = False
    applied: MinecraftPlaybookOut | None = None


class MinecraftProfileUpdate(BaseModel):
    mc_version: str
    loader: str
    loader_version: str = ""
    mods: list[MinecraftModPinOut] = Field(default_factory=list)
    properties: dict[str, str] = Field(default_factory=dict)
    overrides: list[MinecraftOverrideOut] = Field(default_factory=list)
    public_host: str = ""
    public_port: int = Field(default=25565, ge=1, le=65535)


class MinecraftApplyOut(BaseModel):
    ok: bool
    message: str
    boot_in_startup: bool = False
    mod_count: int = 0
    startup_hint: str = ""


class MinecraftGameVersionOut(BaseModel):
    version: str
    stable: bool = False


class MinecraftLoaderVersionOut(BaseModel):
    versions: list[str]


class MinecraftPerfSampleOut(BaseModel):
    at: str = ""
    tps: float | None = None
    mspt: float | None = None


class MinecraftPerfOut(BaseModel):
    enabled: bool = False
    ok: bool = False
    message: str = ""
    tps: float | None = None
    mspt: float | None = None
    range: Literal["30m", "1h", "12h", "24h", "30d", "all"] = "30m"
    range_start: str = ""
    range_end: str = ""
    samples: list[MinecraftPerfSampleOut] = Field(default_factory=list)


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


@router.post("/apply", response_model=MinecraftApplyOut, dependencies=[_FEATURE])
def minecraft_apply(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftApplyOut:
    try:
        result = profile_svc.apply_profile(db)
    except profile_svc.MinecraftProfileError as exc:
        _raise_profile(exc)
        raise
    except pelican.PelicanError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message) from exc
    return MinecraftApplyOut.model_validate(result)


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
