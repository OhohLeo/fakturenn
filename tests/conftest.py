"""Pytest configuration and fixtures."""

import asyncio
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, User
from app.api.main import create_app
from app.api.auth import hash_password, create_token


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
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


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=hash_password("testpass123"),
        language="fr",
        timezone="Europe/Paris",
        role="user",
        active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_admin_user(db_session: AsyncSession) -> User:
    """Create a test admin user."""
    admin = User(
        username="admin",
        email="admin@example.com",
        hashed_password=hash_password("adminpass123"),
        language="fr",
        timezone="Europe/Paris",
        role="admin",
        active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest.fixture
def test_token(test_user: User) -> str:
    """Create a test JWT token."""
    return create_token(
        user_id=test_user.id,
        expires_in=timedelta(hours=1),
    )


@pytest.fixture
def test_admin_token(test_admin_user: User) -> str:
    """Create a test admin JWT token."""
    return create_token(
        user_id=test_admin_user.id,
        expires_in=timedelta(hours=1),
    )


@pytest.fixture
def client(db_session: AsyncSession) -> TestClient:
    """Create a test client.

    Note: This fixture doesn't properly handle async DB operations.
    Use async_client for async tests or manually override dependencies.
    """

    async def override_get_db():
        yield db_session

    app = create_app()
    # Override dependency would go here if needed
    return TestClient(app)


class AsyncTestClient:
    """Async test client wrapper for FastAPI."""

    def __init__(self, app, db_session: AsyncSession):
        """Initialize async test client."""
        self.app = app
        self.db_session = db_session
        self.client = TestClient(app)

    def get_headers(self, token: str) -> dict:
        """Get authorization headers."""
        return {"Authorization": f"Bearer {token}"}
