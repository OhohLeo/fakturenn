"""Automation management endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_db, get_current_user
from app.api.schemas.automation import (
    AutomationCreate,
    AutomationResponse,
    AutomationUpdate,
    AutomationWithRelations,
)
from app.db.models import Automation, User, Job

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[AutomationResponse])
async def list_automations(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List automations for current user.

    Args:
        skip: Pagination skip
        limit: Pagination limit
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of automations
    """
    stmt = (
        select(Automation)
        .where(Automation.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    automations = result.scalars().all()
    return [AutomationResponse.from_orm(a) for a in automations]


@router.post("", response_model=AutomationResponse, status_code=status.HTTP_201_CREATED)
async def create_automation(
    automation_data: AutomationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create new automation.

    Args:
        automation_data: Automation creation data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Created automation

    Raises:
        HTTPException: If automation name already exists for user
    """
    # Check if automation with same name exists
    stmt = select(Automation).where(
        (Automation.user_id == current_user.id) & (Automation.name == automation_data.name)
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Automation with this name already exists",
        )

    # Create automation
    db_automation = Automation(
        user_id=current_user.id,
        name=automation_data.name,
        description=automation_data.description,
        schedule=automation_data.schedule,
        from_date_rule=automation_data.from_date_rule,
        active=automation_data.active,
    )

    db.add(db_automation)
    await db.commit()
    await db.refresh(db_automation)

    logger.info(f"Automation '{db_automation.name}' created by {current_user.username}")

    return AutomationResponse.from_orm(db_automation)


@router.get("/{automation_id}", response_model=AutomationResponse)
async def get_automation(
    automation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get automation by ID.

    Args:
        automation_id: Automation ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Automation

    Raises:
        HTTPException: If automation not found or not owned by user
    """
    stmt = select(Automation).where(
        (Automation.id == automation_id) & (Automation.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    automation = result.scalar_one_or_none()

    if not automation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation not found",
        )

    return AutomationResponse.from_orm(automation)


@router.put("/{automation_id}", response_model=AutomationResponse)
async def update_automation(
    automation_id: int,
    automation_update: AutomationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update automation.

    Args:
        automation_id: Automation ID
        automation_update: Update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated automation

    Raises:
        HTTPException: If automation not found
    """
    stmt = select(Automation).where(
        (Automation.id == automation_id) & (Automation.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    automation = result.scalar_one_or_none()

    if not automation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation not found",
        )

    # Update fields
    if automation_update.name:
        automation.name = automation_update.name
    if automation_update.description is not None:
        automation.description = automation_update.description
    if automation_update.schedule is not None:
        automation.schedule = automation_update.schedule
    if automation_update.from_date_rule is not None:
        automation.from_date_rule = automation_update.from_date_rule
    if automation_update.active is not None:
        automation.active = automation_update.active

    await db.commit()
    await db.refresh(automation)

    logger.info(f"Automation '{automation.name}' updated by {current_user.username}")

    return AutomationResponse.from_orm(automation)


@router.delete("/{automation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_automation(
    automation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete automation and related jobs, sources, exports.

    Args:
        automation_id: Automation ID
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: If automation not found
    """
    stmt = select(Automation).where(
        (Automation.id == automation_id) & (Automation.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    automation = result.scalar_one_or_none()

    if not automation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation not found",
        )

    automation_name = automation.name
    await db.delete(automation)
    await db.commit()

    logger.info(f"Automation '{automation_name}' deleted by {current_user.username}")


@router.post("/{automation_id}/trigger")
async def trigger_automation(
    automation_id: int,
    from_date: str = None,
    max_results: int = 30,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger automation execution.

    Args:
        automation_id: Automation ID
        from_date: Start date for invoice retrieval
        max_results: Max results to process
        current_user: Current authenticated user
        db: Database session

    Returns:
        Job ID

    Raises:
        HTTPException: If automation not found
    """
    stmt = select(Automation).where(
        (Automation.id == automation_id) & (Automation.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    automation = result.scalar_one_or_none()

    if not automation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation not found",
        )

    # Create job (will be picked up by workers via NATS)
    from app.db.models import Job
    from datetime import datetime, date

    job = Job(
        automation_id=automation_id,
        status="pending",
        from_date=datetime.fromisoformat(from_date).date() if from_date else None,
        max_results=max_results,
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)

    logger.info(f"Job {job.id} triggered for automation '{automation.name}' by {current_user.username}")

    # TODO: Publish job trigger event to NATS
    # nats_client.publish("fakturenn.jobs.trigger", job_data)

    return {"job_id": job.id, "status": "pending"}


@router.get("/{automation_id}/jobs")
async def get_automation_jobs(
    automation_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get jobs for automation.

    Args:
        automation_id: Automation ID
        skip: Pagination skip
        limit: Pagination limit
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of jobs

    Raises:
        HTTPException: If automation not found
    """
    # Verify automation exists and belongs to user
    stmt = select(Automation).where(
        (Automation.id == automation_id) & (Automation.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    automation = result.scalar_one_or_none()

    if not automation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation not found",
        )

    # Get jobs
    stmt = (
        select(Job)
        .where(Job.automation_id == automation_id)
        .order_by(Job.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    jobs = result.scalars().all()

    return [
        {
            "id": job.id,
            "status": job.status,
            "from_date": job.from_date,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "error_message": job.error_message,
            "stats": job.stats,
            "created_at": job.created_at,
        }
        for job in jobs
    ]
