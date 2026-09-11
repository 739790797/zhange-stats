"""浏览器 RUM 上报（公开）与管理端汇总。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.rate_limit import auth_limiter, client_ip
from app.models.user import User
from app.services.rum import (
    MAX_EVENTS_PER_POST,
    RumEventIn,
    ingest_rum_events,
    summarize_rum,
)

router = APIRouter(tags=["observability"])


class ClientRumEventIn(BaseModel):
    kind: str = Field(max_length=8)
    url: str = Field(default="", max_length=512)
    duration_ms: float
    status: int | None = None
    method: str | None = Field(default=None, max_length=16)
    transfer_size: int | None = None


class ClientRumIn(BaseModel):
    page: str = Field(default="", max_length=256)
    events: list[ClientRumEventIn] = Field(default_factory=list, max_length=MAX_EVENTS_PER_POST)


class ClientRumOut(BaseModel):
    ok: bool
    accepted: int


class RumSummaryRowOut(BaseModel):
    url_key: str
    host: str = ""
    count: int
    avg_ms: int
    p50_ms: int | None = None
    p95_ms: int | None = None
    max_ms: int | None = None
    error_count: int = 0
    avg_transfer: int | None = None


class RumSeriesPointOut(BaseModel):
    at: str
    api_count: int = 0
    img_count: int = 0
    api_p50_ms: int | None = None
    api_p95_ms: int | None = None
    img_p50_ms: int | None = None
    img_p95_ms: int | None = None


class RumSummaryOut(BaseModel):
    hours: int
    since: str
    api_count: int
    img_count: int
    api_p50_ms: int | None = None
    api_p95_ms: int | None = None
    api_max_ms: int | None = None
    img_p50_ms: int | None = None
    img_p95_ms: int | None = None
    img_max_ms: int | None = None
    api: list[RumSummaryRowOut] = Field(default_factory=list)
    img: list[RumSummaryRowOut] = Field(default_factory=list)
    series: list[RumSeriesPointOut] = Field(default_factory=list)


@router.post("/client-rum", response_model=ClientRumOut)
def post_client_rum(
    body: ClientRumIn,
    request: Request,
    db: Session = Depends(get_db),
) -> ClientRumOut:
    """浏览器批量上报等待时间。访客可报；不上平台日志。"""
    ip = client_ip(request)
    auth_limiter.hit(f"client-rum:ip:{ip}", limit=60, window_sec=600)
    accepted = ingest_rum_events(
        db,
        page=body.page,
        events=[
            RumEventIn(
                kind=ev.kind,
                url=ev.url,
                duration_ms=ev.duration_ms,
                status=ev.status,
                method=ev.method,
                transfer_size=ev.transfer_size,
            )
            for ev in body.events
        ],
    )
    db.commit()
    return ClientRumOut(ok=True, accepted=accepted)


@router.get("/settings/rum", response_model=RumSummaryOut)
def get_rum_summary(
    hours: int = Query(default=24, ge=1, le=336),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RumSummaryOut:
    """管理端：接口转圈与第三方图的 p50/p95。"""
    data = summarize_rum(db, hours=hours)
    return RumSummaryOut.model_validate(data)
