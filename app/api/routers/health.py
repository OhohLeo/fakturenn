"""Health check endpoints."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.core.vault_client import get_vault_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint.

    Verifies:
    - API is running
    - Database connection is working
    - Vault client is initialized

    Args:
        db: Database session

    Returns:
        Health status
    """
    try:
        # Test database connection
        await db.execute("SELECT 1")

        # Check Vault
        vault = get_vault_client()
        vault_status = "connected" if vault.client else "disconnected"

        return {
            "status": "healthy",
            "service": "fakturenn-api",
            "database": "connected",
            "vault": vault_status,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "fakturenn-api",
            "error": str(e),
        }
