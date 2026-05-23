"""
Auth endpoints: register, login, refresh, logout, me.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.dependencies import CurrentUser, DBSession
from backend.core.security import (
    Role,
    TokenPair,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from backend.core.config import settings
from backend.core.exceptions import DuplicateEmailError
from backend.repositories.user_repo import UserRepository
from backend.schemas.auth import (
    PasswordChangeRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(payload: UserRegister, session: DBSession) -> UserResponse:
    repo = UserRepository(session)

    if await repo.email_exists(payload.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email address already registered",
        )
    if await repo.username_exists(payload.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    user = await repo.create(
        email=payload.email,
        username=payload.username,
        password=payload.password,
        full_name=payload.full_name,
        role=Role.ANALYST,
    )
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive JWT tokens",
)
async def login(payload: UserLogin, session: DBSession) -> TokenResponse:
    repo = UserRepository(session)
    user = await repo.get_by_email(payload.email)

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    jti = str(uuid4())
    role = Role(user.role)
    access_token = create_access_token(user.id, role, jti)
    refresh_token = create_refresh_token(user.id, role, str(uuid4()))

    # Update last login
    from sqlalchemy import update
    from backend.models.user import User
    await session.execute(
        update(User)
        .where(User.id == user.id)
        .values(last_login_at=datetime.now(timezone.utc))
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token using refresh token",
)
async def refresh_token(
    payload: RefreshTokenRequest, session: DBSession
) -> TokenResponse:
    try:
        token_data = decode_token(payload.refresh_token)
        if token_data.token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not a refresh token",
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    repo = UserRepository(session)
    from uuid import UUID
    user = await repo.get_by_id(UUID(token_data.sub))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    role = Role(user.role)
    jti = str(uuid4())
    access_token = create_access_token(user.id, role, jti)
    new_refresh = create_refresh_token(user.id, role, str(uuid4()))

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile",
)
async def get_me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change current user password",
)
async def change_password(
    payload: PasswordChangeRequest,
    current_user: CurrentUser,
    session: DBSession,
) -> None:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    from backend.core.security import hash_password
    from sqlalchemy import update
    from backend.models.user import User
    await session.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(hashed_password=hash_password(payload.new_password))
    )