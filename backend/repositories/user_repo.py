"""
User repository — all database access for User entities.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.user import User
from backend.core.security import hash_password, Role


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        email: str,
        username: str,
        password: str,
        full_name: str | None = None,
        role: Role = Role.ANALYST,
    ) -> User:
        user = User(
            email=email.lower().strip(),
            username=username,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role.value,
        )
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.email == email.lower().strip())
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        user = await self.get_by_email(email)
        return user is not None

    async def username_exists(self, username: str) -> bool:
        user = await self.get_by_username(username)
        return user is not None

    async def get_by_google_id(self, google_id: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.google_id == google_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create_google_user(
        self,
        *,
        google_id: str,
        email: str,
        full_name: str | None,
        avatar_url: str | None,
    ) -> tuple[User, bool]:
        """Find an existing user by google_id or email, or create a new one.

        Returns a tuple of (user, created) where ``created`` is True if a new
        user was inserted. If a user with the same email exists but has no
        google_id, the existing account is linked to Google.
        """
        # 1. Try by google_id first
        user = await self.get_by_google_id(google_id)
        if user:
            # Refresh avatar / last login info
            if avatar_url and user.avatar_url != avatar_url:
                user.avatar_url = avatar_url
                await self._session.flush()
            return user, False

        # 2. Try by email — link existing local account to Google
        user = await self.get_by_email(email)
        if user:
            user.google_id = google_id
            user.auth_provider = "google"
            user.is_verified = True
            if avatar_url:
                user.avatar_url = avatar_url
            if full_name and not user.full_name:
                user.full_name = full_name
            await self._session.flush()
            await self._session.refresh(user)
            return user, False

        # 3. Create a brand-new user
        # Derive a unique username from email local-part
        base_username = (email.split("@", 1)[0] or "user").lower()
        base_username = "".join(ch for ch in base_username if ch.isalnum() or ch in "_-")[:80] or "user"
        username = base_username
        suffix = 1
        while await self.username_exists(username):
            suffix += 1
            username = f"{base_username}{suffix}"
            if suffix > 1000:
                # Fallback to a random suffix to avoid infinite loops
                import secrets
                username = f"{base_username}_{secrets.token_hex(4)}"
                break

        user = User(
            email=email.lower().strip(),
            username=username,
            hashed_password=None,
            full_name=full_name,
            role=Role.VIEWER.value,
            is_verified=True,
            google_id=google_id,
            avatar_url=avatar_url,
            auth_provider="google",
        )
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user, True

    async def update_last_login(self, user: User) -> None:
        from datetime import datetime, timezone
        user.last_login_at = datetime.now(timezone.utc)
        await self._session.flush()