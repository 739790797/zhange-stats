"""Shared helpers for platform checkin HTTP routes."""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.member import Member
from app.schemas.checkin import CheckinNowBody

StatusT = TypeVar("StatusT", bound=BaseModel)
RoleT = TypeVar("RoleT", bound=BaseModel)
ResultT = TypeVar("ResultT", bound=BaseModel)
CheckinT = TypeVar("CheckinT", bound=BaseModel)


def raise_api_error(exc: Exception, api_error_cls: type[Exception]) -> None:
    if isinstance(exc, api_error_cls):
        message = getattr(exc, "message", None) or str(exc)
        raise HTTPException(status_code=400, detail=message) from exc
    raise exc


def role_keys_from_now_body(body: CheckinNowBody | None) -> set[tuple[str, str]] | None:
    """Parse optional single-role target from CheckinNowBody."""
    if body is None:
        return None
    gc = (body.game_code or "").strip()
    uid = (body.role_uid or "").strip()
    if gc and uid:
        return {(gc, uid)}
    if gc or uid:
        raise HTTPException(
            status_code=400,
            detail="game_code 与 role_uid 需同时提供",
        )
    return None


def build_checkin_status(
    *,
    db: Session,
    member: Member,
    bind: Any | None,
    status_cls: type[StatusT],
    role_cls: type[RoleT],
    result_cls: type[ResultT],
    query_today: Callable[..., dict[str, Any]],
    preview_roles: Callable[..., list[Any]],
    api_error_cls: type[Exception],
    include_roles: bool = True,
    force: bool = False,
    extra_fields: dict[str, Any] | None = None,
    serialize_role: Callable[[Any], RoleT] | None = None,
    soft_roles_on_none_ok: bool = False,
    role_pref_platform: str | None = None,
) -> StatusT:
    """Assemble *StatusOut for a bound (or unbound) checkin platform.

    soft_roles_on_none_ok: when True (skland), only downgrade token_ok on role
    failure if token_ok is still None; otherwise always set token_ok False.

    role_pref_platform: when set, seed/enrich today_results with per-role prefs.
    """
    if bind is None:
        return status_cls(bound=False)

    roles: list[RoleT] = []
    today_results: list[ResultT] = []
    token_ok: bool | None = None
    token_error: str | None = None
    summary = getattr(bind, "last_checkin_summary", None)

    try:
        live = query_today(db, bind, force=force)
        raw_results = list(live.get("results") or [])
        if role_pref_platform and raw_results:
            from app.api.jobs.checkin_queries import attach_last_checkin_to_result_dicts
            from app.services.checkin_role_prefs import attach_prefs_to_status_results

            raw_results = attach_prefs_to_status_results(
                db,
                platform=role_pref_platform,
                member_id=member.id,
                bind=bind,
                results=raw_results,
            )
            raw_results = attach_last_checkin_to_result_dicts(
                db,
                platform=role_pref_platform,
                member_id=member.id,
                results=raw_results,
            )
            db.refresh(bind)
        today_results = [result_cls(**r) for r in raw_results]
        token_ok = True
        if live.get("summary"):
            summary = str(live["summary"])
    except api_error_cls as exc:  # type: ignore[misc]
        token_ok = False
        token_error = getattr(exc, "message", str(exc))

    if include_roles and token_ok is not False:
        try:
            raw_roles = preview_roles(db, member)
            if serialize_role is not None:
                roles = [serialize_role(r) for r in raw_roles]
            else:
                roles = [role_cls(**r) for r in raw_roles]
        except api_error_cls as exc:  # type: ignore[misc]
            msg = getattr(exc, "message", str(exc))
            if soft_roles_on_none_ok:
                if token_ok is None:
                    token_ok = False
                    token_error = msg
            else:
                token_ok = False
                token_error = token_error or msg
            roles = []

    last_date = getattr(bind, "last_checkin_date", None)
    fields: dict[str, Any] = {
        "bound": True,
        "auto_checkin": bool(getattr(bind, "auto_checkin", False)),
        "checkin_hour": int(getattr(bind, "checkin_hour", 0)),
        "checkin_minute": int(getattr(bind, "checkin_minute", 0)),
        "bound_at": getattr(bind, "bound_at", None),
        "last_checkin_at": getattr(bind, "last_checkin_at", None),
        "last_checkin_date": last_date.isoformat() if last_date else None,
        "last_checkin_ok": getattr(bind, "last_checkin_ok", None),
        "last_checkin_summary": summary,
        "token_ok": token_ok,
        "token_error": token_error,
        "roles": roles,
        "today_results": today_results,
    }
    if extra_fields:
        fields.update(extra_fields)
    return status_cls(**fields)


def build_checkin_response(
    *,
    out: dict[str, Any],
    response_cls: type[CheckinT],
    result_cls: type[ResultT],
) -> CheckinT:
    return response_cls(
        skipped=bool(out.get("skipped")),
        ok=out.get("ok"),
        summary=str(out.get("summary") or ""),
        results=[result_cls(**r) for r in out.get("results") or []],
    )
