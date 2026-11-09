"""Authentication service layer."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_jwt_token,
    verify_password,
)
from app.models.entities import User
from app.schemas.auth import LoginRequest, TokenResponse, UserRead

settings = get_settings()


class AuthService:
    """Handles login verification and JWT token issuance/refresh."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def authenticate_and_issue_tokens(self, payload: LoginRequest) -> TokenResponse:
        """Verify email and password hash, returning access + refresh tokens."""
        stmt = select(User).where(User.email == payload.email.lower())
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None or not verify_password(payload.password, user.hashed_password):
            raise UnauthorizedError(
                code="INVALID_CREDENTIALS",
                message="Invalid email or password.",
            )
        if not user.is_active:
            raise UnauthorizedError(
                code="ACCOUNT_DISABLED",
                message="This user account is disabled.",
            )

        access_token = create_access_token(user.id, user.email, user.role)
        refresh_token = create_refresh_token(user.id, user.email, user.role)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in_seconds=settings.access_token_expire_minutes * 60,
            user=UserRead.model_validate(user),
        )

    async def refresh_access_token(self, refresh_token_str: str) -> TokenResponse:
        """Validate a refresh token and issue a fresh token pair."""
        decoded = decode_jwt_token(refresh_token_str, expected_type="refresh")
        user_id = int(decoded["sub"])
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise UnauthorizedError(
                code="USER_NOT_FOUND",
                message="User associated with refresh token no longer exists.",
            )

        new_access = create_access_token(user.id, user.email, user.role)
        new_refresh = create_refresh_token(user.id, user.email, user.role)
        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            expires_in_seconds=settings.access_token_expire_minutes * 60,
            user=UserRead.model_validate(user),
        )

