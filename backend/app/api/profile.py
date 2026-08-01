from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload
import urllib.parse

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.security import hash_password
from app.models.member import Member
from app.models.user import User, UserRole
from app.schemas import (
    MemberProfileOut,
    MemberProfileUpdate,
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
from app.services.steam_bind import (
    PRIVACY_HINT,
    require_public_steam_profile,
    steam_profile_public_dict,
)
from app.services.steam_openid import (
    build_steam_login_url,
    create_openid_state,
    decode_openid_state,
    verify_steam_openid_assertion,
)
router = APIRouter(tags=["profile"])


def _profile_from_member(
    member: Member,
    steam_persona_name: str | None = None,
    *,
    viewer: User | None = None,
    include_email: bool | None = None,
) -> MemberProfileOut:
    user = member.user
    show_email = include_email
    if show_email is None:
        if viewer is None:
            show_email = True
        else:
            show_email = _is_admin_user(viewer) or (
                user is not None and user.id == viewer.id
            )
    persona = (
        steam_persona_name
        if steam_persona_name is not None
        else member.steam_persona_name
    )
    return MemberProfileOut(
        member_id=member.id,
        nickname=member.nickname,
        avatar_url=member.avatar_url,
        steam_id=member.steam_id,
        steam_persona_name=persona,
        steam_friends_public=member.steam_friends_public,
        steam_friends_synced_at=member.steam_friends_synced_at,
        user_id=member.user_id,
        username=user.username if user else None,
        email=(user.email if user else None) if show_email else None,
        display_name=user.display_name if user else None,
        joined_at=member.joined_at,
    )


def _user_brief(u: User) -> UserBrief:
    return UserBrief(
        id=u.id,
        username=u.username,
        email=u.email,
        display_name=u.display_name,
        role=u.role.value if isinstance(u.role, UserRole) else str(u.role),
        is_admin=bool(u.is_admin) or u.role == UserRole.admin,
        email_verified=bool(u.email_verified),
        member_id=u.member.id if u.member else None,
        steam_id=u.member.steam_id if u.member else None,
    )


def _is_admin_user(u: User) -> bool:
    return bool(u.is_admin) or u.role == UserRole.admin


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _set_steam_id(db: Session, member: Member, steam_id: str | None) -> str | None:
    """绑定或解绑 Steam；绑定时校验公开资料并同步头像。返回 Steam 昵称（解绑为 None）。"""
    from app.services.steam_friends import clear_member_friends, sync_member_friends
    from app.services.steam_persona import force_set_steam_persona_name

    value = (steam_id or "").strip() or None
    if not value:
        member.steam_id = None
        if is_custom_avatar_url(member.avatar_url):
            delete_avatar_file(member.id)
        member.avatar_url = None
        member.steam_friends_public = None
        member.steam_friends_synced_at = None
        member.steam_persona_name = None
        clear_member_friends(db, member.id)
        user = member.user
        if user is None and member.user_id is not None:
            user = db.query(User).filter(User.id == member.user_id).first()
        if user:
            # 解绑后还原为注册时的随机用户名，并清除头像
            member.nickname = user.username
            user.display_name = user.username
        return None

    try:
        profile = require_public_steam_profile(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    taken = (
        db.query(Member)
        .filter(Member.steam_id == profile.steam_id, Member.id != member.id)
        .first()
    )
    if taken:
        raise HTTPException(status_code=400, detail="该 Steam 账号已被其他成员绑定")

    member.steam_id = profile.steam_id
    user = member.user
    if user is None and member.user_id is not None:
        user = db.query(User).filter(User.id == member.user_id).first()
    force_set_steam_persona_name(
        member,
        profile.persona_name,
        user=user,
        update_display=True,
        avatar_url=profile.avatar_url,
    )
    sync_member_friends(db, member)
    return profile.persona_name


@router.get("/users", response_model=list[UserBrief])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[UserBrief]:
    users = (
        db.query(User)
        .options(joinedload(User.member))
        .order_by(User.id.asc())
        .all()
    )
    for u in users:
        ensure_user_member(db, u)
    db.commit()
    users = (
        db.query(User)
        .options(joinedload(User.member))
        .order_by(User.id.asc())
        .all()
    )
    return [_user_brief(u) for u in users]


@router.post("/users", response_model=UserBrief)
def create_user(
    body: UserAdminCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserBrief:
    from app.api.auth import _gen_username

    email = _normalize_email(body.email)
    if "@" not in email:
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    display_name = body.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="该邮箱已被注册")

    user = User(
        username=_gen_username(db),
        email=email,
        display_name=display_name,
        password_hash=hash_password(body.password),
        role=UserRole.user,
        is_admin=False,
        email_verified=True,
    )
    db.add(user)
    db.flush()
    member = ensure_user_member(db, user)
    if body.steam_id is not None:
        _set_steam_id(db, member, body.steam_id)
    db.commit()
    user = (
        db.query(User)
        .options(joinedload(User.member))
        .filter(User.id == user.id)
        .first()
    )
    return _user_brief(user)


@router.patch("/users/{user_id}", response_model=UserBrief)
def update_user(
    user_id: int,
    body: UserAdminUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserBrief:
    user = (
        db.query(User)
        .options(joinedload(User.member))
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    data = body.model_dump(exclude_unset=True)
    member = ensure_user_member(db, user)

    if "email" in data and data["email"] is not None:
        email = _normalize_email(data["email"])
        if "@" not in email:
            raise HTTPException(status_code=400, detail="邮箱格式不正确")
        taken = (
            db.query(User)
            .filter(User.email == email, User.id != user.id)
            .first()
        )
        if taken:
            raise HTTPException(status_code=400, detail="该邮箱已被注册")
        user.email = email

    if "display_name" in data and data["display_name"] is not None:
        name = data["display_name"].strip()
        if not name:
            raise HTTPException(status_code=400, detail="用户名不能为空")
        user.display_name = name
        member.nickname = name

    if "password" in data and data["password"]:
        user.password_hash = hash_password(data["password"])

    if "steam_id" in data:
        _set_steam_id(db, member, data["steam_id"])

    db.commit()
    user = (
        db.query(User)
        .options(joinedload(User.member))
        .filter(User.id == user_id)
        .first()
    )
    return _user_brief(user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
) -> None:
    user = (
        db.query(User)
        .options(joinedload(User.member))
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    if _is_admin_user(user):
        raise HTTPException(status_code=400, detail="不能删除管理员账号")

    try:
        delete_user_with_member(db, user)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=400, detail=f"删除失败：{exc}") from exc


def _apply_profile_fields(
    db: Session,
    user: User,
    member: Member,
    data: dict,
) -> str | None:
    """应用个人中心字段更新。返回绑定时的 Steam 昵称（若有）。"""
    if "display_name" in data:
        raise HTTPException(
            status_code=400,
            detail="用户名由 Steam 绑定后自动同步，不可手动修改",
        )

    steam_persona: str | None = None
    if "steam_id" in data:
        steam_persona = _set_steam_id(db, member, data["steam_id"])

    return steam_persona


@router.get("/profile/me", response_model=MemberProfileOut)
def get_my_profile(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberProfileOut:
    member = ensure_user_member(db, user)
    db.commit()
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member.id)
        .first()
    )
    return _profile_from_member(member)


@router.post("/profile/steam/preview", response_model=SteamBindPreviewResponse)
def preview_steam_bind(
    body: SteamBindPreviewRequest,
    _: User = Depends(get_current_user),
) -> SteamBindPreviewResponse:
    from app.services.steam_bind import lookup_steam_profile

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
    member_id: int | None = Query(
        default=None, description="管理员可为指定成员发起绑定"
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SteamOpenIdStartResponse:
    settings = get_settings()
    backend = (settings.PUBLIC_BACKEND_URL or "").rstrip("/")
    if not backend:
        raise HTTPException(
            status_code=400,
            detail="未配置 PUBLIC_BACKEND_URL，无法发起 Steam 登录绑定",
        )

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

    state = create_openid_state(user_id=user.id, member_id=target_member_id)
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
    settings = get_settings()
    frontend = (settings.PUBLIC_FRONTEND_URL or "http://127.0.0.1:5173").rstrip("/")

    def _redirect(path: str, **params: str) -> RedirectResponse:
        q = urllib.parse.urlencode(params)
        return RedirectResponse(url=f"{frontend}{path}?{q}", status_code=302)

    try:
        state_data = decode_openid_state(state)
    except ValueError as exc:
        return _redirect("/profile", steam_bind="error", detail=str(exc))

    actor_id = int(state_data["uid"])
    target_member_id = int(state_data.get("mid") or 0)

    query = {k: v for k, v in request.query_params.multi_items()}
    try:
        steam_id = verify_steam_openid_assertion(query)
    except ValueError as exc:
        return _redirect("/profile", steam_bind="error", detail=str(exc))

    actor = db.query(User).filter(User.id == actor_id).first()
    if not actor:
        return _redirect("/profile", steam_bind="error", detail="登录用户不存在")

    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == target_member_id)
        .first()
    )
    if not member:
        return _redirect("/profile", steam_bind="error", detail="成员不存在")

    # 非管理员只能绑定自己
    if member.user_id != actor.id and not _is_admin_user(actor):
        return _redirect("/profile", steam_bind="error", detail="无权绑定该成员")

    # 本人回个人中心；管理员代绑他人回成员个人中心
    path = (
        "/profile"
        if member.user_id == actor.id
        else f"/members/{member.id}/profile"
    )

    try:
        persona = _set_steam_id(db, member, steam_id)
        db.commit()
    except HTTPException as exc:
        detail = str(exc.detail) if exc.detail else "绑定失败"
        return _redirect(path, steam_bind="error", detail=detail)

    params = {"steam_bind": "ok"}
    if persona:
        params["name"] = persona
    return _redirect(path, **params)


@router.post("/profile/me/avatar", response_model=MemberProfileOut)
async def upload_my_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberProfileOut:
    member = ensure_user_member(db, user)
    url = await save_avatar_upload(member.id, file)
    member.avatar_url = url
    db.commit()
    db.refresh(member)
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member.id)
        .first()
    )
    return _profile_from_member(member)


@router.delete("/profile/me/avatar", response_model=MemberProfileOut)
def delete_my_avatar(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberProfileOut:
    member = ensure_user_member(db, user)
    if is_custom_avatar_url(member.avatar_url):
        delete_avatar_file(member.id)
    member.avatar_url = None
    db.commit()
    db.refresh(member)
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member.id)
        .first()
    )
    return _profile_from_member(member)


@router.post("/members/{member_id}/avatar", response_model=MemberProfileOut)
async def upload_member_avatar(
    member_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MemberProfileOut:
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    url = await save_avatar_upload(member.id, file)
    member.avatar_url = url
    db.commit()
    db.refresh(member)
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member.id)
        .first()
    )
    return _profile_from_member(member)


@router.patch("/profile/me", response_model=MemberProfileOut)
def update_my_profile(
    body: MemberProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberProfileOut:
    member = ensure_user_member(db, user)
    data = body.model_dump(exclude_unset=True)
    # 普通用户绑 Steam 必须走 OpenID，禁止手填他人 SteamID
    if "steam_id" in data and data["steam_id"] is not None and str(data["steam_id"]).strip():
        raise HTTPException(
            status_code=400,
            detail="请通过「Steam 登录绑定」完成绑定，以确保账号归属",
        )
    steam_persona = _apply_profile_fields(db, user, member, data)
    db.commit()
    db.refresh(member)
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member.id)
        .first()
    )
    return _profile_from_member(member, steam_persona)


@router.get("/members/{member_id}/profile", response_model=MemberProfileOut)
def get_member_profile(
    member_id: int,
    db: Session = Depends(get_db),
    viewer: User = Depends(get_current_user),
) -> MemberProfileOut:
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    return _profile_from_member(member, viewer=viewer)


@router.patch("/members/{member_id}/profile", response_model=MemberProfileOut)
def update_member_profile(
    member_id: int,
    body: MemberProfileUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MemberProfileOut:
    """管理员代编辑成员个人中心（测试绑定等）。"""
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    if not member.user:
        raise HTTPException(status_code=400, detail="该成员未关联用户账号")

    data = body.model_dump(exclude_unset=True)
    steam_persona = _apply_profile_fields(db, member.user, member, data)
    db.commit()
    db.refresh(member)
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member.id)
        .first()
    )
    return _profile_from_member(member, steam_persona)
