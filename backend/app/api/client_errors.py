"""前端渲染错误与 CSP 报告（写入运行时日志，不上第三方）。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.deps import get_current_user
from app.core.rate_limit import auth_limiter, client_ip
from app.models.user import User
from app.services.csp_report import record_csp_report

router = APIRouter(tags=["observability"])
logger = logging.getLogger("zhange.client")


class ClientErrorIn(BaseModel):
    message: str = Field(default="", max_length=500)
    component_stack: str = Field(default="", max_length=4000)
    pathname: str = Field(default="", max_length=256)
    request_id: str | None = Field(default=None, max_length=128)
    app_version: str | None = Field(default=None, max_length=32)


@router.post("/client-errors")
def post_client_error(
    body: ClientErrorIn,
    request: Request,
    user: User = Depends(get_current_user),
) -> dict:
    ip = client_ip(request)
    auth_limiter.hit(f"client-error:ip:{ip}", limit=10, window_sec=600)
    msg = (body.message or "").replace("\n", " ")[:500]
    stack = (body.component_stack or "").replace("\n", " | ")[:4000]
    path = (body.pathname or "").strip()[:256]
    rid = (body.request_id or "").strip()[:128]
    ver = (body.app_version or "").strip()[:32]
    logger.warning(
        "client_error user_id=%s pathname=%s request_id=%s version=%s msg=%s stack=%s",
        user.id,
        path,
        rid,
        ver,
        msg,
        stack,
    )
    return {"ok": True}


@router.post("/csp-report")
async def post_csp_report(request: Request) -> dict:
    ip = client_ip(request)
    auth_limiter.hit(f"csp-report:ip:{ip}", limit=30, window_sec=600)
    # 体积上限由 BodyLimitMiddleware 卡（64KB），超限在读 body 时直接 413
    record_csp_report(await request.body())
    return {"ok": True}
