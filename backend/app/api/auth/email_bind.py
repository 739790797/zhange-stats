from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from app.api.auth.helpers import (
    PURPOSE_BIND,
    _consume_register_challenge,
    _upsert_register_challenge,
    _user_out,
)
from app.api.auth.schemas import (
    BindEmailRequest,
    BindEmailResponse,
    LinkExistingAccountRequest,
    LinkExistingAccountResponse,
    RegisterResponse,
    SendRegisterCodeRequest,
)
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rate_limit import auth_limiter, client_ip
from app.core.security import create_access_token, hash_password, verify_password
from app.models.member import Member
from app.models.user import User
from app.services.member_sync import delete_user_with_member, ensure_user_member

router = APIRouter()


@router.post("/send-bind-email-code", response_model=RegisterResponse)
def send_bind_email_code(
    body: SendRegisterCodeRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RegisterResponse:
    """已登录但无邮箱的用户：发送绑定邮箱验证码。"""
    if user.email:
        raise HTTPException(status_code=400, detail="当前账号已绑定邮箱")
    ip = client_ip(request)
    email = str(body.email).strip().lower()
    auth_limiter.hit(f"bind-email-code:ip:{ip}", limit=10, window_sec=600)
    auth_limiter.hit(f"bind-email-code:uid:{user.id}", limit=5, window_sec=600)
    auth_limiter.hit(f"bind-email-code:email:{email}", limit=5, window_sec=600)

    taken = (
        db.query(User)
        .filter(User.email == email, User.id != user.id)
        .first()
    )
    if taken:
        raise HTTPException(status_code=400, detail="该邮箱已被其他账号使用")

    _, delivery = _upsert_register_challenge(db, email, purpose=PURPOSE_BIND)
    msg = "验证码已发送"
    if delivery["mode"] == "log":
        msg = "验证码已输出到服务端日志（邮件未配置或发送失败）"
    return RegisterResponse(message=msg, email=email, delivery=delivery["mode"])


@router.post("/bind-email", response_model=BindEmailResponse)
def bind_email(
    body: BindEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BindEmailResponse:
    """完善账号：绑定邮箱，可选设置密码。"""
    if user.email:
        raise HTTPException(status_code=400, detail="当前账号已绑定邮箱")
    ip = client_ip(request)
    email = str(body.email).strip().lower()
    code = body.code.strip()
    auth_limiter.hit(f"bind-email:ip:{ip}", limit=20, window_sec=600)
    auth_limiter.hit(f"bind-email:uid:{user.id}", limit=10, window_sec=600)

    taken = (
        db.query(User)
        .filter(User.email == email, User.id != user.id)
        .first()
    )
    if taken:
        raise HTTPException(status_code=400, detail="该邮箱已被其他账号使用")

    _consume_register_challenge(db, email, code, purpose=PURPOSE_BIND)
    user.email = email
    user.email_verified = True
    if body.password:
        user.password_hash = hash_password(body.password)
    member = ensure_user_member(db, user)
    db.commit()
    db.refresh(user)
    db.refresh(member)
    user.member = member
    return BindEmailResponse(message="账号已完善", user=_user_out(user))


@router.post("/link-existing-account", response_model=LinkExistingAccountResponse)
def link_existing_account(
    body: LinkExistingAccountRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LinkExistingAccountResponse:
    """QQ 临时号：验证已有邮箱账号后，把 QQ 挂到老账号并删除临时号。"""
    if user.email:
        raise HTTPException(status_code=400, detail="当前账号已绑定邮箱，无需合并")

    ip = client_ip(request)
    email = str(body.email).strip().lower()
    auth_limiter.hit(f"link-existing:ip:{ip}", limit=20, window_sec=600)
    auth_limiter.hit(f"link-existing:uid:{user.id}", limit=10, window_sec=600)
    auth_limiter.hit(f"link-existing:email:{email}", limit=10, window_sec=600)

    temp_member = (
        db.query(Member)
        .options(
            joinedload(Member.skland_bind),
            joinedload(Member.taygedo_bind),
            joinedload(Member.exilium_bind),
            joinedload(Member.kujiequ_bind),
        )
        .filter(Member.user_id == user.id)
        .first()
    )
    if not temp_member or not temp_member.qq_openid:
        raise HTTPException(status_code=400, detail="当前账号未绑定 QQ，无法合并")

    if temp_member.steam_id:
        raise HTTPException(
            status_code=400,
            detail="临时账号已绑定 Steam，请先解绑后再合并到已有账号",
        )
    if (
        temp_member.skland_bind
        or temp_member.taygedo_bind
        or temp_member.exilium_bind
        or temp_member.kujiequ_bind
    ):
        raise HTTPException(
            status_code=400,
            detail="临时账号已绑定其他平台，请先解绑后再合并到已有账号",
        )

    target = db.query(User).filter(User.email == email).first()
    if not target or not verify_password(body.password, target.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="不能与当前账号合并")
    if target.email and not target.email_verified:
        raise HTTPException(status_code=403, detail="目标账号邮箱未验证")

    target_member = ensure_user_member(db, target)
    if target_member.qq_openid:
        raise HTTPException(
            status_code=400,
            detail="目标账号已绑定其他 QQ，请先在个人中心解绑后再试",
        )

    qq_openid = temp_member.qq_openid
    qq_unionid = temp_member.qq_unionid
    qq_nickname = temp_member.qq_nickname
    qq_avatar_url = temp_member.qq_avatar_url
    temp_avatar = temp_member.avatar_url
    temp_display = user.display_name

    # 先清临时号 QQ，避免 openid 唯一约束冲突
    temp_member.qq_openid = None
    temp_member.qq_unionid = None
    temp_member.qq_nickname = None
    temp_member.qq_avatar_url = None
    db.flush()

    target_member.qq_openid = qq_openid
    target_member.qq_unionid = qq_unionid
    target_member.qq_nickname = qq_nickname
    target_member.qq_avatar_url = qq_avatar_url
    if qq_avatar_url and not target_member.avatar_url:
        target_member.avatar_url = temp_avatar or qq_avatar_url
    if (
        temp_display
        and temp_display != user.username
        and (not target.display_name or target.display_name == target.username)
    ):
        target.display_name = temp_display[:64]
        target_member.nickname = target.display_name

    delete_user_with_member(db, user)
    db.commit()
    db.refresh(target)
    target_member = ensure_user_member(db, target)
    db.refresh(target_member)
    target.member = target_member

    token = create_access_token(target.username, user_id=target.id)
    return LinkExistingAccountResponse(
        message="已合并到已有账号，可用 QQ 登录",
        access_token=token,
        user=_user_out(target),
    )
