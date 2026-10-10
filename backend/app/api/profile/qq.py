from __future__ import annotations

import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload
import urllib.parse

from app.core.biz_logging import log_until_change
from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.public_url import resolve_backend_base, resolve_frontend_base
from app.core.rate_limit import auth_limiter, client_ip
from app.core.security import create_user_access_token, hash_password, strip_markup_chars
from app.core.session_cookies import (
    QQ_OAUTH_NONCE_COOKIE,
    clear_qq_oauth_nonce_cookie,
    set_qq_oauth_nonce_cookie,
)
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
from app.services.email import NOTICE_QQ_LINKED, notify_account_event
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
    STATE_TTL_MINUTES,
    QqOAuthError,
    build_qq_authorize_url,
    create_qq_oauth_state,
    decode_qq_oauth_state,
    exchange_code_for_profile,
    new_oauth_nonce,
    oauth_nonce_matches,
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

logger = logging.getLogger(__name__)

router = APIRouter(tags=["profile"])

@router.get("/profile/qq/oauth/start", response_model=QqOAuthStartResponse)
def qq_oauth_start(
    request: Request,
    response: Response,
    member_id: int | None = Query(
        default=None, description="管理员可为指定成员发起绑定"
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QqOAuthStartResponse:
    from app.services.integrations_config import get_qq_credentials

    ip = client_ip(request)
    auth_limiter.hit(f"qq-bind:ip:{ip}", limit=20, window_sec=600)
    auth_limiter.hit(f"qq-bind:uid:{user.id}", limit=10, window_sec=600)

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

    nonce = new_oauth_nonce()
    try:
        state = create_qq_oauth_state(
            purpose=PURPOSE_BIND,
            nonce=nonce,
            user_id=user.id,
            member_id=target_member_id,
            frontend=frontend,
            backend=backend,
        )
        url = build_qq_authorize_url(state=state, backend=backend)
    except QqOAuthError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    set_qq_oauth_nonce_cookie(
        response, request, nonce, max_age=STATE_TTL_MINUTES * 60
    )
    return QqOAuthStartResponse(url=url)


@router.get("/auth/qq/callback")
def qq_oauth_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    code: str | None = Query(default=None, max_length=512),
    state: str | None = Query(default=None, max_length=4096),
    error: str | None = Query(default=None, max_length=128),
) -> RedirectResponse:
    """QQ 互联登记的回调：/api/auth/qq/callback（登录 / 绑定共用）。

    回跳只带 qq_login|qq_bind=ok|error、固定 reason 码（码表见 docs/security.md）、
    一次性 ticket 与 need_complete，不带 QQ 返回或异常里的任何文案。
    """
    import secrets
    import string

    def _redirect(frontend: str, path: str, **params: str) -> RedirectResponse:
        q = urllib.parse.urlencode(params)
        resp = RedirectResponse(url=f"{frontend}{path}?{q}", status_code=302)
        # nonce 一次性：成败都清掉，回调 URL 被重放也换不出第二张 ticket
        clear_qq_oauth_nonce_cookie(resp, request)
        return resp

    state_data: dict | None = None
    if state:
        try:
            state_data = decode_qq_oauth_state(state)
        except QqOAuthError:
            state_data = None

    frontend = _frontend_from_state(state_data, request) or ""
    purpose = str((state_data or {}).get("purpose") or PURPOSE_LOGIN)
    err_path = "/login" if purpose == PURPOSE_LOGIN else "/profile"
    err_key = "qq_login" if purpose == PURPOSE_LOGIN else "qq_bind"

    def _fail(path: str, reason: str, detail: str = "") -> RedirectResponse:
        if detail:
            log_until_change(
                logger,
                "qq_oauth.rejected",
                "QQ 回调失败 purpose=%s reason=%s detail=%s",
                purpose,
                reason,
                detail,
            )
        return _redirect(frontend, path, **{err_key: "error", "reason": reason})

    if error:
        if error == "access_denied":
            return _fail(err_path, "cancelled")
        # error 是回跳 URL 里任何人都能改的值：repr 转义换行，免得伪造日志行
        return _fail(err_path, "upstream_error", f"error={error!r}")

    if not state or not state_data:
        return _fail(err_path, "state_invalid", "缺少 state" if not state else "state 无效或已过期")

    if not oauth_nonce_matches(state_data, request.cookies.get(QQ_OAUTH_NONCE_COOKIE)):
        return _fail(err_path, "browser_mismatch", "nonce Cookie 与 state 不符")

    backend = str(state_data.get("backend") or "").rstrip("/") or None

    if purpose == PURPOSE_LOGIN:
        if not code:
            return _fail("/login", "missing_code", "缺少 code")
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
                member.qq_nickname = (
                    strip_markup_chars(profile.nickname).strip() or member.qq_nickname
                )
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
                    return _fail("/login", "account_create_failed", "无法生成唯一用户名")
                nick = strip_markup_chars(profile.nickname).strip()[:64] or username
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
            token = create_user_access_token(user)
            from app.services.oauth_ticket import issue_oauth_ticket

            ticket = issue_oauth_ticket(db, token)
            db.commit()
            params = {"qq_login": "ok", "ticket": ticket}
            if not user.email:
                params["need_complete"] = "1"
            return _redirect(frontend, "/login", **params)
        except QqOAuthError as exc:
            db.rollback()
            return _fail("/login", "upstream_error", exc.message)
        except HTTPException as exc:
            db.rollback()
            return _fail("/login", getattr(exc, "reason", None) or "server_error", str(exc.detail))
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("QQ 登录回调异常")
            return _fail("/login", "server_error")

    # 绑定流程
    actor_id = int(state_data["uid"])
    target_member_id = int(state_data.get("mid") or 0)

    actor = db.query(User).filter(User.id == actor_id).first()
    if not actor:
        return _fail("/profile", "user_not_found", f"uid={actor_id}")

    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == target_member_id)
        .first()
    )
    if not member:
        return _fail("/profile", "member_not_found", f"mid={target_member_id}")
    if member.user_id != actor.id and not _is_admin_user(actor):
        return _fail("/profile", "forbidden", f"uid={actor_id} mid={member.id}")

    path = (
        "/profile"
        if member.user_id == actor.id
        else f"/members/{member.id}/profile"
    )

    if not code:
        return _fail(path, "missing_code", "缺少 code")

    try:
        profile = exchange_code_for_profile(code, backend=backend)
        _set_qq_profile(
            db,
            member,
            openid=profile.openid,
            unionid=profile.unionid,
            nickname=profile.nickname,
            avatar_url=profile.avatar_url,
        )
        db.commit()
    except QqOAuthError as exc:
        db.rollback()
        return _fail(path, "upstream_error", exc.message)
    except HTTPException as exc:
        db.rollback()
        return _fail(path, getattr(exc, "reason", None) or "bind_failed", str(exc.detail))
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("QQ 绑定回调异常 member_id=%s", member.id)
        return _fail(path, "server_error")

    owner = member.user
    if owner is not None and owner.email and owner.email_verified:
        background_tasks.add_task(notify_account_event, owner.email, NOTICE_QQ_LINKED)
    return _redirect(frontend, path, qq_bind="ok")


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


