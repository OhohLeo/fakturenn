import uuid
from datetime import date, datetime
from typing import Any

from sqlmodel import Session, select

from app.core.security import get_password_hash, verify_password
from app.models import (
    Exporter,
    ExporterCreate,
    ExporterUpdate,
    Job,
    JobCreate,
    JobUpdate,
    Mapper,
    MapperCreate,
    MapperUpdate,
    Parser,
    ParserCreate,
    ParserUpdate,
    Record,
    RecordCreate,
    RecordUpdate,
    Source,
    SourceCreate,
    SourceUpdate,
    User,
    UserCreate,
    UserUpdate,
    Workflow,
    WorkflowCreate,
    WorkflowUpdate,
)


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


# ============================================================================
# WORKFLOW CRUD
# ============================================================================


def create_workflow(
    *, session: Session, workflow_in: WorkflowCreate, user_id: uuid.UUID
) -> Workflow:
    """Create a new workflow for a user"""
    db_workflow = Workflow.model_validate(workflow_in, update={"user_id": user_id})
    session.add(db_workflow)
    session.commit()
    session.refresh(db_workflow)
    return db_workflow


def get_workflow(*, session: Session, workflow_id: uuid.UUID) -> Workflow | None:
    """Get a workflow by ID"""
    return session.get(Workflow, workflow_id)


def get_workflows_by_user(
    *, session: Session, user_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> list[Workflow]:
    """Get all workflows for a user"""
    statement = (
        select(Workflow)
        .where(Workflow.user_id == user_id)
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def get_workflows_count_by_user(*, session: Session, user_id: uuid.UUID) -> int:
    """Get count of workflows for a user"""
    statement = select(Workflow).where(Workflow.user_id == user_id)
    return len(list(session.exec(statement).all()))


def update_workflow(
    *, session: Session, db_workflow: Workflow, workflow_in: WorkflowUpdate
) -> Workflow:
    """Update a workflow"""
    workflow_data = workflow_in.model_dump(exclude_unset=True)
    db_workflow.sqlmodel_update(workflow_data)
    session.add(db_workflow)
    session.commit()
    session.refresh(db_workflow)
    return db_workflow


def delete_workflow(*, session: Session, db_workflow: Workflow) -> None:
    """Delete a workflow"""
    session.delete(db_workflow)
    session.commit()


# ============================================================================
# SOURCE CRUD
# ============================================================================


def create_source(*, session: Session, source_in: SourceCreate) -> Source:
    """Create a new source"""
    db_source = Source.model_validate(source_in)
    session.add(db_source)
    session.commit()
    session.refresh(db_source)
    return db_source


def get_source(*, session: Session, source_id: uuid.UUID) -> Source | None:
    """Get a source by ID"""
    return session.get(Source, source_id)


def get_sources_by_workflow(
    *, session: Session, workflow_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> list[Source]:
    """Get all sources for a workflow"""
    statement = (
        select(Source)
        .where(Source.workflow_id == workflow_id)
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def get_sources_count_by_workflow(*, session: Session, workflow_id: uuid.UUID) -> int:
    """Get count of sources for a workflow"""
    statement = select(Source).where(Source.workflow_id == workflow_id)
    return len(list(session.exec(statement).all()))


def get_active_sources_with_crontab(*, session: Session) -> list[Source]:
    """Get all active sources that have a crontab configured"""
    statement = select(Source).where(
        Source.is_active == True,  # noqa: E712
        Source.crontab.is_not(None),
    )
    return list(session.exec(statement).all())


def update_source(
    *, session: Session, db_source: Source, source_in: SourceUpdate
) -> Source:
    """Update a source"""
    source_data = source_in.model_dump(exclude_unset=True)
    db_source.sqlmodel_update(source_data)
    session.add(db_source)
    session.commit()
    session.refresh(db_source)
    return db_source


def update_source_sync_status(
    *,
    session: Session,
    db_source: Source,
    sync_cursor: str | None = None,
    error_context: dict | None = None,
) -> Source:
    """Update source sync status"""
    db_source.last_sync_at = datetime.now()
    if sync_cursor is not None:
        db_source.sync_cursor = sync_cursor
    if error_context is not None:
        db_source.error_context = error_context
    session.add(db_source)
    session.commit()
    session.refresh(db_source)
    return db_source


def delete_source(*, session: Session, db_source: Source) -> None:
    """Delete a source"""
    session.delete(db_source)
    session.commit()


# ============================================================================
# PARSER CRUD
# ============================================================================


def create_parser(*, session: Session, parser_in: ParserCreate) -> Parser:
    """Create a new parser"""
    db_parser = Parser.model_validate(parser_in)
    session.add(db_parser)
    session.commit()
    session.refresh(db_parser)
    return db_parser


def get_parser(*, session: Session, parser_id: uuid.UUID) -> Parser | None:
    """Get a parser by ID"""
    return session.get(Parser, parser_id)


def get_parsers_by_source(
    *, session: Session, source_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> list[Parser]:
    """Get all parsers for a source"""
    statement = (
        select(Parser)
        .where(Parser.source_id == source_id)
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def get_parsers_count_by_source(*, session: Session, source_id: uuid.UUID) -> int:
    """Get count of parsers for a source"""
    statement = select(Parser).where(Parser.source_id == source_id)
    return len(list(session.exec(statement).all()))


def get_active_parsers_by_source(
    *, session: Session, source_id: uuid.UUID
) -> list[Parser]:
    """Get all active parsers for a source"""
    statement = select(Parser).where(
        Parser.source_id == source_id,
        Parser.is_active == True,  # noqa: E712
    )
    return list(session.exec(statement).all())


def update_parser(
    *, session: Session, db_parser: Parser, parser_in: ParserUpdate
) -> Parser:
    """Update a parser"""
    parser_data = parser_in.model_dump(exclude_unset=True)
    db_parser.sqlmodel_update(parser_data)
    session.add(db_parser)
    session.commit()
    session.refresh(db_parser)
    return db_parser


def delete_parser(*, session: Session, db_parser: Parser) -> None:
    """Delete a parser"""
    session.delete(db_parser)
    session.commit()


# ============================================================================
# RECORD CRUD
# ============================================================================


def create_record(
    *,
    session: Session,
    record_in: RecordCreate,
    file_content: bytes | None = None,
) -> Record:
    """Create a new record with computed unique key"""
    unique_key = Record.compute_unique_key(
        source_id=record_in.source_id,
        record_date=record_in.date,
        file_content=file_content,
        data=record_in.data,
    )
    db_record = Record.model_validate(record_in, update={"unique_key": unique_key})
    session.add(db_record)
    session.commit()
    session.refresh(db_record)
    return db_record


def get_record(*, session: Session, record_id: uuid.UUID) -> Record | None:
    """Get a record by ID"""
    return session.get(Record, record_id)


def get_record_by_unique_key(
    *, session: Session, unique_key: str
) -> Record | None:
    """Get a record by unique key (for duplicate detection)"""
    statement = select(Record).where(Record.unique_key == unique_key)
    return session.exec(statement).first()


def get_records_by_workflow(
    *,
    session: Session,
    workflow_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
) -> list[Record]:
    """Get all records for a workflow with optional status filter"""
    statement = select(Record).where(Record.workflow_id == workflow_id)
    if status:
        statement = statement.where(Record.status == status)
    statement = statement.offset(skip).limit(limit)
    return list(session.exec(statement).all())


def get_records_count_by_workflow(
    *, session: Session, workflow_id: uuid.UUID, status: str | None = None
) -> int:
    """Get count of records for a workflow"""
    statement = select(Record).where(Record.workflow_id == workflow_id)
    if status:
        statement = statement.where(Record.status == status)
    return len(list(session.exec(statement).all()))


def get_records_by_source(
    *,
    session: Session,
    source_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[Record]:
    """Get all records for a source with optional date filters"""
    statement = select(Record).where(Record.source_id == source_id)
    if from_date:
        statement = statement.where(Record.date >= from_date)
    if to_date:
        statement = statement.where(Record.date <= to_date)
    statement = statement.offset(skip).limit(limit)
    return list(session.exec(statement).all())


def update_record(
    *, session: Session, db_record: Record, record_in: RecordUpdate
) -> Record:
    """Update a record"""
    record_data = record_in.model_dump(exclude_unset=True)
    db_record.sqlmodel_update(record_data)
    session.add(db_record)
    session.commit()
    session.refresh(db_record)
    return db_record


def delete_record(*, session: Session, db_record: Record) -> None:
    """Delete a record"""
    session.delete(db_record)
    session.commit()


# ============================================================================
# EXPORTER CRUD
# ============================================================================


def create_exporter(*, session: Session, exporter_in: ExporterCreate) -> Exporter:
    """Create a new exporter"""
    db_exporter = Exporter.model_validate(exporter_in)
    session.add(db_exporter)
    session.commit()
    session.refresh(db_exporter)
    return db_exporter


def get_exporter(*, session: Session, exporter_id: uuid.UUID) -> Exporter | None:
    """Get an exporter by ID"""
    return session.get(Exporter, exporter_id)


def get_exporters_by_workflow(
    *, session: Session, workflow_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> list[Exporter]:
    """Get all exporters for a workflow"""
    statement = (
        select(Exporter)
        .where(Exporter.workflow_id == workflow_id)
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def get_exporters_count_by_workflow(*, session: Session, workflow_id: uuid.UUID) -> int:
    """Get count of exporters for a workflow"""
    statement = select(Exporter).where(Exporter.workflow_id == workflow_id)
    return len(list(session.exec(statement).all()))


def get_active_exporters_by_workflow(
    *, session: Session, workflow_id: uuid.UUID
) -> list[Exporter]:
    """Get all active exporters for a workflow"""
    statement = select(Exporter).where(
        Exporter.workflow_id == workflow_id,
        Exporter.is_active == True,  # noqa: E712
    )
    return list(session.exec(statement).all())


def update_exporter(
    *, session: Session, db_exporter: Exporter, exporter_in: ExporterUpdate
) -> Exporter:
    """Update an exporter"""
    exporter_data = exporter_in.model_dump(exclude_unset=True)
    db_exporter.sqlmodel_update(exporter_data)
    session.add(db_exporter)
    session.commit()
    session.refresh(db_exporter)
    return db_exporter


def delete_exporter(*, session: Session, db_exporter: Exporter) -> None:
    """Delete an exporter"""
    session.delete(db_exporter)
    session.commit()


# ============================================================================
# MAPPER CRUD
# ============================================================================


def create_mapper(*, session: Session, mapper_in: MapperCreate) -> Mapper:
    """Create a new mapper"""
    db_mapper = Mapper.model_validate(mapper_in)
    session.add(db_mapper)
    session.commit()
    session.refresh(db_mapper)
    return db_mapper


def get_mapper(*, session: Session, mapper_id: uuid.UUID) -> Mapper | None:
    """Get a mapper by ID"""
    return session.get(Mapper, mapper_id)


def get_mappers_by_exporter(
    *, session: Session, exporter_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> list[Mapper]:
    """Get all mappers for an exporter"""
    statement = (
        select(Mapper)
        .where(Mapper.exporter_id == exporter_id)
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def get_mappers_count_by_exporter(*, session: Session, exporter_id: uuid.UUID) -> int:
    """Get count of mappers for an exporter"""
    statement = select(Mapper).where(Mapper.exporter_id == exporter_id)
    return len(list(session.exec(statement).all()))


def get_active_mappers_by_exporter(
    *, session: Session, exporter_id: uuid.UUID
) -> list[Mapper]:
    """Get all active mappers for an exporter"""
    statement = select(Mapper).where(
        Mapper.exporter_id == exporter_id,
        Mapper.is_active == True,  # noqa: E712
    )
    return list(session.exec(statement).all())


def update_mapper(
    *, session: Session, db_mapper: Mapper, mapper_in: MapperUpdate
) -> Mapper:
    """Update a mapper"""
    mapper_data = mapper_in.model_dump(exclude_unset=True)
    db_mapper.sqlmodel_update(mapper_data)
    session.add(db_mapper)
    session.commit()
    session.refresh(db_mapper)
    return db_mapper


def delete_mapper(*, session: Session, db_mapper: Mapper) -> None:
    """Delete a mapper"""
    session.delete(db_mapper)
    session.commit()


# ============================================================================
# JOB CRUD
# ============================================================================


def create_job(*, session: Session, job_in: JobCreate) -> Job:
    """Create a new job"""
    db_job = Job.model_validate(job_in)
    session.add(db_job)
    session.commit()
    session.refresh(db_job)
    return db_job


def get_job(*, session: Session, job_id: uuid.UUID) -> Job | None:
    """Get a job by ID"""
    return session.get(Job, job_id)


def get_jobs_by_source(
    *,
    session: Session,
    source_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
) -> list[Job]:
    """Get all jobs for a source with optional status filter"""
    statement = select(Job).where(Job.source_id == source_id)
    if status:
        statement = statement.where(Job.status == status)
    statement = statement.offset(skip).limit(limit)
    return list(session.exec(statement).all())


def get_jobs_count_by_source(
    *, session: Session, source_id: uuid.UUID, status: str | None = None
) -> int:
    """Get count of jobs for a source"""
    statement = select(Job).where(Job.source_id == source_id)
    if status:
        statement = statement.where(Job.status == status)
    return len(list(session.exec(statement).all()))


def get_pending_jobs(*, session: Session) -> list[Job]:
    """Get all jobs with queued status"""
    statement = select(Job).where(Job.status == "queued")
    return list(session.exec(statement).all())


def update_job(*, session: Session, db_job: Job, job_in: JobUpdate) -> Job:
    """Update a job"""
    job_data = job_in.model_dump(exclude_unset=True)
    db_job.sqlmodel_update(job_data)
    session.add(db_job)
    session.commit()
    session.refresh(db_job)
    return db_job


def start_job(*, session: Session, db_job: Job) -> Job:
    """Mark a job as running"""
    db_job.status = "running"
    db_job.started_at = datetime.now()
    session.add(db_job)
    session.commit()
    session.refresh(db_job)
    return db_job


def complete_job(
    *,
    session: Session,
    db_job: Job,
    success: bool,
    error_context: dict | None = None,
) -> Job:
    """Mark a job as completed"""
    db_job.status = "success" if success else "failed"
    if error_context:
        db_job.error_context = error_context
    session.add(db_job)
    session.commit()
    session.refresh(db_job)
    return db_job


def delete_job(*, session: Session, db_job: Job) -> None:
    """Delete a job"""
    session.delete(db_job)
    session.commit()
