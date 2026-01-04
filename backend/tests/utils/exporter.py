"""Test utilities for Exporter, Mapper models."""

import random
import string
from uuid import UUID

from sqlmodel import Session

from app.models import Exporter, ExporterType, Mapper, MapperType


def random_exporter_name() -> str:
    """Generate a random exporter name."""
    return "".join(random.choices(string.ascii_lowercase, k=10))


def create_random_exporter(
    db: Session,
    workflow_id: UUID,
    exporter_type: ExporterType = ExporterType.paheko,
) -> Exporter:
    """Create a random exporter for testing."""
    exporter = Exporter(
        name=random_exporter_name(),
        workflow_id=workflow_id,
        type=exporter_type,
        config={"api_url": "https://test.paheko.cloud"},
        is_active=True,
    )
    db.add(exporter)
    db.commit()
    db.refresh(exporter)
    return exporter


def create_random_mapper(
    db: Session,
    exporter_id: UUID,
    mapper_type: MapperType = MapperType.record2paheko,
) -> Mapper:
    """Create a random mapper for testing."""
    mapper = Mapper(
        name=f"mapper_{random.randint(1, 1000)}",
        exporter_id=exporter_id,
        mapper_type=mapper_type,
        transformation_logic={
            "transaction_type": "EXPENSE",
            "label_template": "{invoice_id}",
            "debit_account": "601",
            "credit_account": "512",
        },
        is_active=True,
    )
    db.add(mapper)
    db.commit()
    db.refresh(mapper)
    return mapper
