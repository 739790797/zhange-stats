from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload
import urllib.parse

from app.core.biz_logging import log_until_change
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.public_url import resolve_backend_base, resolve_frontend_base
from app.core.session_cookies import (
    STEAM_OPENID_NONCE_COOKIE,
    clear_steam_openid_nonce_cookie,
    set_steam_openid_nonce_cookie,
)
from app.models.member import Member
from app.models.user import User
from app.schemas import (
    SteamBindPreviewRequest,
    SteamBindPreviewResponse,
    SteamOpenIdStartResponse,
)
from app.services.member_sync import ensure_user_member
from app.services.steam.bind import (
    PRIVACY_HINT,
    steam_profile_public_dict,
)
from app.services.steam.openid import (
    STATE_TTL_MINUTES,
    SteamOpenIdError,
    build_steam_login_url,
    claim_openid_state,
    create_openid_state,
    decode_openid_state,
    new_openid_nonce,
    openid_nonce_matches,
    verify_steam_openid_assertion,
)
from app.api.profile.helpers import (
    _frontend_from_state,
    _is_admin_user,
    _require_steam_feature,
    _set_steam_id,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["profile"])


def _steam_return_to(backend: str, state: str) -> str:
    return f"{backend}/api/profile/steam/openid/callback?state={state}"


@router.post("/profile/steam/preview", response_model=SteamBindPreviewResponse)
def preview_steam_bind(
    body: SteamBindPreviewRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SteamBindPreviewResponse:
    from app.services.steam.bind import lookup_steam_profile

    _require_steam_feature(db)
    try:
        profile = lookup_steam_profile(body.steam_input)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    info = steam_profile_public_dict(profile)
    message = None
    if not profile.is_public:
        message = (
            "该账号个人资料未公开，绑定后无法获取游戏与在线信息。" + PRIVACY_HINT
        )
    return SteamBindPreviewResponse(
        steam_id=info["steam_id"],
        persona_name=info["persona_name"],
        avatar_url=info["avatar_url"],
        profile_url=info["profile_url"],
        is_public=info["is_public"],
        privacy_label=info["privacy_label"],
        message=message,
    )


@router.get("/profile/steam/openid/start", response_model=SteamOpenIdStartResponse)
def steam_openid_start(
    request: Request,
    response: Response,
    member_id: int | None = Query(
        default=None, description="管理员可为指定成员发起绑定"
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SteamOpenIdStartResponse:
    _require_steam_feature(db)
    from app.services.integrations_config import get_steam_api_key

    if not get_steam_api_key(db):
        raise HTTPException(
            status_code=400,
            detail="未配置 STEAM_API_KEY，请管理员在「集成密钥」中填写",
        )
    backend = resolve_backend_base(request)
    if not backend:
        raise HTTPException(
            status_code=400,
            detail="无法确定回调地址，请检查访问 Host 或配置 PUBLIC_BACKEND_URL",
        )
    frontend = resolve_frontend_base(request, backend=backend)

    target_member_id: int
    if member_id is not None:
        if not _is_admin_user(user):
            raise HTTPException(status_code=403, detail="仅管理员可为其他成员绑定")
        member = (
            db.query(Member)
            .options(joinedload(Member.user))
            .filter(Member.id == member_id)
            .first()
        )
        if not member or not member.user:
            raise HTTPException(status_code=404, detail="成员不存在")
        target_member_id = member.id
    else:
        member = ensure_user_member(db, user)
        db.commit()
        target_member_id = member.id

    nonce = new_openid_nonce()
    state = create_openid_state(
        user_id=user.id,
        member_id=target_member_id,
        nonce=nonce,
        frontend=frontend,
        backend=backend,
    )
    return_to = _steam_return_to(backend, state)
    realm = f"{backend}/"
    set_steam_openid_nonce_cookie(
        response, request, nonce, max_age=STATE_TTL_MINUTES * 60
    )
    return SteamOpenIdStartResponse(
        url=build_steam_login_url(return_to=return_to, realm=realm)
    )


@router.get("/profile/steam/openid/callback")
def steam_openid_callback(
    request: Request,
    db: Session = Depends(get_db),
    state: str = Query(..., max_length=4096),
) -> RedirectResponse:
    """回跳只带 steam_bind=ok|error 与固定 reason 码（码表见 docs/security.md），不带任何文案。"""

    def _redirect(frontend: str, path: str, reason: str | None = None) -> RedirectResponse:
        params = {"steam_bind": "error", "reason": reason} if reason else {"steam_bind": "ok"}
        resp = RedirectResponse(
            url=f"{frontend}{path}?{urllib.parse.urlencode(params)}", status_code=302
        )
        # nonce 一次性：成败都清掉
        clear_steam_openid_nonce_cookie(resp, request)
        return resp

    def _reject(frontend: str, path: str, reason: str, detail: str) -> RedirectResponse:
        log_until_change(
            logger,
            "steam_openid.rejected",
            "Steam 绑定回调被拒 reason=%s detail=%s",
            reason,
            detail,
        )
        return _redirect(frontend, path, reason)

    try:
        state_data = decode_openid_state(state)
    except ValueError as exc:
        frontend = resolve_frontend_base(request) or resolve_backend_base(request)
        return _reject(frontend, "/profile", "state_invalid", str(exc))

    frontend = _frontend_from_state(state_data, request)
    if not openid_nonce_matches(state_data, request.cookies.get(STEAM_OPENID_NONCE_COOKIE)):
        return _reject(frontend, "/profile", "browser_mismatch", "nonce Cookie 与 state 不符")
    backend = str(state_data.get("backend") or "").rstrip("/")
    if not backend:
        return _reject(frontend, "/profile", "state_invalid", "state 缺少 backend")
    if not claim_openid_state(state_data):
        return _reject(frontend, "/profile", "state_invalid", "state 已用过")

    query = {k: v for k, v in request.query_params.multi_items()}
    try:
        steam_id = verify_steam_openid_assertion(
            query, return_to=_steam_return_to(backend, state)
        )
    except SteamOpenIdError as exc:
        if exc.reason == "cancelled":
            return _redirect(frontend, "/profile", "cancelled")
        return _reject(frontend, "/profile", exc.reason, str(exc))

    actor_id = int(state_data["uid"])
    target_member_id = int(state_data.get("mid") or 0)
    actor = db.query(User).filter(User.id == actor_id).first()
    if not actor:
        return _reject(frontend, "/profile", "user_not_found", f"uid={actor_id}")

    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == target_member_id)
        .first()
    )
    if not member:
        return _reject(frontend, "/profile", "member_not_found", f"mid={target_member_id}")

    # 非管理员只能绑定自己
    if member.user_id != actor.id and not _is_admin_user(actor):
        return _reject(frontend, "/profile", "forbidden", f"uid={actor_id} mid={member.id}")

    # 本人回个人中心；管理员代绑他人回成员个人中心
    path = (
        "/profile"
        if member.user_id == actor.id
        else f"/members/{member.id}/profile"
    )

    try:
        _require_steam_feature(db)
        _set_steam_id(db, member, steam_id)
        db.commit()
    except HTTPException as exc:
        db.rollback()
        reason = getattr(exc, "reason", None) or "bind_failed"
        return _reject(frontend, path, reason, str(exc.detail))
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Steam 绑定回调异常 member_id=%s", member.id)
        return _redirect(frontend, path, "server_error")

    return _redirect(frontend, path)


