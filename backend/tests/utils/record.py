"""Test utilities for Record model."""

import random
from datetime import date, timedelta
from uuid import UUID

from sqlmodel import Session

from app.models import Record, RecordStatus


def create_random_record(
    db: Session,
    source_id: UUID,
    workflow_id: UUID,
    status: RecordStatus = RecordStatus.pending,
) -> Record:
    """Create a random record for testing."""
    record_date = date.today() - timedelta(days=random.randint(0, 30))
    data = {
        "invoice_id": f"INV-{random.randint(1000, 9999)}",
        "amount_text": f"{random.randint(10, 1000)},00 €",
        "description": f"Test invoice {random.randint(1, 100)}",
    }

    # Compute unique key
    unique_key = Record.compute_unique_key(
        source_id=source_id,
        date=record_date,
        file_content=None,
        data=data,
    )

    record = Record(
        source_id=source_id,
        workflow_id=workflow_id,
        date=record_date,
        data=data,
        unique_key=unique_key,
        status=status,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
