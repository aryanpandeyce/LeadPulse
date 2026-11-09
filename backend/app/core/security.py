"""Password hashing with bcrypt, JWT access/refresh token creation, and RBAC dependencies."""

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db_session
from app.core.errors import ForbiddenError, RateLimitError, UnauthorizedError
from app.core.redis import get_redis
from app.models.entities import User

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    salt = bcrypt.gensalt(rounds=10)
    hashed: bytes = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(user_id: int, email: str, role: str) -> str:
    """Issue a signed JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int, email: str, role: str) -> str:
    """Issue a signed JWT refresh token."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "type": "refresh",
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_jwt_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    """Decode and validate a JWT token's signature, expiration, and token type."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError(
            code="TOKEN_EXPIRED",
            message="Token has expired. Please refresh or log in again.",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError(
            code="INVALID_TOKEN",
            message="Invalid authentication token.",
        ) from exc

    if payload.get("type") != expected_type:
        raise UnauthorizedError(
            code="WRONG_TOKEN_TYPE",
            message=f"Expected '{expected_type}' token.",
        )
    return payload


async def enforce_login_rate_limit(request: Request, email: str) -> None:
    """Protect /auth/login against brute-force attacks (max 10 attempts per minute per IP/email)."""
    redis = await get_redis()
    client_ip = request.client.host if request.client else "unknown"
    key = f"rl:login:{client_ip}:{email.lower()}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60)
    if count > 10:
        ttl = await redis.ttl(key)
        raise RateLimitError(
            code="LOGIN_RATE_LIMIT_EXCEEDED",
            message="Too many login attempts. Please wait before trying again.",
            retry_after=max(1, ttl),
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """FastAPI dependency that resolves the authenticated User or falls back to demo agent in dev mode if configured."""
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError(
            code="MISSING_AUTH_TOKEN",
            message="Authentication token is required (Authorization: Bearer <token>).",
        )

    payload = decode_jwt_token(credentials.credentials, expected_type="access")
    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise UnauthorizedError(
            code="USER_NOT_FOUND_OR_INACTIVE",
            message="User account does not exist or has been deactivated.",
        )
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> User | None:
    """Resolve authenticated User if Bearer header is provided; allows demo read access in portfolio UI while still supporting strict auth."""
    if credentials is None or not credentials.credentials:
        return None
    try:
        payload = decode_jwt_token(credentials.credentials, expected_type="access")
        user_id = int(payload["sub"])
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    except Exception:
        return None


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency enforcing `admin` role."""
    if user.role != "admin":
        raise ForbiddenError(
            code="ADMIN_ROLE_REQUIRED",
            message="Administrator privileges are required for this endpoint.",
        )
    return user
