"""Source schemas."""

from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field


class SourceBase(BaseModel):
    """Base source schema."""

    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., description="FreeInvoice, FreeMobileInvoice, or Gmail")
    email_sender_from: Optional[str] = None
    email_subject_contains: Optional[str] = None
    extraction_params: Optional[Dict[str, Any]] = None
    max_results: int = 30
    active: bool = True


class SourceCreate(SourceBase):
    """Source creation schema."""

    pass


class SourceUpdate(BaseModel):
    """Source update schema."""

    name: Optional[str] = None
    email_sender_from: Optional[str] = None
    email_subject_contains: Optional[str] = None
    extraction_params: Optional[Dict[str, Any]] = None
    max_results: Optional[int] = None
    active: Optional[bool] = None


class SourceResponse(SourceBase):
    """Source response schema."""

    id: int
    automation_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
