import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Job,
    JobCreate,
    JobPublic,
    JobsPublic,
    JobStatus,
    Message,
    Source,
    Workflow,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _verify_workflow_access(
    session: SessionDep, workflow_id: uuid.UUID, user_id: uuid.UUID
) -> Workflow:
    """Verify user has access to the workflow."""
    workflow = session.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if workflow.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return workflow


def _verify_source_access(
    session: SessionDep, source_id: uuid.UUID, user_id: uuid.UUID
) -> Source:
    """Verify user has access to the source via its workflow."""
    source = session.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    workflow = session.get(Workflow, source.workflow_id)
    if not workflow or workflow.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return source


def _verify_job_access(
    session: SessionDep, job_id: uuid.UUID, user_id: uuid.UUID
) -> Job:
    """Verify user has access to the job via its source's workflow."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    source = session.get(Source, job.source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    workflow = session.get(Workflow, source.workflow_id)
    if not workflow or workflow.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return job


@router.get("/source/{source_id}", response_model=JobsPublic)
def read_jobs_by_source(
    session: SessionDep,
    current_user: CurrentUser,
    source_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    status: JobStatus | None = None,
) -> Any:
    """
    Retrieve jobs for a source.
    """
    _verify_source_access(session, source_id, current_user.id)

    # Build base query
    base_filter = Job.source_id == source_id
    if status:
        base_filter = base_filter & (Job.status == status)

    count_statement = select(func.count()).select_from(Job).where(base_filter)
    count = session.exec(count_statement).one()

    statement = (
        select(Job)
        .where(base_filter)
        .order_by(Job.scheduled_at.desc())
        .offset(skip)
        .limit(limit)
    )
    jobs = session.exec(statement).all()

    return JobsPublic(data=jobs, count=count)


@router.get("/workflow/{workflow_id}", response_model=JobsPublic)
def read_jobs_by_workflow(
    session: SessionDep,
    current_user: CurrentUser,
    workflow_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    status: JobStatus | None = None,
) -> Any:
    """
    Retrieve jobs for all sources in a workflow.
    """
    _verify_workflow_access(session, workflow_id, current_user.id)

    # Get all source IDs for this workflow
    source_statement = select(Source.id).where(Source.workflow_id == workflow_id)
    source_ids = list(session.exec(source_statement).all())

    if not source_ids:
        return JobsPublic(data=[], count=0)

    # Build base query
    base_filter = Job.source_id.in_(source_ids)
    if status:
        base_filter = base_filter & (Job.status == status)

    count_statement = select(func.count()).select_from(Job).where(base_filter)
    count = session.exec(count_statement).one()

    statement = (
        select(Job)
        .where(base_filter)
        .order_by(Job.scheduled_at.desc())
        .offset(skip)
        .limit(limit)
    )
    jobs = session.exec(statement).all()

    return JobsPublic(data=jobs, count=count)


@router.get("/{id}", response_model=JobPublic)
def read_job(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    """
    Get job by ID.
    """
    job = _verify_job_access(session, id, current_user.id)
    return job


@router.post("/source/{source_id}/trigger", response_model=JobPublic)
def trigger_job(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    source_id: uuid.UUID,
) -> Any:
    """
    Manually trigger a job for a source.
    Creates a new job in 'queued' status.
    """
    source = _verify_source_access(session, source_id, current_user.id)

    if not source.is_active:
        raise HTTPException(status_code=400, detail="Source is not active")

    # Create a new job
    job = Job(
        source_id=source_id,
        status=JobStatus.queued,
        scheduled_at=datetime.utcnow(),
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    # TODO: Publish to NATS JetStream to trigger the worker
    # This will be implemented in the async pipeline phase

    return job


@router.delete("/{id}")
def delete_job(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete a job (only if not running).
    """
    job = _verify_job_access(session, id, current_user.id)

    if job.status == JobStatus.running:
        raise HTTPException(status_code=400, detail="Cannot delete a running job")

    session.delete(job)
    session.commit()
    return Message(message="Job deleted successfully")


@router.get("/", response_model=JobsPublic)
def read_all_jobs(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    status: JobStatus | None = None,
) -> Any:
    """
    Retrieve all jobs across user's workflows.
    """
    # Get all workflow IDs for the current user
    user_workflow_statement = select(Workflow.id).where(
        Workflow.user_id == current_user.id
    )
    user_workflow_ids = list(session.exec(user_workflow_statement).all())

    if not user_workflow_ids:
        return JobsPublic(data=[], count=0)

    # Get all source IDs for these workflows
    source_statement = select(Source.id).where(
        Source.workflow_id.in_(user_workflow_ids)
    )
    source_ids = list(session.exec(source_statement).all())

    if not source_ids:
        return JobsPublic(data=[], count=0)

    # Build base query
    base_filter = Job.source_id.in_(source_ids)
    if status:
        base_filter = base_filter & (Job.status == status)

    count_statement = select(func.count()).select_from(Job).where(base_filter)
    count = session.exec(count_statement).one()

    statement = (
        select(Job)
        .where(base_filter)
        .order_by(Job.scheduled_at.desc())
        .offset(skip)
        .limit(limit)
    )
    jobs = session.exec(statement).all()

    return JobsPublic(data=jobs, count=count)
