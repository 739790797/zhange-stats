"""Admin APIs: multi-service runtime health snapshot."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.services.runtime_health import collect_runtime_health

router = APIRouter(prefix="/settings/runtime-health", tags=["settings"])


class RuntimeHealthServiceOut(BaseModel):
    id: str
    name: str
    status: str
    latency_ms: float | None = None
    detail: str = ""


class RuntimeHealthOut(BaseModel):
    checked_at: str
    overall: str
    services: list[RuntimeHealthServiceOut] = Field(default_factory=list)


@router.get("", response_model=RuntimeHealthOut)
def get_runtime_health(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RuntimeHealthOut:
    from app.main import scheduler

    running = bool(scheduler.running) if scheduler else False
    report = collect_runtime_health(db, scheduler_running=running)
    return RuntimeHealthOut(
        checked_at=report.checked_at,
        overall=report.overall,
        services=[
            RuntimeHealthServiceOut(
                id=s.id,
                name=s.name,
                status=s.status,
                latency_ms=s.latency_ms,
                detail=s.detail,
            )
            for s in report.services
        ],
    )
