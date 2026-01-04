import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Exporter,
    ExporterCreate,
    ExporterPublic,
    ExportersPublic,
    ExporterUpdate,
    Mapper,
    MapperCreate,
    MapperPublic,
    MappersPublic,
    MapperUpdate,
    Message,
    Workflow,
)

router = APIRouter(prefix="/exporters", tags=["exporters"])


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


def _verify_exporter_access(
    session: SessionDep, exporter_id: uuid.UUID, user_id: uuid.UUID
) -> Exporter:
    """Verify user has access to the exporter via its workflow."""
    exporter = session.get(Exporter, exporter_id)
    if not exporter:
        raise HTTPException(status_code=404, detail="Exporter not found")
    workflow = session.get(Workflow, exporter.workflow_id)
    if not workflow or workflow.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return exporter


# --- Exporter endpoints ---


@router.get("/", response_model=ExportersPublic)
def read_all_exporters(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve all exporters for the current user across all workflows.
    """
    # Get all workflow IDs belonging to the user
    workflow_ids = session.exec(
        select(Workflow.id).where(Workflow.user_id == current_user.id)
    ).all()

    if not workflow_ids:
        return ExportersPublic(data=[], count=0)

    count_statement = (
        select(func.count())
        .select_from(Exporter)
        .where(Exporter.workflow_id.in_(workflow_ids))  # type: ignore[union-attr]
    )
    count = session.exec(count_statement).one()
    statement = (
        select(Exporter)
        .where(Exporter.workflow_id.in_(workflow_ids))  # type: ignore[union-attr]
        .offset(skip)
        .limit(limit)
    )
    exporters = session.exec(statement).all()

    return ExportersPublic(data=exporters, count=count)


@router.get("/workflow/{workflow_id}", response_model=ExportersPublic)
def read_exporters(
    session: SessionDep,
    current_user: CurrentUser,
    workflow_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve exporters for a workflow.
    """
    _verify_workflow_access(session, workflow_id, current_user.id)

    count_statement = (
        select(func.count())
        .select_from(Exporter)
        .where(Exporter.workflow_id == workflow_id)
    )
    count = session.exec(count_statement).one()
    statement = (
        select(Exporter)
        .where(Exporter.workflow_id == workflow_id)
        .offset(skip)
        .limit(limit)
    )
    exporters = session.exec(statement).all()

    return ExportersPublic(data=exporters, count=count)


@router.get("/{id}", response_model=ExporterPublic)
def read_exporter(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    """
    Get exporter by ID.
    """
    exporter = _verify_exporter_access(session, id, current_user.id)
    return exporter


@router.post("/workflow/{workflow_id}", response_model=ExporterPublic)
def create_exporter(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workflow_id: uuid.UUID,
    exporter_in: ExporterCreate,
) -> Any:
    """
    Create new exporter for a workflow.
    """
    _verify_workflow_access(session, workflow_id, current_user.id)

    exporter = Exporter.model_validate(
        exporter_in, update={"workflow_id": workflow_id}
    )
    session.add(exporter)
    session.commit()
    session.refresh(exporter)
    return exporter


@router.put("/{id}", response_model=ExporterPublic)
def update_exporter(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    exporter_in: ExporterUpdate,
) -> Any:
    """
    Update an exporter.
    """
    exporter = _verify_exporter_access(session, id, current_user.id)
    update_dict = exporter_in.model_dump(exclude_unset=True)
    exporter.sqlmodel_update(update_dict)
    session.add(exporter)
    session.commit()
    session.refresh(exporter)
    return exporter


@router.delete("/{id}")
def delete_exporter(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete an exporter.
    """
    exporter = _verify_exporter_access(session, id, current_user.id)
    session.delete(exporter)
    session.commit()
    return Message(message="Exporter deleted successfully")


# --- Mapper endpoints (nested under exporter) ---


@router.get("/{exporter_id}/mappers", response_model=MappersPublic)
def read_mappers(
    session: SessionDep,
    current_user: CurrentUser,
    exporter_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve mappers for an exporter.
    """
    _verify_exporter_access(session, exporter_id, current_user.id)

    count_statement = (
        select(func.count())
        .select_from(Mapper)
        .where(Mapper.exporter_id == exporter_id)
    )
    count = session.exec(count_statement).one()
    statement = (
        select(Mapper)
        .where(Mapper.exporter_id == exporter_id)
        .offset(skip)
        .limit(limit)
    )
    mappers = session.exec(statement).all()

    return MappersPublic(data=mappers, count=count)


@router.get("/{exporter_id}/mappers/{mapper_id}", response_model=MapperPublic)
def read_mapper(
    session: SessionDep,
    current_user: CurrentUser,
    exporter_id: uuid.UUID,
    mapper_id: uuid.UUID,
) -> Any:
    """
    Get mapper by ID.
    """
    _verify_exporter_access(session, exporter_id, current_user.id)
    mapper = session.get(Mapper, mapper_id)
    if not mapper or mapper.exporter_id != exporter_id:
        raise HTTPException(status_code=404, detail="Mapper not found")
    return mapper


@router.post("/{exporter_id}/mappers", response_model=MapperPublic)
def create_mapper(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    exporter_id: uuid.UUID,
    mapper_in: MapperCreate,
) -> Any:
    """
    Create new mapper for an exporter.
    """
    _verify_exporter_access(session, exporter_id, current_user.id)

    mapper = Mapper.model_validate(mapper_in, update={"exporter_id": exporter_id})
    session.add(mapper)
    session.commit()
    session.refresh(mapper)
    return mapper


@router.put("/{exporter_id}/mappers/{mapper_id}", response_model=MapperPublic)
def update_mapper(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    exporter_id: uuid.UUID,
    mapper_id: uuid.UUID,
    mapper_in: MapperUpdate,
) -> Any:
    """
    Update a mapper.
    """
    _verify_exporter_access(session, exporter_id, current_user.id)
    mapper = session.get(Mapper, mapper_id)
    if not mapper or mapper.exporter_id != exporter_id:
        raise HTTPException(status_code=404, detail="Mapper not found")
    update_dict = mapper_in.model_dump(exclude_unset=True)
    mapper.sqlmodel_update(update_dict)
    session.add(mapper)
    session.commit()
    session.refresh(mapper)
    return mapper


@router.delete("/{exporter_id}/mappers/{mapper_id}")
def delete_mapper(
    session: SessionDep,
    current_user: CurrentUser,
    exporter_id: uuid.UUID,
    mapper_id: uuid.UUID,
) -> Message:
    """
    Delete a mapper.
    """
    _verify_exporter_access(session, exporter_id, current_user.id)
    mapper = session.get(Mapper, mapper_id)
    if not mapper or mapper.exporter_id != exporter_id:
        raise HTTPException(status_code=404, detail="Mapper not found")
    session.delete(mapper)
    session.commit()
    return Message(message="Mapper deleted successfully")
