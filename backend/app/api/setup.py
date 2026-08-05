"""首次安装向导 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.auth_config import get_min_password_length
from app.services.setup import SetupError, complete_initial_admin, needs_setup

router = APIRouter(prefix="/setup", tags=["setup"])


class SetupStatusOut(BaseModel):
    needs_setup: bool
    min_password_length: int = 8


class SetupAdminRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=72)


class SetupAdminResponse(BaseModel):
    message: str
    access_token: str
    token_type: str = "bearer"


@router.get("/status", response_model=SetupStatusOut)
def get_setup_status(db: Session = Depends(get_db)) -> SetupStatusOut:
    return SetupStatusOut(
        needs_setup=needs_setup(db),
        min_password_length=get_min_password_length(db),
    )


@router.post("/admin", response_model=SetupAdminResponse)
def post_setup_admin(
    body: SetupAdminRequest,
    db: Session = Depends(get_db),
) -> SetupAdminResponse:
    try:
        _user, token = complete_initial_admin(
            db,
            email=str(body.email),
            display_name=body.display_name,
            password=body.password,
        )
    except SetupError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return SetupAdminResponse(
        message="初始化完成，已创建管理员账号",
        access_token=token,
    )
