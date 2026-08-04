from __future__ import annotations

import hmac
import secrets
import string
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rate_limit import auth_limiter, client_ip
from app.core.security import create_access_token, hash_password, verify_password
from app.core.timeutil import now_naive, to_naive
from app.models.register_challenge import RegisterChallenge
from app.models.user import User, UserRole
from app.schemas import LoginRequest, TokenResponse, UserOut, QqOAuthStartResponse
from app.services.email import send_verification_email
from app.services.member_sync import ensure_user_member
from app.core.public_url import resolve_backend_base, resolve_frontend_base
from app.services.integrations_config import get_qq_credentials
from app.services.qq_oauth import (
    PURPOSE_LOGIN,
    QqOAuthError,
    build_qq_authorize_url,
    create_qq_oauth_state,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class SendRegisterCodeRequest(BaseModel):
    email: EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    code: str = Field(min_length=4, max_length=16)


class RegisterResponse(BaseModel):
    message: str
    email: str
    delivery: str | None = None
    access_token: str | None = None
    token_type: str = "bearer"


class BindEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=16)
    password: str | None = Field(default=None, min_length=8, max_length=72)


class BindEmailResponse(BaseModel):
    message: str
    user: UserOut


class LinkExistingAccountRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class LinkExistingAccountResponse(BaseModel):
    message: str
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=16)


class ResendCodeRequest(BaseModel):
    email: EmailStr


def _utcnow() -> datetime:
    return now_naive()


def _gen_code() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(6))


def _gen_username(db: Session) -> str:
    alphabet = string.ascii_lowercase + string.digits
    for _ in range(20):
        suffix = "".join(secrets.choice(alphabet) for _ in range(6))
        username = f"user_{suffix}"
        if not db.query(User).filter(User.username == username).first():
            return username
    raise HTTPException(status_code=500, detail="无法生成唯一用户名，请重试")


def _upsert_register_challenge(db: Session, email: str) -> tuple[str, dict]:
    from app.services.email_config import load_email_config

    cfg = load_email_config(db)
    expire_minutes = max(1, int(cfg.get("code_expire_minutes") or 15))
    code = _gen_code()
    expires = _utcnow() + timedelta(minutes=expire_minutes)
    row = db.query(RegisterChallenge).filter(RegisterChallenge.email == email).first()
    if row:
        row.code = code
        row.expires_at = expires
    else:
        db.add(RegisterChallenge(email=email, code=code, expires_at=expires))
    db.commit()
    delivery = send_verification_email(email, code, db=db)
    return code, delivery


def _consume_register_challenge(db: Session, email: str, code: str) -> None:
    row = db.query(RegisterChallenge).filter(RegisterChallenge.email == email).first()
    if not row:
        raise HTTPException(status_code=400, detail="请先发送验证码")
    if to_naive(row.expires_at) < _utcnow():
        raise HTTPException(status_code=400, detail="验证码已过期，请重新获取")
    provided = code.strip()
    if len(provided) != len(row.code) or not hmac.compare_digest(row.code, provided):
        raise HTTPException(status_code=400, detail="验证码错误")
    db.delete(row)
    db.flush()


def _user_out(user: User) -> UserOut:
    member = user.member
    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        role=user.role.value if isinstance(user.role, UserRole) else str(user.role),
        is_admin=bool(user.is_admin) or user.role == UserRole.admin,
        email_verified=bool(user.email_verified),
        avatar_url=member.avatar_url if member else None,
        steam_id=member.steam_id if member else None,
        created_at=user.created_at,
    )


@router.post("/send-register-code", response_model=RegisterResponse)
def send_register_code(
    body: SendRegisterCodeRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    ip = client_ip(request)
    email = str(body.email).strip().lower()
    auth_limiter.hit(f"send-code:ip:{ip}", limit=10, window_sec=600)
    auth_limiter.hit(f"send-code:email:{email}", limit=5, window_sec=600)

    existing = db.query(User).filter(User.email == email).first()
    if existing and existing.email_verified:
        # 不暴露邮箱是否已注册
        return RegisterResponse(
            message="若该邮箱可注册，验证码已发送",
            email=email,
            delivery="skipped",
        )
    _, delivery = _upsert_register_challenge(db, email)
    msg = "若该邮箱可注册，验证码已发送"
    if delivery["mode"] == "log":
        msg = "验证码已输出到服务端日志（邮件未配置或发送失败）"
    return RegisterResponse(message=msg, email=email, delivery=delivery["mode"])


@router.post("/register", response_model=RegisterResponse)
def register(
    body: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    ip = client_ip(request)
    auth_limiter.hit(f"register:ip:{ip}", limit=10, window_sec=600)

    email = str(body.email).strip().lower()
    code = body.code.strip()
    auth_limiter.hit(f"register:email:{email}", limit=10, window_sec=600)

    existing = db.query(User).filter(User.email == email).first()
    if existing and existing.email_verified:
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    _consume_register_challenge(db, email, code)

    # 清理未完成验证的旧账号（若有）
    if existing:
        from app.services.member_sync import delete_user_with_member

        delete_user_with_member(db, existing)

    username = _gen_username(db)
    display_name = username
    user = User(
        username=username,
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
    db.commit()
    db.refresh(user)
    db.refresh(member)
    user.member = member
    token = create_access_token(user.username)
    return RegisterResponse(
        message="注册成功",
        email=email,
        access_token=token,
    )


@router.post("/verify-email")
def verify_email(
    body: VerifyEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """兼容旧流程：已注册未验证用户补验证（验证码存于 register_challenges）。"""
    ip = client_ip(request)
    auth_limiter.hit(f"verify:ip:{ip}", limit=20, window_sec=600)

    email = str(body.email).strip().lower()
    code = body.code.strip()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="验证失败，请检查邮箱与验证码")
    if user.email_verified:
        return {"message": "邮箱已验证，可直接登录"}
    _consume_register_challenge(db, email, code)
    user.email_verified = True
    db.commit()
    return {"message": "邮箱验证成功，请登录"}


@router.post("/resend-code", response_model=RegisterResponse)
def resend_code(
    body: ResendCodeRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    ip = client_ip(request)
    email = str(body.email).strip().lower()
    auth_limiter.hit(f"resend:ip:{ip}", limit=10, window_sec=600)
    auth_limiter.hit(f"resend:email:{email}", limit=5, window_sec=600)

    user = db.query(User).filter(User.email == email).first()
    if not user or user.email_verified:
        return RegisterResponse(
            message="若需要验证，验证码已发送",
            email=email,
            delivery="skipped",
        )
    _, delivery = _upsert_register_challenge(db, email)
    msg = "验证码已重新发送"
    if delivery["mode"] == "log":
        msg = "验证码已输出到服务端日志"
    return RegisterResponse(message=msg, email=email, delivery=delivery["mode"])


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    ip = client_ip(request)
    account = body.username.strip()
    auth_limiter.hit(f"login:ip:{ip}", limit=20, window_sec=600)
    auth_limiter.hit(f"login:account:{account.lower()}", limit=10, window_sec=600)

    if "@" in account:
        user = db.query(User).filter(User.email == account.lower()).first()
    else:
        user = db.query(User).filter(User.username == account).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误",
        )
    if user.email and not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="请先完成邮箱验证",
        )
    token = create_access_token(user.username)
    return TokenResponse(access_token=token)


@router.get("/qq/oauth/start", response_model=QqOAuthStartResponse)
def qq_oauth_login_start(
    request: Request,
    db: Session = Depends(get_db),
) -> QqOAuthStartResponse:
    """未登录用户发起 QQ 登录 / 一键注册。"""
    ip = client_ip(request)
    auth_limiter.hit(f"qq-login:ip:{ip}", limit=20, window_sec=600)

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
    try:
        state = create_qq_oauth_state(
            purpose=PURPOSE_LOGIN,
            frontend=frontend,
            backend=backend,
        )
        url = build_qq_authorize_url(state=state, backend=backend)
    except QqOAuthError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return QqOAuthStartResponse(url=url)


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

    _, delivery = _upsert_register_challenge(db, email)
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

    _consume_register_challenge(db, email, code)
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
    from sqlalchemy.orm import joinedload

    from app.models.member import Member
    from app.services.member_sync import delete_user_with_member

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

    token = create_access_token(target.username)
    return LinkExistingAccountResponse(
        message="已合并到已有账号，可用 QQ 登录",
        access_token=token,
        user=_user_out(target),
    )


@router.get("/me", response_model=UserOut)
def me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserOut:
    member = ensure_user_member(db, user)
    db.commit()
    db.refresh(user)
    db.refresh(member)
    user.member = member
    return _user_out(user)
