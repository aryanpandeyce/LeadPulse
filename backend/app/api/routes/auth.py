"""Thin API route handlers for authentication (/auth/login, /auth/refresh, /auth/me)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import enforce_login_rate_limit, get_current_user
from app.models.entities import User
from app.schemas.auth import LoginRequest, RefreshTokenRequest, TokenResponse, UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])


@router.post("/login", response_model=TokenResponse, summary="Authenticate with email and password")
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Issue JWT access and refresh tokens after enforcing login rate limits."""
    await enforce_login_rate_limit(request, payload.email)
    service = AuthService(db)
    return await service.authenticate_and_issue_tokens(payload)


@router.post("/refresh", response_model=TokenResponse, summary="Exchange refresh token for new JWT pair")
async def refresh_tokens(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Rotate JWT access and refresh tokens."""
    service = AuthService(db)
    return await service.refresh_access_token(payload.refresh_token)


@router.get("/me", response_model=UserRead, summary="Get current authenticated user profile")
async def get_me(current_user: User = Depends(get_current_user)) -> UserRead:
    """Return the authenticated user's profile and role (`admin` or `agent`)."""
    return UserRead.model_validate(current_user)

