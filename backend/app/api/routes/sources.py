import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Message,
    Parser,
    ParserCreate,
    ParserPublic,
    ParsersPublic,
    ParserUpdate,
    Source,
    SourceCreate,
    SourcePublic,
    SourcesPublic,
    SourceUpdate,
    Workflow,
)

router = APIRouter(prefix="/sources", tags=["sources"])


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


# --- Source endpoints ---


@router.get("/", response_model=SourcesPublic)
def read_all_sources(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve all sources for the current user across all workflows.
    """
    # Get all workflow IDs belonging to the user
    workflow_ids = session.exec(
        select(Workflow.id).where(Workflow.user_id == current_user.id)
    ).all()

    if not workflow_ids:
        return SourcesPublic(data=[], count=0)

    count_statement = (
        select(func.count())
        .select_from(Source)
        .where(Source.workflow_id.in_(workflow_ids))  # type: ignore[union-attr]
    )
    count = session.exec(count_statement).one()
    statement = (
        select(Source)
        .where(Source.workflow_id.in_(workflow_ids))  # type: ignore[union-attr]
        .offset(skip)
        .limit(limit)
    )
    sources = session.exec(statement).all()

    return SourcesPublic(data=sources, count=count)


@router.get("/workflow/{workflow_id}", response_model=SourcesPublic)
def read_sources(
    session: SessionDep,
    current_user: CurrentUser,
    workflow_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve sources for a workflow.
    """
    _verify_workflow_access(session, workflow_id, current_user.id)

    count_statement = (
        select(func.count())
        .select_from(Source)
        .where(Source.workflow_id == workflow_id)
    )
    count = session.exec(count_statement).one()
    statement = (
        select(Source)
        .where(Source.workflow_id == workflow_id)
        .offset(skip)
        .limit(limit)
    )
    sources = session.exec(statement).all()

    return SourcesPublic(data=sources, count=count)


@router.get("/{id}", response_model=SourcePublic)
def read_source(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    """
    Get source by ID.
    """
    source = _verify_source_access(session, id, current_user.id)
    return source


@router.post("/workflow/{workflow_id}", response_model=SourcePublic)
def create_source(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workflow_id: uuid.UUID,
    source_in: SourceCreate,
) -> Any:
    """
    Create new source for a workflow.
    """
    _verify_workflow_access(session, workflow_id, current_user.id)

    source = Source.model_validate(source_in, update={"workflow_id": workflow_id})
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


@router.put("/{id}", response_model=SourcePublic)
def update_source(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    source_in: SourceUpdate,
) -> Any:
    """
    Update a source.
    """
    source = _verify_source_access(session, id, current_user.id)
    update_dict = source_in.model_dump(exclude_unset=True)
    source.sqlmodel_update(update_dict)
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


@router.delete("/{id}")
def delete_source(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete a source.
    """
    source = _verify_source_access(session, id, current_user.id)
    session.delete(source)
    session.commit()
    return Message(message="Source deleted successfully")


# --- Parser endpoints (nested under source) ---


@router.get("/{source_id}/parsers", response_model=ParsersPublic)
def read_parsers(
    session: SessionDep,
    current_user: CurrentUser,
    source_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve parsers for a source.
    """
    _verify_source_access(session, source_id, current_user.id)

    count_statement = (
        select(func.count())
        .select_from(Parser)
        .where(Parser.source_id == source_id)
    )
    count = session.exec(count_statement).one()
    statement = (
        select(Parser)
        .where(Parser.source_id == source_id)
        .offset(skip)
        .limit(limit)
    )
    parsers = session.exec(statement).all()

    return ParsersPublic(data=parsers, count=count)


@router.get("/{source_id}/parsers/{parser_id}", response_model=ParserPublic)
def read_parser(
    session: SessionDep,
    current_user: CurrentUser,
    source_id: uuid.UUID,
    parser_id: uuid.UUID,
) -> Any:
    """
    Get parser by ID.
    """
    _verify_source_access(session, source_id, current_user.id)
    parser = session.get(Parser, parser_id)
    if not parser or parser.source_id != source_id:
        raise HTTPException(status_code=404, detail="Parser not found")
    return parser


@router.post("/{source_id}/parsers", response_model=ParserPublic)
def create_parser(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    source_id: uuid.UUID,
    parser_in: ParserCreate,
) -> Any:
    """
    Create new parser for a source.
    """
    _verify_source_access(session, source_id, current_user.id)

    parser = Parser.model_validate(parser_in, update={"source_id": source_id})
    session.add(parser)
    session.commit()
    session.refresh(parser)
    return parser


@router.put("/{source_id}/parsers/{parser_id}", response_model=ParserPublic)
def update_parser(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    source_id: uuid.UUID,
    parser_id: uuid.UUID,
    parser_in: ParserUpdate,
) -> Any:
    """
    Update a parser.
    """
    _verify_source_access(session, source_id, current_user.id)
    parser = session.get(Parser, parser_id)
    if not parser or parser.source_id != source_id:
        raise HTTPException(status_code=404, detail="Parser not found")
    update_dict = parser_in.model_dump(exclude_unset=True)
    parser.sqlmodel_update(update_dict)
    session.add(parser)
    session.commit()
    session.refresh(parser)
    return parser


@router.delete("/{source_id}/parsers/{parser_id}")
def delete_parser(
    session: SessionDep,
    current_user: CurrentUser,
    source_id: uuid.UUID,
    parser_id: uuid.UUID,
) -> Message:
    """
    Delete a parser.
    """
    _verify_source_access(session, source_id, current_user.id)
    parser = session.get(Parser, parser_id)
    if not parser or parser.source_id != source_id:
        raise HTTPException(status_code=404, detail="Parser not found")
    session.delete(parser)
    session.commit()
    return Message(message="Parser deleted successfully")
