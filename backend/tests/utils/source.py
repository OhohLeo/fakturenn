"""Test utilities for Source, Parser models."""

import random
import string
from uuid import UUID

from sqlmodel import Session

from app.models import Parser, ParserEngineType, Source, SourceType


def random_source_name() -> str:
    """Generate a random source name."""
    return "".join(random.choices(string.ascii_lowercase, k=10))


def create_random_source(
    db: Session,
    workflow_id: UUID,
    source_type: SourceType = SourceType.gmail,
) -> Source:
    """Create a random source for testing."""
    source = Source(
        name=random_source_name(),
        workflow_id=workflow_id,
        type=source_type,
        config={"test_key": "test_value"},
        is_active=True,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def create_random_parser(
    db: Session,
    source_id: UUID,
    engine_type: ParserEngineType = ParserEngineType.mail2record,
) -> Parser:
    """Create a random parser for testing."""
    parser = Parser(
        name=f"parser_{random.randint(1, 1000)}",
        source_id=source_id,
        engine_type=engine_type,
        rules={"test_rule": "test_value"},
        is_active=True,
    )
    db.add(parser)
    db.commit()
    db.refresh(parser)
    return parser
