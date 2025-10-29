"""Export management endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_current_user
from app.api.schemas.export import ExportCreate, ExportResponse, ExportUpdate
from app.db.models import Export, Automation, User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=list[ExportResponse])
async def list_exports(
    automation_id: int = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List exports."""
    query = select(Export)
    if automation_id:
        stmt = select(Automation).where(
            (Automation.id == automation_id) & (Automation.user_id == current_user.id)
        )
        result = await db.execute(stmt)
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        query = query.where(Export.automation_id == automation_id)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return [ExportResponse.from_orm(e) for e in result.scalars().all()]


@router.post("", response_model=ExportResponse, status_code=status.HTTP_201_CREATED)
async def create_export(
    export_data: ExportCreate,
    automation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create export."""
    stmt = select(Automation).where(
        (Automation.id == automation_id) & (Automation.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    db_export = Export(
        automation_id=automation_id,
        name=export_data.name,
        type=export_data.type,
        configuration=export_data.configuration.dict(),
        active=export_data.active,
    )
    db.add(db_export)
    await db.commit()
    await db.refresh(db_export)
    return ExportResponse.from_orm(db_export)


@router.get("/{export_id}", response_model=ExportResponse)
async def get_export(
    export_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get export."""
    stmt = select(Export).where(Export.id == export_id)
    result = await db.execute(stmt)
    export = result.scalar_one_or_none()
    if not export:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return ExportResponse.from_orm(export)


@router.put("/{export_id}", response_model=ExportResponse)
async def update_export(
    export_id: int,
    export_update: ExportUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update export."""
    stmt = select(Export).where(Export.id == export_id)
    result = await db.execute(stmt)
    export = result.scalar_one_or_none()
    if not export:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if export_update.name:
        export.name = export_update.name
    if export_update.configuration:
        export.configuration = export_update.configuration.dict()
    if export_update.active is not None:
        export.active = export_update.active

    await db.commit()
    await db.refresh(export)
    return ExportResponse.from_orm(export)


@router.delete("/{export_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_export(
    export_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete export."""
    stmt = select(Export).where(Export.id == export_id)
    result = await db.execute(stmt)
    export = result.scalar_one_or_none()
    if not export:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await db.delete(export)
    await db.commit()
