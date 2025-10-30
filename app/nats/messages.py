"""Message schemas for NATS event-driven architecture."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class JobStartedEvent(BaseModel):
    """Event published when a job starts execution."""

    job_id: int = Field(..., description="Job ID")
    automation_id: int = Field(..., description="Automation ID")
    user_id: int = Field(..., description="User ID")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    from_date: Optional[str] = Field(
        None, description="Start date for source extraction (YYYY-MM-DD)"
    )
    max_results: Optional[int] = Field(None, description="Maximum results to fetch")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": 1,
                "automation_id": 1,
                "user_id": 1,
                "started_at": "2025-10-29T18:00:00Z",
                "from_date": "2025-01-01",
                "max_results": 30,
            }
        }


class JobCompletedEvent(BaseModel):
    """Event published when a job completes successfully."""

    job_id: int = Field(..., description="Job ID")
    automation_id: int = Field(..., description="Automation ID")
    user_id: int = Field(..., description="User ID")
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    stats: Optional[Dict[str, Any]] = Field(None, description="Job statistics")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": 1,
                "automation_id": 1,
                "user_id": 1,
                "completed_at": "2025-10-29T18:30:00Z",
                "stats": {
                    "sources_executed": 2,
                    "exports_completed": 5,
                    "duration_seconds": 1800,
                },
            }
        }


class JobFailedEvent(BaseModel):
    """Event published when a job fails."""

    job_id: int = Field(..., description="Job ID")
    automation_id: int = Field(..., description="Automation ID")
    user_id: int = Field(..., description="User ID")
    failed_at: datetime = Field(default_factory=datetime.utcnow)
    error_message: str = Field(..., description="Error description")
    error_details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error context"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": 1,
                "automation_id": 1,
                "user_id": 1,
                "failed_at": "2025-10-29T18:15:00Z",
                "error_message": "Failed to initialize Paheko client",
                "error_details": {"vault_error": "Connection timeout"},
            }
        }
