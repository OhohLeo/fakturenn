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


class SourceExecuteEvent(BaseModel):
    """Event published to execute a source within a job."""

    job_id: int = Field(..., description="Parent job ID")
    automation_id: int = Field(..., description="Automation ID")
    user_id: int = Field(..., description="User ID")
    source_id: int = Field(..., description="Source ID to execute")
    source_type: str = Field(
        ..., description="Source type (FreeInvoice, FreeMobileInvoice, Gmail)"
    )
    source_name: str = Field(..., description="Source name")
    from_date: Optional[str] = Field(
        None, description="Start date for extraction (YYYY-MM-DD)"
    )
    max_results: Optional[int] = Field(None, description="Maximum results to fetch")
    extraction_params: Optional[Dict[str, Any]] = Field(
        None, description="Extraction parameters"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": 1,
                "automation_id": 1,
                "user_id": 1,
                "source_id": 1,
                "source_type": "Gmail",
                "source_name": "Free ISP Invoices",
                "from_date": "2025-01-01",
                "max_results": 30,
                "extraction_params": {
                    "email_from": "facture@free.fr",
                    "subject_contains": "Facture",
                },
            }
        }


class ExportExecuteEvent(BaseModel):
    """Event published to execute exports for extracted invoices."""

    job_id: int = Field(..., description="Parent job ID")
    automation_id: int = Field(..., description="Automation ID")
    user_id: int = Field(..., description="User ID")
    source_id: int = Field(..., description="Source ID that provided the invoice")
    export_ids: list[int] = Field(..., description="Export IDs to execute")
    invoice_data: Dict[str, Any] = Field(..., description="Invoice data to export")
    context: Dict[str, Any] = Field(..., description="Export context variables")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": 1,
                "automation_id": 1,
                "user_id": 1,
                "source_id": 1,
                "export_ids": [1, 2],
                "invoice_data": {
                    "file_path": "/tmp/facture.pdf",
                    "amount_eur": 99.99,
                },
                "context": {
                    "invoice_id": "INV-001",
                    "date": "2025-10-29",
                    "amount_eur": 99.99,
                    "month": "10",
                    "year": "2025",
                },
            }
        }


class ExportCompletedEvent(BaseModel):
    """Event published when an export completes successfully."""

    job_id: int = Field(..., description="Parent job ID")
    export_id: int = Field(..., description="Export ID that completed")
    automation_id: int = Field(..., description="Automation ID")
    user_id: int = Field(..., description="User ID")
    external_reference: str = Field(..., description="Reference from external system")
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    export_type: str = Field(
        ..., description="Export type (Paheko, LocalStorage, GoogleDrive)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": 1,
                "export_id": 1,
                "automation_id": 1,
                "user_id": 1,
                "external_reference": "12345",
                "completed_at": "2025-10-29T18:05:00Z",
                "export_type": "Paheko",
            }
        }


class ExportFailedEvent(BaseModel):
    """Event published when an export fails."""

    job_id: int = Field(..., description="Parent job ID")
    export_id: int = Field(..., description="Export ID that failed")
    automation_id: int = Field(..., description="Automation ID")
    user_id: int = Field(..., description="User ID")
    failed_at: datetime = Field(default_factory=datetime.utcnow)
    error_message: str = Field(..., description="Error description")
    export_type: str = Field(
        ..., description="Export type (Paheko, LocalStorage, GoogleDrive)"
    )
    error_details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error context"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": 1,
                "export_id": 1,
                "automation_id": 1,
                "user_id": 1,
                "failed_at": "2025-10-29T18:05:00Z",
                "error_message": "Paheko API returned 500",
                "export_type": "Paheko",
                "error_details": {"api_response": "Internal server error"},
            }
        }
