"""Tests for exporter API routes."""

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import ExporterType, User
from tests.utils.exporter import create_random_exporter, create_random_mapper
from tests.utils.workflow import create_random_workflow


def test_create_exporter(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test creating a new exporter."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)

    data = {
        "name": "Test Paheko Exporter",
        "type": "paheko",
        "config": {"api_url": "https://test.paheko.cloud"},
        "is_active": True,
    }
    response = client.post(
        f"{settings.API_V1_STR}/workflows/{workflow.id}/exporters/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["type"] == data["type"]
    assert content["config"] == data["config"]
    assert content["is_active"] is True


def test_create_gdrive_exporter(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test creating a Google Drive exporter."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)

    data = {
        "name": "Test GDrive Exporter",
        "type": "gdrive",
        "config": {"folder_id": "1ABC123xyz"},
        "is_active": True,
    }
    response = client.post(
        f"{settings.API_V1_STR}/workflows/{workflow.id}/exporters/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["type"] == "gdrive"


def test_read_exporter(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test reading a single exporter."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    exporter = create_random_exporter(db, workflow_id=workflow.id)

    response = client.get(
        f"{settings.API_V1_STR}/exporters/{exporter.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == exporter.name
    assert content["id"] == str(exporter.id)


def test_read_exporter_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test reading a non-existent exporter."""
    response = client.get(
        f"{settings.API_V1_STR}/exporters/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


def test_read_exporters_by_workflow(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test listing exporters for a workflow."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    create_random_exporter(db, workflow_id=workflow.id, exporter_type=ExporterType.paheko)
    create_random_exporter(db, workflow_id=workflow.id, exporter_type=ExporterType.gdrive)

    response = client.get(
        f"{settings.API_V1_STR}/workflows/{workflow.id}/exporters/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert "data" in content
    assert len(content["data"]) >= 2


def test_update_exporter(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test updating an exporter."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    exporter = create_random_exporter(db, workflow_id=workflow.id)

    data = {"name": "Updated Exporter Name", "is_active": False}
    response = client.put(
        f"{settings.API_V1_STR}/exporters/{exporter.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["is_active"] is False


def test_delete_exporter(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test deleting an exporter."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    exporter = create_random_exporter(db, workflow_id=workflow.id)

    response = client.delete(
        f"{settings.API_V1_STR}/exporters/{exporter.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Exporter deleted successfully"


# Mapper tests


def test_create_mapper(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test creating a new mapper."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    exporter = create_random_exporter(db, workflow_id=workflow.id)

    data = {
        "name": "Test Mapper",
        "mapper_type": "record2paheko",
        "transformation_logic": {
            "transaction_type": "EXPENSE",
            "label_template": "{invoice_id} - {month}",
            "debit_account": "601",
            "credit_account": "512A",
        },
        "is_active": True,
    }
    response = client.post(
        f"{settings.API_V1_STR}/exporters/{exporter.id}/mappers/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["mapper_type"] == data["mapper_type"]


def test_create_gdrive_mapper(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test creating a Google Drive mapper."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    exporter = create_random_exporter(
        db, workflow_id=workflow.id, exporter_type=ExporterType.gdrive
    )

    data = {
        "name": "GDrive Mapper",
        "mapper_type": "record2gdrive",
        "transformation_logic": {
            "filename_template": "{date}_{invoice_id}.pdf",
            "folder_structure": "{year}/{month}",
            "skip_if_no_file": True,
        },
        "is_active": True,
    }
    response = client.post(
        f"{settings.API_V1_STR}/exporters/{exporter.id}/mappers/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["mapper_type"] == "record2gdrive"


def test_read_mappers_by_exporter(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test listing mappers for an exporter."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    exporter = create_random_exporter(db, workflow_id=workflow.id)
    create_random_mapper(db, exporter_id=exporter.id)
    create_random_mapper(db, exporter_id=exporter.id)

    response = client.get(
        f"{settings.API_V1_STR}/exporters/{exporter.id}/mappers/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert "data" in content
    assert len(content["data"]) >= 2


def test_update_mapper(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test updating a mapper."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    exporter = create_random_exporter(db, workflow_id=workflow.id)
    mapper = create_random_mapper(db, exporter_id=exporter.id)

    data = {"name": "Updated Mapper", "is_active": False}
    response = client.put(
        f"{settings.API_V1_STR}/mappers/{mapper.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["is_active"] is False


def test_delete_mapper(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test deleting a mapper."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    exporter = create_random_exporter(db, workflow_id=workflow.id)
    mapper = create_random_mapper(db, exporter_id=exporter.id)

    response = client.delete(
        f"{settings.API_V1_STR}/mappers/{mapper.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Mapper deleted successfully"
