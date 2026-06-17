"""
Auth endpoints: register, login, refresh, logout, me.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Response, status
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
    GoogleAuthRequest,
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
    response_class=Response,
    summary="Change current user password",
)
async def change_password(
    payload: PasswordChangeRequest,
    current_user: CurrentUser,
    session: DBSession,
):
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


# ── Google OAuth ──────────────────────────────────────────────────────────────
async def _verify_google_id_token(id_token: str) -> dict:
    """Verify a Google ID token and return the decoded payload.

    Uses Google's tokeninfo endpoint so we don't need to manage a JWKS cache
    or pin a specific signing key. In production you should verify the
    ``aud`` claim matches your ``GOOGLE_CLIENT_ID``.
    """
    import httpx

    if not settings.GOOGLE_OAUTH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured on this server",
        )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": id_token},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not reach Google verification endpoint: {exc}",
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google ID token",
        )

    info = resp.json()

    # Validate required claims
    if "sub" not in info or "email" not in info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google token missing required claims",
        )

    # Verify the token was issued for our client (if configured)
    if (
        settings.GOOGLE_CLIENT_ID
        and info.get("aud") != settings.GOOGLE_CLIENT_ID
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google token audience mismatch",
        )

    # Verify the email is verified by Google
    if info.get("email_verified") not in (True, "true"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google email is not verified",
        )

    # Optional: restrict to allowed email domains
    if settings.GOOGLE_ALLOWED_DOMAINS:
        domain = (info.get("email") or "").split("@", 1)[-1].lower()
        if domain not in {d.lower() for d in settings.GOOGLE_ALLOWED_DOMAINS}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Email domain {domain!r} is not allowed",
            )

    return info


@router.post(
    "/google",
    response_model=TokenResponse,
    summary="Sign in or register with a Google ID token",
)
async def google_login(payload: GoogleAuthRequest, session: DBSession) -> TokenResponse:
    """Exchange a Google ``id_token`` (from Google Identity Services) for app JWTs.

    If the Google account is not yet linked to a user, a new account is
    created automatically. If the email already exists, the existing account
    is linked to Google.
    """
    info = await _verify_google_id_token(payload.id_token)

    google_id: str = info["sub"]
    email: str = info["email"]
    full_name: str | None = info.get("name")
    avatar_url: str | None = info.get("picture")

    repo = UserRepository(session)
    user, _created = await repo.get_or_create_google_user(
        google_id=google_id,
        email=email,
        full_name=full_name,
        avatar_url=avatar_url,
    )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    role = Role(user.role)
    access_token = create_access_token(user.id, role, str(uuid4()))
    refresh_token = create_refresh_token(user.id, role, str(uuid4()))

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