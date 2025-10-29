"""Authentication endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import (
    create_access_token,
    create_refresh_token,
    verify_password,
    TokenData,
)
from app.api.dependencies import get_db, get_current_user
from app.api.schemas.user import UserLogin, TokenResponse, UserCreate, UserProfile
from app.db.models import User

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """Login with username and password.

    Args:
        credentials: Username and password
        db: Database session

    Returns:
        Access token and refresh token
    """
    # Find user by username
    stmt = select(User).where(User.username == credentials.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Create tokens
    token_data = TokenData(
        user_id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        language=user.language,
    )

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(user.id)

    logger.info(f"User {user.username} logged in")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.get("/me", response_model=UserProfile)
async def get_profile(
    current_user: User = Depends(get_current_user),
):
    """Get current user profile.

    Args:
        current_user: Current authenticated user

    Returns:
        User profile
    """
    return UserProfile.from_orm(current_user)


@router.put("/me", response_model=UserProfile)
async def update_profile(
    user_update: UserCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user profile.

    Args:
        user_update: Updated user data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated user profile
    """
    if user_update.email:
        current_user.email = user_update.email
    if user_update.language:
        current_user.language = user_update.language
    if user_update.timezone:
        current_user.timezone = user_update.timezone

    await db.commit()
    await db.refresh(current_user)

    logger.info(f"User {current_user.username} updated profile")

    return UserProfile.from_orm(current_user)
