"""Source-Export mapping endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_current_user
from app.api.schemas.export import SourceExportMappingResponse, SourceExportMappingBase
from app.db.models import SourceExportMapping, Source, Export, Automation, User

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("", response_model=list[SourceExportMappingResponse])
async def list_mappings(
    source_id: int = None,
    export_id: int = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List mappings."""
    query = select(SourceExportMapping)
    if source_id:
        query = query.where(SourceExportMapping.source_id == source_id)
    if export_id:
        query = query.where(SourceExportMapping.export_id == export_id)
    result = await db.execute(query)
    return [SourceExportMappingResponse.from_orm(m) for m in result.scalars().all()]

@router.post("", response_model=SourceExportMappingResponse, status_code=status.HTTP_201_CREATED)
async def create_mapping(
    mapping_data: SourceExportMappingBase,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create mapping."""
    db_mapping = SourceExportMapping(**mapping_data.dict())
    db.add(db_mapping)
    await db.commit()
    await db.refresh(db_mapping)
    return SourceExportMappingResponse.from_orm(db_mapping)

@router.delete("/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mapping(mapping_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Delete mapping."""
    stmt = select(SourceExportMapping).where(SourceExportMapping.id == mapping_id)
    result = await db.execute(stmt)
    mapping = result.scalar_one_or_none()
    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await db.delete(mapping)
    await db.commit()
