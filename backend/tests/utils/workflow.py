"""Test utilities for Workflow model."""

import random
import string
from uuid import UUID

from sqlmodel import Session

from app.models import Workflow


def random_workflow_name() -> str:
    """Generate a random workflow name."""
    return "".join(random.choices(string.ascii_lowercase, k=10))


def create_random_workflow(db: Session, owner_id: UUID) -> Workflow:
    """Create a random workflow for testing."""
    workflow = Workflow(
        name=random_workflow_name(),
        description=f"Test workflow {random.randint(1, 1000)}",
        owner_id=owner_id,
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return workflow
