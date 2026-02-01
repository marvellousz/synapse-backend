"""Auth request/response schemas."""

from pydantic import BaseModel, EmailStr


class SignUp(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None


class Login(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    name: str | None
    createdAt: str

    model_config = {"from_attributes": True}
