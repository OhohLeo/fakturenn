"""Source management endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_current_user
from app.api.schemas.source import SourceCreate, SourceResponse, SourceUpdate
from app.db.models import Source, Automation, User

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("", response_model=list[SourceResponse])
async def list_sources(
    automation_id: int = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List sources."""
    query = select(Source)
    if automation_id:
        # Verify automation belongs to user
        stmt = select(Automation).where(
            (Automation.id == automation_id) & (Automation.user_id == current_user.id)
        )
        result = await db.execute(stmt)
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        query = query.where(Source.automation_id == automation_id)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return [SourceResponse.from_orm(s) for s in result.scalars().all()]

@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    source_data: SourceCreate,
    automation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create source."""
    stmt = select(Automation).where(
        (Automation.id == automation_id) & (Automation.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    db_source = Source(
        automation_id=automation_id,
        **source_data.dict()
    )
    db.add(db_source)
    await db.commit()
    await db.refresh(db_source)
    return SourceResponse.from_orm(db_source)

@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(source_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get source."""
    stmt = select(Source).where(Source.id == source_id)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return SourceResponse.from_orm(source)

@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(source_id: int, source_update: SourceUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Update source."""
    stmt = select(Source).where(Source.id == source_id)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    for key, value in source_update.dict(exclude_unset=True).items():
        setattr(source, key, value)
    await db.commit()
    await db.refresh(source)
    return SourceResponse.from_orm(source)

@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(source_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Delete source."""
    stmt = select(Source).where(Source.id == source_id)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await db.delete(source)
    await db.commit()
