"""Tests for job API routes."""

import uuid
from datetime import datetime

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import Job, JobStatus, User
from tests.utils.source import create_random_source
from tests.utils.workflow import create_random_workflow


def create_random_job(
    db: Session,
    source_id: uuid.UUID,
    status: JobStatus = JobStatus.queued,
) -> Job:
    """Create a random job for testing."""
    job = Job(
        source_id=source_id,
        scheduled_at=datetime.utcnow(),
        status=status,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def test_read_job(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test reading a single job."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    source = create_random_source(db, workflow_id=workflow.id)
    job = create_random_job(db, source_id=source.id)

    response = client.get(
        f"{settings.API_V1_STR}/jobs/{job.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == str(job.id)
    assert content["status"] == job.status.value


def test_read_job_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test reading a non-existent job."""
    response = client.get(
        f"{settings.API_V1_STR}/jobs/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


def test_read_jobs_by_source(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test listing jobs for a source."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    source = create_random_source(db, workflow_id=workflow.id)
    create_random_job(db, source_id=source.id, status=JobStatus.queued)
    create_random_job(db, source_id=source.id, status=JobStatus.success)

    response = client.get(
        f"{settings.API_V1_STR}/sources/{source.id}/jobs/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert "data" in content
    assert len(content["data"]) >= 2


def test_read_jobs_by_workflow(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test listing jobs for a workflow."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    source1 = create_random_source(db, workflow_id=workflow.id)
    source2 = create_random_source(db, workflow_id=workflow.id)
    create_random_job(db, source_id=source1.id)
    create_random_job(db, source_id=source2.id)

    response = client.get(
        f"{settings.API_V1_STR}/workflows/{workflow.id}/jobs/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert "data" in content
    assert len(content["data"]) >= 2


def test_read_jobs_filter_by_status(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test filtering jobs by status."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    source = create_random_source(db, workflow_id=workflow.id)
    create_random_job(db, source_id=source.id, status=JobStatus.queued)
    create_random_job(db, source_id=source.id, status=JobStatus.success)
    create_random_job(db, source_id=source.id, status=JobStatus.failed)

    # Filter by success status
    response = client.get(
        f"{settings.API_V1_STR}/sources/{source.id}/jobs/",
        headers=superuser_token_headers,
        params={"status": "success"},
    )
    assert response.status_code == 200
    content = response.json()
    for job in content["data"]:
        assert job["status"] == "success"


def test_job_with_error_context(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test reading a failed job with error context."""
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=user.id)
    source = create_random_source(db, workflow_id=workflow.id)

    # Create failed job with error context
    job = Job(
        source_id=source.id,
        scheduled_at=datetime.utcnow(),
        started_at=datetime.utcnow(),
        status=JobStatus.failed,
        error_context={"error": "Connection timeout", "retry_count": 3},
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    response = client.get(
        f"{settings.API_V1_STR}/jobs/{job.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["status"] == "failed"
    assert content["error_context"]["error"] == "Connection timeout"


def test_job_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Test that normal users can only access jobs from their workflows."""
    # Create job owned by superuser's source
    superuser = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    workflow = create_random_workflow(db, owner_id=superuser.id)
    source = create_random_source(db, workflow_id=workflow.id)
    job = create_random_job(db, source_id=source.id)

    # Normal user should not be able to access it
    response = client.get(
        f"{settings.API_V1_STR}/jobs/{job.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 400
    content = response.json()
    assert content["detail"] == "Not enough permissions"
