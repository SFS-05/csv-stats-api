"""
FastAPI dependency injection: auth, DB session, current user, rate limiting.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.exceptions import (
    AuthenticationError,
    PermissionDeniedError,
    TokenExpiredError,
    TokenInvalidError,
)
from backend.core.security import Role, TokenPayload, decode_token, has_permission
from backend.db.base import get_db
from backend.models.user import User
from backend.repositories.user_repo import UserRepository

# ── HTTP Bearer scheme ────────────────────────────────────────────────────────
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
) -> TokenPayload:
    """Extract and validate JWT from Authorization header."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
        if payload.token_type != "access":
            raise TokenInvalidError("Not an access token")
        return payload
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (JWTError, TokenInvalidError, AuthenticationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    token: Annotated[TokenPayload, Depends(get_current_token)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Load the authenticated user from the database."""
    repo = UserRepository(session)
    user = await repo.get_by_id(UUID(token.sub))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    return user


def require_permission(permission: str):
    """Factory: return a dependency that enforces a specific RBAC permission."""

    async def _check(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        role = Role(user.role)
        if not has_permission(role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission!r} required",
            )
        return user

    return _check


def require_role(*roles: Role):
    """Factory: return a dependency that enforces one of the given roles."""

    async def _check(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if Role(user.role) not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {user.role!r} is not authorized for this action",
            )
        return user

    return _check


# ── Typed dependency aliases ──────────────────────────────────────────────────
CurrentUser = Annotated[User, Depends(get_current_user)]
DBSession = Annotated[AsyncSession, Depends(get_db)]
CurrentToken = Annotated[TokenPayload, Depends(get_current_token)]