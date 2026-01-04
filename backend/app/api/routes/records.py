import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Message,
    Record,
    RecordPublic,
    RecordsPublic,
    RecordStatus,
    RecordUpdate,
    Source,
    Workflow,
)

router = APIRouter(prefix="/records", tags=["records"])


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


def _verify_record_access(
    session: SessionDep, record_id: uuid.UUID, user_id: uuid.UUID
) -> Record:
    """Verify user has access to the record via its workflow."""
    record = session.get(Record, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    workflow = session.get(Workflow, record.workflow_id)
    if not workflow or workflow.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return record


@router.get("/workflow/{workflow_id}", response_model=RecordsPublic)
def read_records_by_workflow(
    session: SessionDep,
    current_user: CurrentUser,
    workflow_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    status: RecordStatus | None = None,
    source_id: uuid.UUID | None = None,
) -> Any:
    """
    Retrieve records for a workflow with optional filtering.
    """
    _verify_workflow_access(session, workflow_id, current_user.id)

    # Build base query
    base_filter = Record.workflow_id == workflow_id
    if status:
        base_filter = base_filter & (Record.status == status)
    if source_id:
        base_filter = base_filter & (Record.source_id == source_id)

    count_statement = (
        select(func.count()).select_from(Record).where(base_filter)
    )
    count = session.exec(count_statement).one()

    statement = (
        select(Record)
        .where(base_filter)
        .order_by(Record.date.desc())
        .offset(skip)
        .limit(limit)
    )
    records = session.exec(statement).all()

    return RecordsPublic(data=records, count=count)


@router.get("/source/{source_id}", response_model=RecordsPublic)
def read_records_by_source(
    session: SessionDep,
    current_user: CurrentUser,
    source_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    status: RecordStatus | None = None,
) -> Any:
    """
    Retrieve records for a specific source.
    """
    source = session.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    _verify_workflow_access(session, source.workflow_id, current_user.id)

    # Build base query
    base_filter = Record.source_id == source_id
    if status:
        base_filter = base_filter & (Record.status == status)

    count_statement = (
        select(func.count()).select_from(Record).where(base_filter)
    )
    count = session.exec(count_statement).one()

    statement = (
        select(Record)
        .where(base_filter)
        .order_by(Record.date.desc())
        .offset(skip)
        .limit(limit)
    )
    records = session.exec(statement).all()

    return RecordsPublic(data=records, count=count)


@router.get("/{id}", response_model=RecordPublic)
def read_record(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    """
    Get record by ID.
    """
    record = _verify_record_access(session, id, current_user.id)
    return record


@router.put("/{id}", response_model=RecordPublic)
def update_record(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    record_in: RecordUpdate,
) -> Any:
    """
    Update a record (mainly for status changes or error context).
    """
    record = _verify_record_access(session, id, current_user.id)
    update_dict = record_in.model_dump(exclude_unset=True)
    record.sqlmodel_update(update_dict)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@router.delete("/{id}")
def delete_record(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete a record.
    """
    record = _verify_record_access(session, id, current_user.id)
    session.delete(record)
    session.commit()
    return Message(message="Record deleted successfully")


@router.get("/", response_model=RecordsPublic)
def read_all_records(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    status: RecordStatus | None = None,
    workflow_ids: list[uuid.UUID] | None = Query(default=None),
) -> Any:
    """
    Retrieve all records across user's workflows with optional filtering.
    """
    # Get all workflow IDs for the current user
    user_workflow_statement = select(Workflow.id).where(
        Workflow.user_id == current_user.id
    )
    user_workflow_ids = list(session.exec(user_workflow_statement).all())

    if not user_workflow_ids:
        return RecordsPublic(data=[], count=0)

    # Filter by specified workflow IDs if provided
    if workflow_ids:
        # Ensure user owns the requested workflows
        allowed_ids = set(user_workflow_ids) & set(workflow_ids)
        if not allowed_ids:
            return RecordsPublic(data=[], count=0)
        filter_workflow_ids = list(allowed_ids)
    else:
        filter_workflow_ids = user_workflow_ids

    # Build base query
    base_filter = Record.workflow_id.in_(filter_workflow_ids)
    if status:
        base_filter = base_filter & (Record.status == status)

    count_statement = (
        select(func.count()).select_from(Record).where(base_filter)
    )
    count = session.exec(count_statement).one()

    statement = (
        select(Record)
        .where(base_filter)
        .order_by(Record.date.desc())
        .offset(skip)
        .limit(limit)
    )
    records = session.exec(statement).all()

    return RecordsPublic(data=records, count=count)
