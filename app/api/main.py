"""FastAPI application factory and configuration."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.connection import init_db, get_db_manager
from app.core.vault_client import init_vault
from app.core.logging_config import configure_logging

logger = logging.getLogger(__name__)


def create_app(
    database_url: str = None,
    vault_addr: str = None,
    vault_role_id: str = None,
    vault_secret_id: str = None,
    vault_dev_mode: bool = False,
    nats_servers: str = None,
) -> FastAPI:
    """Create and configure FastAPI application.

    Args:
        database_url: PostgreSQL connection URL
        vault_addr: Vault server address
        vault_role_id: Vault AppRole role_id
        vault_secret_id: Vault AppRole secret_id
        vault_dev_mode: Use Vault dev mode
        nats_servers: Comma-separated NATS server URLs

    Returns:
        Configured FastAPI application
    """
    # Configure logging
    configure_logging()

    # Initialize database
    init_db(
        database_url or "postgresql+asyncpg://fakturenn:fakturenn@localhost/fakturenn"
    )

    # Initialize Vault
    init_vault(vault_addr, vault_role_id, vault_secret_id, vault_dev_mode)

    # Parse NATS servers
    nats_servers_str = nats_servers or os.getenv(
        "NATS_SERVERS", "nats://localhost:4222"
    )
    nats_server_list = [s.strip() for s in nats_servers_str.split(",")]

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Manage app lifecycle."""
        logger.info("Starting Fakturenn API")

        # Initialize NATS
        from app.nats import init_nats_client, close_nats_client

        try:
            await init_nats_client(nats_server_list)
            logger.info("NATS client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize NATS client: {e}")
            raise

        yield

        logger.info("Shutting down Fakturenn API")
        db_manager = get_db_manager()
        await db_manager.close()

        # Close NATS client
        try:
            await close_nats_client()
            logger.info("NATS client closed")
        except Exception as e:
            logger.error(f"Failed to close NATS client: {e}")

    app = FastAPI(
        title="Fakturenn API",
        description="Invoice automation and accounting integration",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:8000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok", "service": "fakturenn-api"}

    # Include routers
    from app.api.routers import (
        auth,
        users,
        automations,
        sources,
        exports,
        mappings,
        jobs,
        export_history,
        health,
    )

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
    app.include_router(
        automations.router, prefix="/api/v1/automations", tags=["automations"]
    )
    app.include_router(sources.router, prefix="/api/v1/sources", tags=["sources"])
    app.include_router(exports.router, prefix="/api/v1/exports", tags=["exports"])
    app.include_router(mappings.router, prefix="/api/v1/mappings", tags=["mappings"])
    app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["jobs"])
    app.include_router(
        export_history.router, prefix="/api/v1/export-history", tags=["export-history"]
    )
    app.include_router(health.router, prefix="/api/v1", tags=["health"])

    return app


# Application instance for Uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
