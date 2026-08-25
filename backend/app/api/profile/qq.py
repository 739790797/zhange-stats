from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload
import urllib.parse

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.public_url import resolve_backend_base, resolve_frontend_base
from app.core.security import create_access_token, hash_password
from app.models.member import Member
from app.models.user import User, UserRole
from app.schemas import (
    MemberProfileOut,
    MemberProfileUpdate,
    QqOAuthStartResponse,
    SteamBindPreviewRequest,
    SteamBindPreviewResponse,
    SteamOpenIdStartResponse,
    UserAdminCreate,
    UserAdminUpdate,
    UserBrief,
)
from app.services.avatar_store import (
    delete_avatar_file,
    is_custom_avatar_url,
    save_avatar_upload,
)
from app.services.member_sync import delete_user_with_member, ensure_user_member
from app.services.steam.bind import (
    PRIVACY_HINT,
    require_public_steam_profile,
    steam_profile_public_dict,
)
from app.services.steam.openid import (
    build_steam_login_url,
    create_openid_state,
    decode_openid_state,
    verify_steam_openid_assertion,
)
from app.services.qq_oauth import (
    PURPOSE_BIND,
    PURPOSE_LOGIN,
    QqOAuthError,
    build_qq_authorize_url,
    create_qq_oauth_state,
    decode_qq_oauth_state,
    exchange_code_for_profile,
)
from app.api.profile.helpers import (
    _apply_profile_fields,
    _frontend_from_state,
    _is_admin_user,
    _normalize_email,
    _profile_from_member,
    _require_steam_feature,
    _set_qq_profile,
    _set_steam_id,
    _user_brief,
)

router = APIRouter(tags=["profile"])

@router.get("/profile/qq/oauth/start", response_model=QqOAuthStartResponse)
def qq_oauth_start(
    request: Request,
    member_id: int | None = Query(
        default=None, description="管理员可为指定成员发起绑定"
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QqOAuthStartResponse:
    from app.services.integrations_config import get_qq_credentials

    qq_app_id, qq_app_key = get_qq_credentials(db)
    if not qq_app_id or not qq_app_key:
        raise HTTPException(status_code=400, detail="未配置 QQ_APP_ID / QQ_APP_KEY")
    backend = resolve_backend_base(request)
    if not backend:
        raise HTTPException(
            status_code=400,
            detail="无法确定回调地址，请检查访问 Host 或配置 PUBLIC_BACKEND_URL",
        )
    frontend = resolve_frontend_base(request, backend=backend)

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

    try:
        state = create_qq_oauth_state(
            purpose=PURPOSE_BIND,
            user_id=user.id,
            member_id=target_member_id,
            frontend=frontend,
            backend=backend,
        )
        url = build_qq_authorize_url(state=state, backend=backend)
    except QqOAuthError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return QqOAuthStartResponse(url=url)


@router.get("/auth/qq/callback")
def qq_oauth_callback(
    request: Request,
    db: Session = Depends(get_db),
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse:
    """QQ 互联登记的回调：/api/auth/qq/callback（登录 / 绑定共用）。"""
    import secrets
    import string

    def _redirect(frontend: str, path: str, **params: str) -> RedirectResponse:
        q = urllib.parse.urlencode(params)
        return RedirectResponse(url=f"{frontend}{path}?{q}", status_code=302)

    fallback_frontend = (
        resolve_frontend_base(request) or resolve_backend_base(request) or ""
    )

    state_data: dict | None = None
    if state:
        try:
            state_data = decode_qq_oauth_state(state)
        except QqOAuthError:
            state_data = None

    frontend = (
        (_frontend_from_state(state_data, request) if state_data else None)
        or fallback_frontend
    )
    purpose = str((state_data or {}).get("purpose") or PURPOSE_LOGIN)
    err_path = "/login" if purpose == PURPOSE_LOGIN else "/profile"
    err_key = "qq_login" if purpose == PURPOSE_LOGIN else "qq_bind"

    if error:
        detail = error_description or error or "用户取消授权"
        return _redirect(frontend, err_path, **{err_key: "error", "detail": detail})

    if not state or not state_data:
        detail = "缺少 state" if not state else "QQ 登录状态已过期，请重试"
        return _redirect(frontend, err_path, **{err_key: "error", "detail": detail})

    backend = str(state_data.get("backend") or "").rstrip("/") or None

    if purpose == PURPOSE_LOGIN:
        if not code:
            return _redirect(frontend, "/login", qq_login="error", detail="缺少授权 code")
        try:
            profile = exchange_code_for_profile(code, backend=backend)
            member = (
                db.query(Member)
                .options(joinedload(Member.user))
                .filter(Member.qq_openid == profile.openid)
                .first()
            )
            if member and member.user:
                user = member.user
                member.qq_unionid = profile.unionid or member.qq_unionid
                member.qq_nickname = profile.nickname or member.qq_nickname
                member.qq_avatar_url = profile.avatar_url or member.qq_avatar_url
                if profile.avatar_url and not is_custom_avatar_url(member.avatar_url):
                    member.avatar_url = profile.avatar_url
            else:
                alphabet = string.ascii_lowercase + string.digits
                username = None
                for _ in range(20):
                    suffix = "".join(secrets.choice(alphabet) for _ in range(6))
                    candidate = f"qq_{suffix}"
                    if not db.query(User).filter(User.username == candidate).first():
                        username = candidate
                        break
                if not username:
                    return _redirect(
                        frontend, "/login", qq_login="error", detail="无法创建账号，请重试"
                    )
                nick = (profile.nickname or username)[:64]
                user = User(
                    username=username,
                    email=None,
                    display_name=nick,
                    password_hash=hash_password(secrets.token_urlsafe(32)),
                    role=UserRole.user,
                    email_verified=True,
                )
                db.add(user)
                db.flush()
                member = ensure_user_member(db, user)
                _set_qq_profile(
                    db,
                    member,
                    openid=profile.openid,
                    unionid=profile.unionid,
                    nickname=profile.nickname,
                    avatar_url=profile.avatar_url,
                )
                if profile.avatar_url:
                    member.avatar_url = profile.avatar_url

            db.commit()
            token = create_access_token(user.username)
            from app.services.oauth_ticket import issue_oauth_ticket

            ticket = issue_oauth_ticket(db, token)
            db.commit()
            params = {"qq_login": "ok", "ticket": ticket}
            if member.qq_nickname:
                params["name"] = member.qq_nickname
            if not user.email:
                params["need_complete"] = "1"
            return _redirect(frontend, "/login", **params)
        except QqOAuthError as exc:
            return _redirect(frontend, "/login", qq_login="error", detail=exc.message)
        except HTTPException as exc:
            detail = str(exc.detail) if exc.detail else "登录失败"
            return _redirect(frontend, "/login", qq_login="error", detail=detail)

    # 绑定流程
    actor_id = int(state_data["uid"])
    target_member_id = int(state_data.get("mid") or 0)

    actor = db.query(User).filter(User.id == actor_id).first()
    if not actor:
        return _redirect(frontend, "/profile", qq_bind="error", detail="登录用户不存在")

    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == target_member_id)
        .first()
    )
    if not member:
        return _redirect(frontend, "/profile", qq_bind="error", detail="成员不存在")
    if member.user_id != actor.id and not _is_admin_user(actor):
        return _redirect(frontend, "/profile", qq_bind="error", detail="无权绑定该成员")

    path = (
        "/profile"
        if member.user_id == actor.id
        else f"/members/{member.id}/profile"
    )

    if not code:
        return _redirect(frontend, path, qq_bind="error", detail="缺少授权 code")

    try:
        profile = exchange_code_for_profile(code, backend=backend)
        nickname = _set_qq_profile(
            db,
            member,
            openid=profile.openid,
            unionid=profile.unionid,
            nickname=profile.nickname,
            avatar_url=profile.avatar_url,
        )
        db.commit()
    except QqOAuthError as exc:
        return _redirect(frontend, path, qq_bind="error", detail=exc.message)
    except HTTPException as exc:
        detail = str(exc.detail) if exc.detail else "绑定失败"
        return _redirect(frontend, path, qq_bind="error", detail=detail)

    params = {"qq_bind": "ok"}
    if nickname:
        params["name"] = nickname
    return _redirect(frontend, path, **params)


@router.delete("/profile/qq", response_model=MemberProfileOut)
def unbind_qq(
    member_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberProfileOut:
    if member_id is not None:
        if not _is_admin_user(user):
            raise HTTPException(status_code=403, detail="仅管理员可为其他成员解绑")
        member = (
            db.query(Member)
            .options(
                joinedload(Member.user),
                joinedload(Member.skland_bind),
                joinedload(Member.taygedo_bind),
                joinedload(Member.exilium_bind),
                joinedload(Member.kujiequ_bind),
                joinedload(Member.mihoyo_bind),
            )
            .filter(Member.id == member_id)
            .first()
        )
        if not member:
            raise HTTPException(status_code=404, detail="成员不存在")
    else:
        member = ensure_user_member(db, user)
    _set_qq_profile(db, member, openid=None)
    db.commit()
    db.refresh(member)
    return _profile_from_member(member, viewer=user)


