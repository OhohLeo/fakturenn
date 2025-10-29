"""Automation schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AutomationBase(BaseModel):
    """Base automation schema."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    schedule: Optional[str] = None
    from_date_rule: Optional[str] = None
    active: bool = True


class AutomationCreate(AutomationBase):
    """Automation creation schema."""

    pass


class AutomationUpdate(BaseModel):
    """Automation update schema."""

    name: Optional[str] = None
    description: Optional[str] = None
    schedule: Optional[str] = None
    from_date_rule: Optional[str] = None
    active: Optional[bool] = None


class AutomationResponse(AutomationBase):
    """Automation response schema."""

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AutomationWithRelations(AutomationResponse):
    """Automation with sources and exports."""

    sources: list = Field(default_factory=list)
    exports: list = Field(default_factory=list)
    jobs_count: int = 0
