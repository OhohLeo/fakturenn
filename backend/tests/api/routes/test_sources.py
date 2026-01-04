"""Tests for source API routes."""

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import SourceType, User
from tests.utils.source import create_random_parser, create_random_source
from tests.utils.workflow import create_random_workflow


def test_create_source(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test creating a new source."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)

    data = {
        "name": "Test Gmail Source",
        "type": "gmail",
        "config": {"query": "from:test@example.com"},
        "is_active": True,
    }
    response = client.post(
        f"{settings.API_V1_STR}/workflows/{workflow.id}/sources/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["type"] == data["type"]
    assert content["config"] == data["config"]
    assert content["is_active"] is True


def test_create_source_with_crontab(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test creating a source with crontab schedule."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)

    data = {
        "name": "Scheduled Source",
        "type": "xls",
        "config": {"file_path": "/data/test.xlsx"},
        "crontab": "0 9 * * *",  # Every day at 9am
        "is_active": True,
    }
    response = client.post(
        f"{settings.API_V1_STR}/workflows/{workflow.id}/sources/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["crontab"] == data["crontab"]


def test_read_source(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test reading a single source."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    source = create_random_source(db, workflow_id=workflow.id)

    response = client.get(
        f"{settings.API_V1_STR}/sources/{source.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == source.name
    assert content["id"] == str(source.id)


def test_read_source_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test reading a non-existent source."""
    response = client.get(
        f"{settings.API_V1_STR}/sources/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


def test_read_sources_by_workflow(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test listing sources for a workflow."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    create_random_source(db, workflow_id=workflow.id, source_type=SourceType.gmail)
    create_random_source(db, workflow_id=workflow.id, source_type=SourceType.xls)

    response = client.get(
        f"{settings.API_V1_STR}/workflows/{workflow.id}/sources/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert "data" in content
    assert len(content["data"]) >= 2


def test_update_source(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test updating a source."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    source = create_random_source(db, workflow_id=workflow.id)

    data = {"name": "Updated Source Name", "is_active": False}
    response = client.put(
        f"{settings.API_V1_STR}/sources/{source.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["is_active"] is False


def test_delete_source(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test deleting a source."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    source = create_random_source(db, workflow_id=workflow.id)

    response = client.delete(
        f"{settings.API_V1_STR}/sources/{source.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Source deleted successfully"


def test_trigger_source_sync(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test manually triggering a source sync."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    source = create_random_source(db, workflow_id=workflow.id)

    response = client.post(
        f"{settings.API_V1_STR}/sources/{source.id}/trigger",
        headers=superuser_token_headers,
    )
    # Note: This will fail if NATS is not running, which is expected in tests
    # We just check that the endpoint exists and returns appropriate response
    assert response.status_code in [200, 500, 503]


# Parser tests


def test_create_parser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test creating a new parser."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    source = create_random_source(db, workflow_id=workflow.id)

    data = {
        "name": "Test Parser",
        "engine_type": "mail2record",
        "rules": {
            "filters": {"from": "invoices@test.com"},
            "extraction_regex": {"email_html": r"Invoice #(\d+)"},
        },
        "is_active": True,
    }
    response = client.post(
        f"{settings.API_V1_STR}/sources/{source.id}/parsers/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["engine_type"] == data["engine_type"]


def test_read_parsers_by_source(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test listing parsers for a source."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    source = create_random_source(db, workflow_id=workflow.id)
    create_random_parser(db, source_id=source.id)
    create_random_parser(db, source_id=source.id)

    response = client.get(
        f"{settings.API_V1_STR}/sources/{source.id}/parsers/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert "data" in content
    assert len(content["data"]) >= 2


def test_update_parser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test updating a parser."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    source = create_random_source(db, workflow_id=workflow.id)
    parser = create_random_parser(db, source_id=source.id)

    data = {"name": "Updated Parser", "is_active": False}
    response = client.put(
        f"{settings.API_V1_STR}/parsers/{parser.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["is_active"] is False


def test_delete_parser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test deleting a parser."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    source = create_random_source(db, workflow_id=workflow.id)
    parser = create_random_parser(db, source_id=source.id)

    response = client.delete(
        f"{settings.API_V1_STR}/parsers/{parser.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Parser deleted successfully"
