"""Admin APIs for AstrBot-style in-app self-update."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.deps import require_admin
from app.models.user import User
from app.services import app_updator

router = APIRouter(prefix="/settings/app-update", tags=["settings"])


class AppUpdateStatusOut(BaseModel):
    current_version: str
    install_dir: str
    update_allowed: bool
    update_blocked_reason: str = ""
    has_new_version: bool = False
    latest_version: str = ""
    latest_body: str = ""
    latest_published_at: str = ""
    busy: bool = False
    phase: str = ""
    message: str = ""
    error: str = ""
    restart_strategy: str = ""


class AppUpdateReleaseOut(BaseModel):
    tag_name: str
    name: str
    body: str = ""
    published_at: str = ""
    has_static_asset: bool = False


class AppUpdateCheckOut(BaseModel):
    status: AppUpdateStatusOut
    releases: list[AppUpdateReleaseOut] = Field(default_factory=list)


class AppUpdateDoIn(BaseModel):
    version: str = Field(default="latest", description="latest or vX.Y.Z")
    proxy: str | None = Field(default=None, description="Optional GitHub proxy URL prefix")
    reboot: bool = True


class AppUpdateDoOut(BaseModel):
    ok: bool
    message: str
    version: str = ""
    reboot: bool = False


def _status_out(st: app_updator.UpdateStatus) -> AppUpdateStatusOut:
    return AppUpdateStatusOut(
        current_version=st.current_version,
        install_dir=st.install_dir,
        update_allowed=st.update_allowed,
        update_blocked_reason=st.update_blocked_reason,
        has_new_version=st.has_new_version,
        latest_version=st.latest_version,
        latest_body=st.latest_body,
        latest_published_at=st.latest_published_at,
        busy=st.busy,
        phase=st.phase,
        message=st.message,
        error=st.error,
        restart_strategy=st.restart_strategy,
    )


@router.get("/status", response_model=AppUpdateStatusOut)
async def get_app_update_status(_: User = Depends(require_admin)) -> AppUpdateStatusOut:
    latest = None
    try:
        latest, _ = await app_updator.check_update()
    except Exception:
        # Status should still return local info if GitHub is unreachable
        pass
    return _status_out(app_updator.build_status(latest=latest, releases_checked=True))


@router.get("/releases", response_model=list[AppUpdateReleaseOut])
async def list_app_update_releases(
    _: User = Depends(require_admin),
) -> list[AppUpdateReleaseOut]:
    try:
        releases = await app_updator.fetch_releases()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取 Release 失败: {e}") from e
    return [
        AppUpdateReleaseOut(
            tag_name=r.tag_name,
            name=r.name,
            body=r.body,
            published_at=r.published_at,
            has_static_asset=bool(r.static_asset_url),
        )
        for r in releases
    ]


@router.post("/check", response_model=AppUpdateCheckOut)
async def check_app_update(_: User = Depends(require_admin)) -> AppUpdateCheckOut:
    try:
        latest, releases = await app_updator.check_update()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"检查更新失败: {e}") from e
    return AppUpdateCheckOut(
        status=_status_out(app_updator.build_status(latest=latest, releases_checked=True)),
        releases=[
            AppUpdateReleaseOut(
                tag_name=r.tag_name,
                name=r.name,
                body=r.body,
                published_at=r.published_at,
                has_static_asset=bool(r.static_asset_url),
            )
            for r in releases
        ],
    )


@router.post("/do", response_model=AppUpdateDoOut)
async def do_app_update(
    body: AppUpdateDoIn,
    _: User = Depends(require_admin),
) -> AppUpdateDoOut:
    allowed, reason = app_updator.update_allowed()
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)
    result = await app_updator.apply_update(
        version=body.version,
        proxy=body.proxy,
        reboot=body.reboot,
    )
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.message)
    return AppUpdateDoOut(
        ok=result.ok,
        message=result.message,
        version=result.version,
        reboot=result.reboot,
    )
