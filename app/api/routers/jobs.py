"""Job management endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_current_user
from app.db.models import Job, User

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("")
async def list_jobs(
    automation_id: int = None,
    status_filter: str = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List jobs."""
    query = select(Job)
    if automation_id:
        query = query.where(Job.automation_id == automation_id)
    if status_filter:
        query = query.where(Job.status == status_filter)
    query = query.order_by(Job.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return [{"id": j.id, "status": j.status, "created_at": j.created_at} for j in result.scalars().all()]

@router.get("/{job_id}")
async def get_job(job_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get job details."""
    stmt = select(Job).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return {"id": job.id, "status": job.status, "stats": job.stats}

@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_job(job_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Cancel running job."""
    stmt = select(Job).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if job.status not in ("pending", "running"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only cancel pending/running jobs")
    job.status = "cancelled"
    await db.commit()
