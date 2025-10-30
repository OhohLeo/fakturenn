#!/usr/bin/env python3
"""Script to run the job worker process."""

import asyncio
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def load_env_file():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        logger.info(f"Loading environment variables from {env_path}")
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip("\"'")
                    os.environ[key] = value


def main():
    """Run the job worker."""
    load_env_file()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Get configuration from environment
    db_url = os.getenv("DATABASE_URL")
    nats_servers_str = os.getenv("NATS_SERVERS", "nats://localhost:4222")

    if not db_url:
        raise ValueError("DATABASE_URL environment variable is required")

    # Parse NATS servers (comma-separated)
    nats_servers = [s.strip() for s in nats_servers_str.split(",")]

    logger.info(f"Starting job worker with NATS servers: {nats_servers}")
    logger.info(f"Using database: {db_url}")

    # Import and run worker
    from app.workers.job_worker import run_job_worker

    asyncio.run(run_job_worker(nats_servers, db_url))


if __name__ == "__main__":
    main()
