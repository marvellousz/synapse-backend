"""Auth request/response schemas."""

from pydantic import BaseModel, EmailStr


class SignUp(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None


class Login(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str


class DeleteAccountRequest(BaseModel):
    password: str


class ConfirmDeleteAccountRequest(BaseModel):
    token: str


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class MessageResponse(BaseModel):
    message: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    name: str | None
    emailVerified: bool
    createdAt: str

    model_config = {"from_attributes": True}
