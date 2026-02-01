"""Auth: signup, login, me."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from prisma.models import User

from app.core.auth import create_access_token, get_current_user, hash_password, verify_password
from app.schemas.auth import Login, SignUp, Token, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        createdAt=user.createdAt.isoformat(),
    )


@router.post("/signup", response_model=UserResponse, status_code=201)
async def signup(body: SignUp) -> UserResponse:
    """Create a new user account."""
    existing = await User.prisma().find_unique(where={"email": body.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = await User.prisma().create(
        data={
            "email": body.email,
            "passwordHash": hash_password(body.password),
            "name": body.name,
        }
    )
    return _user_response(user)


@router.post("/login", response_model=Token)
async def login(body: Login) -> Token:
    """Log in and get an access token."""
    user = await User.prisma().find_unique(where={"email": body.email})
    if not user or not verify_password(body.password, user.passwordHash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(user.id)
    return Token(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    """Get current user (requires Bearer token)."""
    return _user_response(user)
