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

    state = create_openid_state(
        user_id=user.id,
        member_id=target_member_id,
        frontend=frontend,
        backend=backend,
    )
    return_to = f"{backend}/api/profile/steam/openid/callback?state={state}"
    realm = f"{backend}/"
    return SteamOpenIdStartResponse(
        url=build_steam_login_url(return_to=return_to, realm=realm)
    )


@router.get("/profile/steam/openid/callback")
def steam_openid_callback(
    request: Request,
    db: Session = Depends(get_db),
    state: str = Query(...),
) -> RedirectResponse:
    def _redirect(frontend: str, path: str, **params: str) -> RedirectResponse:
        q = urllib.parse.urlencode(params)
        return RedirectResponse(url=f"{frontend}{path}?{q}", status_code=302)

    try:
        state_data = decode_openid_state(state)
    except ValueError as exc:
        frontend = resolve_frontend_base(request) or resolve_backend_base(request)
        return _redirect(frontend, "/profile", steam_bind="error", detail=str(exc))

    frontend = _frontend_from_state(state_data, request)
    actor_id = int(state_data["uid"])
    target_member_id = int(state_data.get("mid") or 0)

    query = {k: v for k, v in request.query_params.multi_items()}
    try:
        steam_id = verify_steam_openid_assertion(query)
    except ValueError as exc:
        return _redirect(frontend, "/profile", steam_bind="error", detail=str(exc))

    actor = db.query(User).filter(User.id == actor_id).first()
    if not actor:
        return _redirect(frontend, "/profile", steam_bind="error", detail="登录用户不存在")

    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == target_member_id)
        .first()
    )
    if not member:
        return _redirect(frontend, "/profile", steam_bind="error", detail="成员不存在")

    # 非管理员只能绑定自己
    if member.user_id != actor.id and not _is_admin_user(actor):
        return _redirect(frontend, "/profile", steam_bind="error", detail="无权绑定该成员")

    # 本人回个人中心；管理员代绑他人回成员个人中心
    path = (
        "/profile"
        if member.user_id == actor.id
        else f"/members/{member.id}/profile"
    )

    try:
        _require_steam_feature(db)
        persona = _set_steam_id(db, member, steam_id)
        db.commit()
    except HTTPException as exc:
        detail = str(exc.detail) if exc.detail else "绑定失败"
        return _redirect(frontend, path, steam_bind="error", detail=detail)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        return _redirect(
            frontend, path, steam_bind="error", detail=f"绑定失败: {exc}"
        )

    params = {"steam_bind": "ok"}
    if persona:
        params["name"] = persona
    return _redirect(frontend, path, **params)


