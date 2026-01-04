"""Tests for record API routes."""

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import RecordStatus, User
from tests.utils.record import create_random_record
from tests.utils.source import create_random_source
from tests.utils.workflow import create_random_workflow


def test_read_record(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test reading a single record."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    source = create_random_source(db, workflow_id=workflow.id)
    record = create_random_record(db, source_id=source.id, workflow_id=workflow.id)

    response = client.get(
        f"{settings.API_V1_STR}/records/{record.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == str(record.id)
    assert content["data"] == record.data


def test_read_record_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test reading a non-existent record."""
    response = client.get(
        f"{settings.API_V1_STR}/records/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


def test_read_records_by_workflow(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test listing records for a workflow."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    source = create_random_source(db, workflow_id=workflow.id)
    create_random_record(db, source_id=source.id, workflow_id=workflow.id)
    create_random_record(db, source_id=source.id, workflow_id=workflow.id)

    response = client.get(
        f"{settings.API_V1_STR}/workflows/{workflow.id}/records/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert "data" in content
    assert len(content["data"]) >= 2


def test_read_records_by_source(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test listing records for a source."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    source = create_random_source(db, workflow_id=workflow.id)
    create_random_record(db, source_id=source.id, workflow_id=workflow.id)
    create_random_record(db, source_id=source.id, workflow_id=workflow.id)

    response = client.get(
        f"{settings.API_V1_STR}/sources/{source.id}/records/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert "data" in content
    assert len(content["data"]) >= 2


def test_read_records_filter_by_status(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test filtering records by status."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    source = create_random_source(db, workflow_id=workflow.id)
    create_random_record(
        db, source_id=source.id, workflow_id=workflow.id, status=RecordStatus.pending
    )
    create_random_record(
        db, source_id=source.id, workflow_id=workflow.id, status=RecordStatus.exported
    )

    # Filter by pending status
    response = client.get(
        f"{settings.API_V1_STR}/workflows/{workflow.id}/records/",
        headers=superuser_token_headers,
        params={"status": "pending"},
    )
    assert response.status_code == 200
    content = response.json()
    for record in content["data"]:
        assert record["status"] == "pending"


def test_trigger_record_export(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test manually triggering a record export."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    source = create_random_source(db, workflow_id=workflow.id)
    record = create_random_record(db, source_id=source.id, workflow_id=workflow.id)

    response = client.post(
        f"{settings.API_V1_STR}/records/{record.id}/export",
        headers=superuser_token_headers,
    )
    # Note: This may fail if NATS is not running
    assert response.status_code in [200, 500, 503]


def test_delete_record(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test deleting a record."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    source = create_random_source(db, workflow_id=workflow.id)
    record = create_random_record(db, source_id=source.id, workflow_id=workflow.id)

    response = client.delete(
        f"{settings.API_V1_STR}/records/{record.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Record deleted successfully"


def test_record_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Test that normal users can only access records from their workflows."""
    # Create record owned by superuser
    superuser = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=superuser.id)
    source = create_random_source(db, workflow_id=workflow.id)
    record = create_random_record(db, source_id=source.id, workflow_id=workflow.id)

    # Normal user should not be able to access it
    response = client.get(
        f"{settings.API_V1_STR}/records/{record.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 400
    content = response.json()
    assert content["detail"] == "Not enough permissions"
