"""User management endpoints (admin only)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import hash_password
from app.api.dependencies import get_db, get_current_admin_user
from app.api.schemas.user import UserCreate, UserResponse, UserUpdate
from app.db.models import User

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all users (admin only).

    Args:
        skip: Pagination skip
        limit: Pagination limit
        current_user: Current admin user
        db: Database session

    Returns:
        List of users
    """
    stmt = select(User).offset(skip).limit(limit)
    result = await db.execute(stmt)
    users = result.scalars().all()
    return [UserResponse.from_orm(u) for u in users]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user (admin only).

    Args:
        user_data: User creation data
        current_user: Current admin user
        db: Database session

    Returns:
        Created user

    Raises:
        HTTPException: If user already exists
    """
    # Check if user exists
    stmt = select(User).where(
        (User.username == user_data.username) | (User.email == user_data.email)
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )

    # Create user
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        language=user_data.language,
        timezone=user_data.timezone,
        role=user_data.role,
    )

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    logger.info(f"User {db_user.username} created by {current_user.username}")

    return UserResponse.from_orm(db_user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user by ID (admin only).

    Args:
        user_id: User ID
        current_user: Current admin user
        db: Database session

    Returns:
        User

    Raises:
        HTTPException: If user not found
    """
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse.from_orm(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user (admin only).

    Args:
        user_id: User ID
        user_update: User update data
        current_user: Current admin user
        db: Database session

    Returns:
        Updated user

    Raises:
        HTTPException: If user not found
    """
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update fields
    if user_update.email:
        user.email = user_update.email
    if user_update.language:
        user.language = user_update.language
    if user_update.timezone:
        user.timezone = user_update.timezone
    if user_update.role:
        user.role = user_update.role
    if user_update.active is not None:
        user.active = user_update.active
    if user_update.password:
        user.hashed_password = hash_password(user_update.password)

    await db.commit()
    await db.refresh(user)

    logger.info(f"User {user.username} updated by {current_user.username}")

    return UserResponse.from_orm(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete user (admin only).

    Args:
        user_id: User ID
        current_user: Current admin user
        db: Database session

    Raises:
        HTTPException: If user not found or trying to delete self
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await db.delete(user)
    await db.commit()

    logger.info(f"User {user.username} deleted by {current_user.username}")
