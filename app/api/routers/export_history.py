"""Export history (audit) endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_current_user
from app.db.models import ExportHistory, User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def list_export_history(
    job_id: int = None,
    export_id: int = None,
    status_filter: str = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List export history."""
    query = select(ExportHistory)
    if job_id:
        query = query.where(ExportHistory.job_id == job_id)
    if export_id:
        query = query.where(ExportHistory.export_id == export_id)
    if status_filter:
        query = query.where(ExportHistory.status == status_filter)
    query = query.order_by(ExportHistory.exported_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return [
        {
            "id": h.id,
            "export_type": h.export_type,
            "status": h.status,
            "exported_at": h.exported_at,
            "context": h.context,
        }
        for h in result.scalars().all()
    ]


@router.get("/{history_id}")
async def get_export_history(
    history_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get export history details."""
    stmt = select(ExportHistory).where(ExportHistory.id == history_id)
    result = await db.execute(stmt)
    history = result.scalar_one_or_none()
    if not history:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return {
        "id": history.id,
        "job_id": history.job_id,
        "export_id": history.export_id,
        "export_type": history.export_type,
        "status": history.status,
        "context": history.context,
        "external_reference": history.external_reference,
        "error_message": history.error_message,
    }
