from fastapi import APIRouter

from app.api.routes import (
    exporters,
    jobs,
    login,
    private,
    records,
    schemas,
    sources,
    users,
    utils,
    workflows,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(workflows.router)
api_router.include_router(sources.router)
api_router.include_router(exporters.router)
api_router.include_router(records.router)
api_router.include_router(jobs.router)
api_router.include_router(schemas.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
