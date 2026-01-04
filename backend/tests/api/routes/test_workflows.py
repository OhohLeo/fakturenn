"""Tests for workflow API routes."""

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import User
from tests.utils.workflow import create_random_workflow


def test_create_workflow(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test creating a new workflow."""
    data = {"name": "Test Workflow", "description": "A test workflow"}
    response = client.post(
        f"{settings.API_V1_STR}/workflows/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert "id" in content
    assert "owner_id" in content


def test_create_workflow_without_description(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test creating a workflow without description."""
    data = {"name": "Workflow No Desc"}
    response = client.post(
        f"{settings.API_V1_STR}/workflows/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] is None


def test_read_workflow(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test reading a single workflow."""
    # Get the superuser
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)

    response = client.get(
        f"{settings.API_V1_STR}/workflows/{workflow.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == workflow.name
    assert content["id"] == str(workflow.id)


def test_read_workflow_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test reading a non-existent workflow."""
    response = client.get(
        f"{settings.API_V1_STR}/workflows/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Workflow not found"


def test_read_workflows(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test listing workflows."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    create_random_workflow(db, owner_id=user.id)
    create_random_workflow(db, owner_id=user.id)

    response = client.get(
        f"{settings.API_V1_STR}/workflows/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert "data" in content
    assert len(content["data"]) >= 2


def test_update_workflow(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test updating a workflow."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)

    data = {"name": "Updated Workflow", "description": "Updated description"}
    response = client.put(
        f"{settings.API_V1_STR}/workflows/{workflow.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]


def test_update_workflow_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test updating a non-existent workflow."""
    data = {"name": "Updated Name"}
    response = client.put(
        f"{settings.API_V1_STR}/workflows/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 404


def test_delete_workflow(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test deleting a workflow."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)

    response = client.delete(
        f"{settings.API_V1_STR}/workflows/{workflow.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Workflow deleted successfully"


def test_delete_workflow_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test deleting a non-existent workflow."""
    response = client.delete(
        f"{settings.API_V1_STR}/workflows/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


def test_workflow_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Test that normal users can only access their own workflows."""
    # Create workflow owned by superuser
    superuser = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=superuser.id)

    # Normal user should not be able to access it
    response = client.get(
        f"{settings.API_V1_STR}/workflows/{workflow.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 400
    content = response.json()
    assert content["detail"] == "Not enough permissions"
