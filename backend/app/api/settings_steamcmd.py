"""管理端 SteamCMD 登录。口令和令牌不进配置文件。"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.deps import require_admin
from app.models.user import User
from app.services.ror2.steamcmd import SteamCmdError
from app.services.ror2.steamcmd_login import (
    SteamCmdBusy,
    cancel_login,
    login_status,
    start_login,
    submit_guard,
)

router = APIRouter(prefix="/integrations/steamcmd/login", tags=["settings"])


class SteamCmdLoginStart(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class SteamCmdLoginGuard(BaseModel):
    code: str = Field(min_length=1, max_length=16)


class SteamCmdLoginStatus(BaseModel):
    state: Literal["idle", "starting", "need_guard", "need_mobile", "ok", "error"]
    message: str = ""


def _call(action):
    try:
        return action()
    except SteamCmdBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SteamCmdError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("", response_model=SteamCmdLoginStatus)
def begin_steamcmd_login(
    body: SteamCmdLoginStart,
    _: User = Depends(require_admin),
) -> dict[str, str]:
    return _call(lambda: start_login(body.username, body.password))


@router.get("", response_model=SteamCmdLoginStatus)
def read_steamcmd_login(_: User = Depends(require_admin)) -> dict[str, str]:
    return login_status()


@router.post("/guard", response_model=SteamCmdLoginStatus)
def submit_steamcmd_guard(
    body: SteamCmdLoginGuard,
    _: User = Depends(require_admin),
) -> dict[str, str]:
    return _call(lambda: submit_guard(body.code))


@router.post("/cancel", response_model=SteamCmdLoginStatus)
def cancel_steamcmd_login(_: User = Depends(require_admin)) -> dict[str, str]:
    return cancel_login()
