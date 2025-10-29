"""Pytest configuration and fixtures."""

import asyncio
from datetime import timedelta

import pytest
from pytest_asyncio import fixture
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, User
# Lazy import to avoid bcrypt initialization during test collection
# from app.api.auth import hash_password, create_access_token, TokenData


@fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@fixture
async def db_session():
    """Create a test database session."""
    # Use in-memory SQLite for tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session

    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    # Use a dummy bcrypt hash for testing to avoid bcrypt initialization
    dummy_hash = "$2b$12$abcdefghijklmnopqrstuvwxyz.test"
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=dummy_hash,
        language="fr",
        timezone="Europe/Paris",
        role="user",
        active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@fixture
async def test_admin_user(db_session: AsyncSession) -> User:
    """Create a test admin user."""
    # Use a dummy bcrypt hash for testing to avoid bcrypt initialization
    dummy_hash = "$2b$12$abcdefghijklmnopqrstuvwxyz.test"
    admin = User(
        username="admin",
        email="admin@example.com",
        hashed_password=dummy_hash,
        language="fr",
        timezone="Europe/Paris",
        role="admin",
        active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@fixture
async def test_token(test_user: User) -> str:
    """Create a test JWT token."""
    from app.api.auth import create_access_token, TokenData

    token_data = TokenData(
        user_id=test_user.id,
        username=test_user.username,
        email=test_user.email,
        role=test_user.role,
        language=test_user.language,
    )
    return create_access_token(token_data)


@fixture
async def test_admin_token(test_admin_user: User) -> str:
    """Create a test admin JWT token."""
    from app.api.auth import create_access_token, TokenData

    token_data = TokenData(
        user_id=test_admin_user.id,
        username=test_admin_user.username,
        email=test_admin_user.email,
        role=test_admin_user.role,
        language=test_admin_user.language,
    )
    return create_access_token(token_data)


