from pydantic import BaseModel, EmailStr, Field

from app.schemas import UserOut

# 只挡异常大的请求体；设密码处的 72 字节上限由 validate_password 给中文提示，校验处照旧按 72 字节截断比对
PASSWORD_INPUT_MAX = 256


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=PASSWORD_INPUT_MAX)


class SessionResponse(BaseModel):
    """会话只在 HttpOnly Cookie 里，响应体不回令牌。"""

    ok: bool = True
    message: str


class SendRegisterCodeRequest(BaseModel):
    email: EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_INPUT_MAX)
    code: str = Field(min_length=4, max_length=16)


class RegisterResponse(BaseModel):
    message: str
    email: str
    delivery: str | None = None


class BindEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=16)
    password: str | None = Field(default=None, min_length=1, max_length=PASSWORD_INPUT_MAX)


class BindEmailResponse(BaseModel):
    message: str
    user: UserOut


class LinkExistingAccountRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_INPUT_MAX)


class LinkExistingAccountResponse(BaseModel):
    message: str
    user: UserOut


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=16)


class ResendCodeRequest(BaseModel):
    email: EmailStr


class SendResetPasswordCodeRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=16)
    new_password: str = Field(min_length=1, max_length=PASSWORD_INPUT_MAX)


class ResetPasswordResponse(BaseModel):
    message: str
    email: str
    delivery: str | None = None
