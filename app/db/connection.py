"""Database connection and session management."""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages async database connections and sessions."""

    def __init__(self, database_url: str):
        """Initialize database manager.

        Args:
            database_url: PostgreSQL async URL (postgresql+asyncpg://...)
        """
        self.database_url = database_url
        self.engine = None
        self.SessionLocal = None

    def initialize(self):
        """Initialize the database engine and session factory."""
        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            poolclass=NullPool,  # For edge functions / serverless, use NullPool
        )
        self.SessionLocal = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        logger.info(f"Database initialized: {self.database_url}")

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an async database session.

        Yields:
            AsyncSession: Database session
        """
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        async with self.SessionLocal() as session:
            yield session

    async def close(self):
        """Close the database engine."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection closed")


# Global database manager instance
db_manager = None


def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    if db_manager is None:
        raise RuntimeError("Database manager not initialized")
    return db_manager


def init_db(database_url: str) -> DatabaseManager:
    """Initialize the global database manager.

    Args:
        database_url: PostgreSQL async URL

    Returns:
        DatabaseManager: The initialized database manager
    """
    global db_manager
    db_manager = DatabaseManager(database_url)
    db_manager.initialize()
    return db_manager
