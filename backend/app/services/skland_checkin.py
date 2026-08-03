"""森空岛绑定与每日签到编排。"""

from __future__ import annotations

import logging
import threading
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.core.crypto_secret import decrypt_secret, encrypt_secret
from app.core.timeutil import now_naive, today
from app.models.job_run import JobRun
from app.models.member import Member
from app.models.skland import SklandBind
from app.services.checkin_common import (
    CheckinResult,
    is_success_status,
    results_to_api,
    summarize_results,
)
from app.services.skland_client import (
    SklandApiError,
    SklandRole,
    checkin_role,
    fetch_arknights_box,
    friendly_error_message,
    list_roles,
    login_with_token,
    normalize_hg_token,
    query_role_today,
    query_today_all,
    sort_skland_results,
    GAME_ARKNIGHTS,
)

logger = logging.getLogger(__name__)

JOB_KEY = "skland_checkin"
_job_lock = threading.Lock()


def get_bind_for_member(db: Session, member_id: int) -> SklandBind | None:
    return db.query(SklandBind).filter(SklandBind.member_id == member_id).one_or_none()


def bind_skland(db: Session, member: Member, raw_token: str) -> SklandBind:
    token = normalize_hg_token(raw_token)
    session = login_with_token(token)
    list_roles(session)

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        bind = SklandBind(
            member_id=member.id,
            token_enc=encrypt_secret(token),
            auto_checkin=True,
        )
        db.add(bind)
    else:
        bind.token_enc = encrypt_secret(token)
    bind.updated_at = now_naive()
    db.commit()
    db.refresh(bind)
    return bind


def bind_skland_with_password(
    db: Session, member: Member, phone: str, password: str
) -> SklandBind:
    from app.services.skland_client import token_by_phone_password

    return bind_skland(db, member, token_by_phone_password(phone, password))


def bind_skland_with_sms(db: Session, member: Member, phone: str, code: str) -> SklandBind:
    from app.services.skland_client import token_by_phone_code

    return bind_skland(db, member, token_by_phone_code(phone, code))


def send_skland_sms(phone: str) -> None:
    from app.services.skland_client import send_phone_code

    send_phone_code(phone)


def unbind_skland(db: Session, member: Member) -> None:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        return
    db.delete(bind)
    db.commit()


def set_auto_checkin(db: Session, member: Member, enabled: bool) -> SklandBind:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise SklandApiError("尚未绑定森空岛")
    bind.auto_checkin = bool(enabled)
    bind.updated_at = now_naive()
    db.commit()
    db.refresh(bind)
    return bind


def preview_roles(db: Session, member: Member) -> list[SklandRole]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise SklandApiError("尚未绑定森空岛")
    token = decrypt_secret(bind.token_enc)
    if not token:
        raise SklandApiError("凭证已损坏，请重新绑定")
    session = login_with_token(token)
    return list_roles(session)


def get_arknights_box_for_member(db: Session, member: Member, uid: str | None = None):
    """拉取指定（或默认）明日方舟账号的干员盒子。"""
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise SklandApiError("尚未绑定森空岛")
    session = _session_for_bind(bind)
    roles = [r for r in list_roles(session) if r.game_code == GAME_ARKNIGHTS]
    if not roles:
        raise SklandApiError("未找到明日方舟绑定角色")
    target_uid = str(uid or "").strip()
    role = next((r for r in roles if r.uid == target_uid), None) if target_uid else roles[0]
    if role is None:
        raise SklandApiError("UID 不在当前森空岛绑定列表中")
    box = fetch_arknights_box(session, role.uid)
    return box, role, roles


def _summarize(results: list[CheckinResult]) -> tuple[bool, str]:
    return summarize_results(
        results,
        empty_message="未找到可签到的游戏角色（请确认已在森空岛绑定明日方舟 / 终末地）",
    )


def _session_for_bind(bind: SklandBind):
    token = decrypt_secret(bind.token_enc)
    if not token:
        raise SklandApiError("凭证已损坏，请重新绑定")
    return login_with_token(token)


def query_today_for_bind(db: Session, bind: SklandBind) -> dict[str, Any]:
    """打开页：实时查询官方今日签到状态（不写日志表）。"""
    session = _session_for_bind(bind)
    try:
        results = query_today_all(session)
    except SklandApiError as exc:
        raise SklandApiError(friendly_error_message(exc.message)) from exc
    results = sort_skland_results(results)
    ok, summary = _summarize(results)
    # pending 不算失败；query 页只展示实时态
    if results:
        ok = all(r.status != "error" for r in results)
        summary = "\n".join(
            f"[{r.game_name}] {r.role_name}（{r.channel_name}）：{r.message}" for r in results
        )
    return {
        "ok": ok,
        "summary": summary,
        "results": results_to_api(results),
        "token_ok": True,
    }


def query_today_for_member(db: Session, member: Member) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise SklandApiError("尚未绑定森空岛")
    return query_today_for_bind(db, bind)


def run_checkin_for_bind(
    db: Session,
    bind: SklandBind,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """手动 / 自动签到：始终以官方为准；不写签到日志表。

    自动任务可用 bind.last_checkin_* 轻量跳过；手动 force 时忽略跳过。
    """
    checkin_date = today()
    if (
        not force
        and bind.last_checkin_date == checkin_date
        and bind.last_checkin_ok
    ):
        # 仍查官方，避免摘要过期；全部已签则 skipped
        try:
            live = query_today_for_bind(db, bind)
            results = [
                CheckinResult(
                    game_code=str(r.get("game_code") or ""),
                    game_name=str(r.get("game_name") or ""),
                    role_uid=str(r.get("role_uid") or ""),
                    role_name=str(r.get("role_name") or ""),
                    channel_name=str(r.get("channel_name") or ""),
                    status=str(r.get("status") or "pending"),
                    message=str(r.get("message") or ""),
                    awards_text=r.get("awards_text"),
                )
                for r in (live.get("results") or [])
            ]
            if results and all(is_success_status(r.status) for r in results):
                return {
                    "skipped": True,
                    "ok": True,
                    "reason": "today_done",
                    "summary": live.get("summary") or "今日已签到",
                    "results": live.get("results") or [],
                }
        except SklandApiError:
            pass

    session = _session_for_bind(bind)
    roles = list_roles(session)
    if not roles:
        return {
            "skipped": False,
            "ok": False,
            "summary": "未找到可签到的游戏角色（请确认已在森空岛绑定明日方舟 / 终末地）",
            "results": [],
        }

    results: list[CheckinResult] = []
    for role in roles:
        # 先查今日：已签则只补奖励，不 POST
        if not force:
            probed = query_role_today(session, role)
            if is_success_status(probed.status):
                results.append(probed)
                continue
        try:
            result = checkin_role(session, role)
        except SklandApiError as exc:
            msg = exc.message or ""
            already = "请勿重复签到" in msg or "重复签到" in msg
            if already:
                result = query_role_today(session, role)
                if result.status == "pending":
                    result = CheckinResult(
                        game_code=role.game_code,
                        game_name=role.game_name,
                        role_uid=role.uid,
                        role_name=role.role_name,
                        channel_name=role.channel_name,
                        status="already",
                        message="今日已签到",
                    )
            else:
                result = CheckinResult(
                    game_code=role.game_code,
                    game_name=role.game_name,
                    role_uid=role.uid,
                    role_name=role.role_name,
                    channel_name=role.channel_name,
                    status="error",
                    message=friendly_error_message(msg),
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("skland checkin unexpected error")
            result = CheckinResult(
                game_code=role.game_code,
                game_name=role.game_name,
                role_uid=role.uid,
                role_name=role.role_name,
                channel_name=role.channel_name,
                status="error",
                message=friendly_error_message(str(exc)),
            )
        results.append(result)

    results = sort_skland_results(results)
    ok, summary = _summarize(results)
    bind.last_checkin_at = now_naive()
    bind.last_checkin_date = checkin_date
    bind.last_checkin_ok = ok
    bind.last_checkin_summary = summary
    bind.updated_at = now_naive()
    db.commit()

    return {
        "skipped": False,
        "summary": summary,
        "ok": ok,
        "results": results_to_api(results),
    }


def run_checkin_for_member(
    db: Session, member: Member, *, force: bool = False
) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise SklandApiError("尚未绑定森空岛")
    return run_checkin_for_bind(db, bind, force=force)


def run_skland_checkin_job(db: Session) -> dict[str, Any]:
    binds = (
        db.query(SklandBind)
        .options(joinedload(SklandBind.member))
        .filter(SklandBind.auto_checkin.is_(True))
        .all()
    )
    stats: dict[str, Any] = {"total": len(binds), "ok": 0, "failed": 0, "skipped": 0}
    for bind in binds:
        try:
            out = run_checkin_for_bind(db, bind, force=False)
            if out.get("skipped"):
                stats["skipped"] += 1
            elif out.get("ok"):
                stats["ok"] += 1
            else:
                stats["failed"] += 1
        except Exception:  # noqa: BLE001
            logger.exception("skland auto checkin failed member_id=%s", bind.member_id)
            stats["failed"] += 1
            db.rollback()
    return stats


def checkin_job_wrapper() -> None:
    from app.core.database import SessionLocal

    if not _job_lock.acquire(blocking=False):
        logger.info("skland checkin job already running, skip")
        return
    db = SessionLocal()
    job = JobRun(job_key=JOB_KEY, status="running")
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        stats = run_skland_checkin_job(db)
        job.status = "ok"
        job.message = (
            f"完成：成功 {stats['ok']} / 失败 {stats['failed']} / "
            f"跳过 {stats['skipped']}（共 {stats['total']}）"
        )
        job.stats = stats
        job.finished_at = now_naive()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("skland checkin job crashed")
        job.status = "error"
        job.message = str(exc)
        job.finished_at = now_naive()
        db.commit()
    finally:
        db.close()
        _job_lock.release()
