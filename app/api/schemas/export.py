"""Export schemas."""

from datetime import datetime
from typing import Optional, Dict, Any, Union

from pydantic import BaseModel, Field


# Export configurations for different types
class PahekoExportConfig(BaseModel):
    """Paheko export configuration."""

    paheko_type: str = Field(..., description="EXPENSE, REVENUE, TRANSFER, ADVANCED")
    label_template: str = Field(
        ...,
        description="Template with {invoice_id}, {month}, {date}, {year}, {quarter}",
    )
    debit: str = Field(..., description="Debit account code(s)")
    credit: str = Field(..., description="Credit account code(s)")


class LocalStorageExportConfig(BaseModel):
    """Local storage export configuration."""

    base_path: str = Field(default="factures")
    path_template: str = Field(
        default="{year}/{month}/{source}_{invoice_id}.pdf",
        description="Template with {year}, {month}, {quarter}, {invoice_id}, {source}, {date}, {amount}",
    )
    create_directories: bool = True


class GoogleDriveExportConfig(BaseModel):
    """Google Drive export configuration."""

    parent_folder_id: Optional[str] = None
    path_template: str = Field(
        default="{year}/{month}/{source}_{invoice_id}.pdf",
        description="Template with {year}, {month}, {quarter}, {invoice_id}, {source}, {date}, {amount}",
    )
    create_folders: bool = True
    share_with: list[str] = Field(default_factory=list)


# Base export schemas
class ExportBase(BaseModel):
    """Base export schema."""

    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., description="Paheko, LocalStorage, or GoogleDrive")
    active: bool = True


class ExportCreate(ExportBase):
    """Export creation schema."""

    configuration: Union[
        PahekoExportConfig, LocalStorageExportConfig, GoogleDriveExportConfig
    ]


class ExportUpdate(BaseModel):
    """Export update schema."""

    name: Optional[str] = None
    configuration: Optional[
        Union[PahekoExportConfig, LocalStorageExportConfig, GoogleDriveExportConfig]
    ] = None
    active: Optional[bool] = None


class ExportResponse(ExportBase):
    """Export response schema."""

    id: int
    automation_id: int
    configuration: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Mapping schemas
class SourceExportMappingBase(BaseModel):
    """Base mapping schema."""

    source_id: int
    export_id: int
    priority: int = 1
    conditions: Optional[Dict[str, Any]] = None


class SourceExportMappingResponse(SourceExportMappingBase):
    """Mapping response schema."""

    id: int
    created_at: datetime

    class Config:
        from_attributes = True
