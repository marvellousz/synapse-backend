"""Auth: signup, login, verification, password reset, me."""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from prisma.models import (
    Chat,
    ChatMessage,
    EmailVerificationToken,
    Embedding,
    Extraction,
    Memory,
    MemoryTag,
    PasswordResetToken,
    Space,
    SpaceMemory,
    Upload,
    User,
)

from app.config import FRONTEND_BASE_URL
from app.core.auth import create_access_token, get_current_user, hash_password, verify_password
from app.schemas.auth import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    ForgotPasswordRequest,
    Login,
    MessageResponse,
    ResendVerificationRequest,
    ResetPasswordRequest,
    SignUp,
    Token,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.email_service import (
    build_reset_password_email_html,
    build_verify_email_html,
    send_email,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


TOKEN_TTL_HOURS = 24


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _expires_at() -> datetime:
    return _utcnow() + timedelta(hours=TOKEN_TTL_HOURS)


def _is_expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at < _utcnow()


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        emailVerified=user.emailVerifiedAt is not None,
        createdAt=user.createdAt.isoformat(),
    )


async def _delete_user_data(user_id: str) -> None:
    memory_rows = await Memory.prisma().find_many(
        where={"userId": user_id},
        select={"id": True},
    )
    memory_ids = [row.id for row in memory_rows]

    space_rows = await Space.prisma().find_many(
        where={"userId": user_id},
        select={"id": True},
    )
    space_ids = [row.id for row in space_rows]

    chat_rows = await Chat.prisma().find_many(
        where={"userId": user_id},
        select={"id": True},
    )
    chat_ids = [row.id for row in chat_rows]

    if chat_ids:
        await ChatMessage.prisma().delete_many(where={"chatId": {"in": chat_ids}})
    await Chat.prisma().delete_many(where={"userId": user_id})

    if memory_ids:
        await Embedding.prisma().delete_many(where={"memoryId": {"in": memory_ids}})
        await Extraction.prisma().delete_many(where={"memoryId": {"in": memory_ids}})
        await MemoryTag.prisma().delete_many(where={"memoryId": {"in": memory_ids}})
        await SpaceMemory.prisma().delete_many(where={"memoryId": {"in": memory_ids}})
        await Upload.prisma().delete_many(where={"memoryId": {"in": memory_ids}})
    await Memory.prisma().delete_many(where={"userId": user_id})

    if space_ids:
        await SpaceMemory.prisma().delete_many(where={"spaceId": {"in": space_ids}})
    await Space.prisma().delete_many(where={"userId": user_id})

    await EmailVerificationToken.prisma().delete_many(where={"userId": user_id})
    await PasswordResetToken.prisma().delete_many(where={"userId": user_id})
    await User.prisma().delete(where={"id": user_id})


async def _send_verification_email(user: User) -> None:
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    now = _utcnow()

    await EmailVerificationToken.prisma().update_many(
        where={"userId": user.id, "usedAt": None},
        data={"usedAt": now},
    )
    await EmailVerificationToken.prisma().create(
        data={
            "userId": user.id,
            "tokenHash": token_hash,
            "expiresAt": _expires_at(),
        }
    )

    verify_link = f"{FRONTEND_BASE_URL}/verify-email?token={token}"
    await send_email(
        to_email=user.email,
        subject="verify your synapse email",
        html=build_verify_email_html(verify_url=verify_link),
    )


async def _send_password_reset_email(user: User) -> None:
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    now = _utcnow()

    await PasswordResetToken.prisma().update_many(
        where={"userId": user.id, "usedAt": None},
        data={"usedAt": now},
    )
    await PasswordResetToken.prisma().create(
        data={
            "userId": user.id,
            "tokenHash": token_hash,
            "expiresAt": _expires_at(),
        }
    )

    reset_link = f"{FRONTEND_BASE_URL}/reset-password?token={token}"
    await send_email(
        to_email=user.email,
        subject="reset your synapse password",
        html=build_reset_password_email_html(reset_url=reset_link),
    )


@router.post("/signup", response_model=UserResponse, status_code=201)
async def signup(body: SignUp) -> UserResponse:
    """Create a new user account."""
    email = _normalize_email(body.email)
    existing = await User.prisma().find_unique(where={"email": email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = await User.prisma().create(
        data={
            "email": email,
            "passwordHash": hash_password(body.password),
            "name": body.name,
        }
    )

    try:
        await _send_verification_email(user)
    except Exception:
        logger.exception("failed to send verification email for user_id=%s", user.id)

    return _user_response(user)


@router.post("/login", response_model=Token)
async def login(body: Login) -> Token:
    """Log in and get an access token."""
    email = _normalize_email(body.email)
    user = await User.prisma().find_unique(where={"email": email})
    if not user or not verify_password(body.password, user.passwordHash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if user.emailVerifiedAt is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in",
        )
    token = create_access_token(user.id)
    return Token(access_token=token)


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(body: VerifyEmailRequest) -> MessageResponse:
    token_hash = _hash_token(body.token)
    record = await EmailVerificationToken.prisma().find_unique(where={"tokenHash": token_hash})

    if not record or record.usedAt is not None or _is_expired(record.expiresAt):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link",
        )

    await User.prisma().update(
        where={"id": record.userId},
        data={"emailVerifiedAt": _utcnow()},
    )
    await EmailVerificationToken.prisma().update(
        where={"id": record.id},
        data={"usedAt": _utcnow()},
    )

    return MessageResponse(message="Email verified. You can log in now.")


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(body: ResendVerificationRequest) -> MessageResponse:
    email = _normalize_email(body.email)
    user = await User.prisma().find_unique(where={"email": email})

    if user and user.emailVerifiedAt is None:
        try:
            await _send_verification_email(user)
        except Exception:
            logger.exception("failed to resend verification email for user_id=%s", user.id)

    return MessageResponse(message="If that email exists, a verification link has been sent.")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(body: ForgotPasswordRequest) -> MessageResponse:
    email = _normalize_email(body.email)
    user = await User.prisma().find_unique(where={"email": email})

    if user:
        try:
            await _send_password_reset_email(user)
        except Exception:
            logger.exception("failed to send password reset email for user_id=%s", user.id)

    return MessageResponse(message="If that email exists, a reset link has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(body: ResetPasswordRequest) -> MessageResponse:
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    token_hash = _hash_token(body.token)
    record = await PasswordResetToken.prisma().find_unique(where={"tokenHash": token_hash})

    if not record or record.usedAt is not None or _is_expired(record.expiresAt):
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    now = _utcnow()
    await User.prisma().update(
        where={"id": record.userId},
        data={"passwordHash": hash_password(body.password)},
    )
    await PasswordResetToken.prisma().update(
        where={"id": record.id},
        data={"usedAt": now},
    )

    return MessageResponse(message="Password updated. You can log in now.")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> MessageResponse:
    if not verify_password(body.currentPassword, user.passwordHash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(body.newPassword) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    if body.newPassword == body.currentPassword:
        raise HTTPException(status_code=400, detail="New password must be different")

    now = _utcnow()
    await User.prisma().update(
        where={"id": user.id},
        data={"passwordHash": hash_password(body.newPassword)},
    )
    await PasswordResetToken.prisma().update_many(
        where={"userId": user.id, "usedAt": None},
        data={"usedAt": now},
    )

    return MessageResponse(message="Password changed successfully.")


@router.post("/delete-account", response_model=MessageResponse)
async def delete_account(
    body: DeleteAccountRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> MessageResponse:
    if not verify_password(body.password, user.passwordHash):
        raise HTTPException(status_code=400, detail="Password is incorrect")

    await _delete_user_data(user.id)
    return MessageResponse(message="Account deleted.")


@router.get("/me", response_model=UserResponse)
async def me(user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    """Get current user (requires Bearer token)."""
    return _user_response(user)
