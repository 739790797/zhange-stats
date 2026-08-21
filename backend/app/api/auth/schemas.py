from pydantic import BaseModel, EmailStr, Field

from app.schemas import UserOut


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


class SendResetPasswordCodeRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=16)
    new_password: str = Field(min_length=1, max_length=72)


class ResetPasswordResponse(BaseModel):
    message: str
    email: str
    delivery: str | None = None
