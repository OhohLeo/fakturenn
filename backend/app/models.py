import hashlib
import json
import uuid
from datetime import date, datetime
from enum import Enum

from pydantic import EmailStr
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel


# ============================================================================
# ENUMS
# ============================================================================


class SourceType(str, Enum):
    """Types of invoice sources"""

    gmail = "gmail"
    xls = "xls"
    free = "free"  # Phase 2
    free_mobile = "free_mobile"  # Phase 2


class ExporterType(str, Enum):
    """Types of export destinations"""

    paheko = "paheko"
    gdrive = "gdrive"


class ParserEngineType(str, Enum):
    """Types of parser engines"""

    mail2record = "mail2record"
    xls2record = "xls2record"
    free2record = "free2record"  # Phase 2
    ai_model = "ai_model"  # Future


class MapperType(str, Enum):
    """Types of mappers"""

    record2paheko = "record2paheko"
    record2gdrive = "record2gdrive"


class RecordStatus(str, Enum):
    """Status of a record"""

    pending = "pending"
    processing = "processing"
    success = "success"
    failed = "failed"
    exported = "exported"


class JobStatus(str, Enum):
    """Status of a job"""

    queued = "queued"
    running = "running"
    success = "success"
    failed = "failed"


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    workflows: list["Workflow"] = Relationship(
        back_populates="user", cascade_delete=True
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# ============================================================================
# WORKFLOW MODELS
# ============================================================================


class WorkflowBase(SQLModel):
    """Base workflow properties"""

    name: str = Field(min_length=1, max_length=255)


class WorkflowCreate(WorkflowBase):
    """Properties for workflow creation"""

    pass


class WorkflowUpdate(SQLModel):
    """Properties for workflow update"""

    name: str | None = Field(default=None, min_length=1, max_length=255)


class Workflow(WorkflowBase, table=True):
    """Workflow database model - contains sources and exporters"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")

    # Relationships
    user: User | None = Relationship(back_populates="workflows")
    sources: list["Source"] = Relationship(back_populates="workflow", cascade_delete=True)
    exporters: list["Exporter"] = Relationship(
        back_populates="workflow", cascade_delete=True
    )
    records: list["Record"] = Relationship(
        back_populates="workflow", cascade_delete=True
    )


class WorkflowPublic(WorkflowBase):
    """Workflow properties returned via API"""

    id: uuid.UUID
    user_id: uuid.UUID


class WorkflowsPublic(SQLModel):
    """List of workflows with count"""

    data: list[WorkflowPublic]
    count: int


# ============================================================================
# SOURCE MODELS
# ============================================================================


class SourceBase(SQLModel):
    """Base source properties"""

    name: str = Field(min_length=1, max_length=255)
    type: SourceType
    crontab: str | None = Field(default=None, max_length=100)
    is_active: bool = True


class SourceCreate(SourceBase):
    """Properties for source creation"""

    workflow_id: uuid.UUID
    config: dict | None = Field(default=None, sa_column=Column(JSONB))


class SourceUpdate(SQLModel):
    """Properties for source update"""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    type: SourceType | None = None
    config: dict | None = Field(default=None, sa_column=Column(JSONB))
    crontab: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None


class Source(SourceBase, table=True):
    """Source database model - fetches invoices from external systems"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workflow_id: uuid.UUID = Field(
        foreign_key="workflow.id", nullable=False, ondelete="CASCADE"
    )
    config: dict | None = Field(default=None, sa_column=Column(JSONB))
    sync_cursor: str | None = Field(default=None, max_length=500)
    last_sync_at: datetime | None = None
    error_context: dict | None = Field(default=None, sa_column=Column(JSONB))

    # Relationships
    workflow: Workflow | None = Relationship(back_populates="sources")
    parsers: list["Parser"] = Relationship(back_populates="source", cascade_delete=True)
    jobs: list["Job"] = Relationship(back_populates="source", cascade_delete=True)
    records: list["Record"] = Relationship(back_populates="source", cascade_delete=True)


class SourcePublic(SourceBase):
    """Source properties returned via API"""

    id: uuid.UUID
    workflow_id: uuid.UUID
    config: dict | None = None
    sync_cursor: str | None = None
    last_sync_at: datetime | None = None
    error_context: dict | None = None


class SourcesPublic(SQLModel):
    """List of sources with count"""

    data: list[SourcePublic]
    count: int


# ============================================================================
# PARSER MODELS
# ============================================================================


class ParserBase(SQLModel):
    """Base parser properties"""

    name: str = Field(min_length=1, max_length=255)
    engine_type: ParserEngineType
    is_active: bool = True


class ParserCreate(ParserBase):
    """Properties for parser creation"""

    source_id: uuid.UUID
    rules: dict | None = Field(default=None, sa_column=Column(JSONB))


class ParserUpdate(SQLModel):
    """Properties for parser update"""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    engine_type: ParserEngineType | None = None
    rules: dict | None = Field(default=None, sa_column=Column(JSONB))
    is_active: bool | None = None


class Parser(ParserBase, table=True):
    """Parser database model - transforms source data into records"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_id: uuid.UUID = Field(
        foreign_key="source.id", nullable=False, ondelete="CASCADE"
    )
    rules: dict | None = Field(default=None, sa_column=Column(JSONB))
    error_context: dict | None = Field(default=None, sa_column=Column(JSONB))

    # Relationships
    source: Source | None = Relationship(back_populates="parsers")


class ParserPublic(ParserBase):
    """Parser properties returned via API"""

    id: uuid.UUID
    source_id: uuid.UUID
    rules: dict | None = None
    error_context: dict | None = None


class ParsersPublic(SQLModel):
    """List of parsers with count"""

    data: list[ParserPublic]
    count: int


# ============================================================================
# RECORD MODELS
# ============================================================================


class RecordBase(SQLModel):
    """Base record properties"""

    date: date
    status: RecordStatus = RecordStatus.pending


class RecordCreate(RecordBase):
    """Properties for record creation"""

    source_id: uuid.UUID
    workflow_id: uuid.UUID
    data: dict | None = Field(default=None, sa_column=Column(JSONB))
    file_path: str | None = Field(default=None, max_length=500)
    file_hash: str | None = Field(default=None, max_length=64)


class RecordUpdate(SQLModel):
    """Properties for record update"""

    status: RecordStatus | None = None
    data: dict | None = Field(default=None, sa_column=Column(JSONB))
    file_path: str | None = Field(default=None, max_length=500)
    file_hash: str | None = Field(default=None, max_length=64)
    error_context: dict | None = Field(default=None, sa_column=Column(JSONB))


class Record(RecordBase, table=True):
    """Record database model - extracted invoice data"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_id: uuid.UUID = Field(
        foreign_key="source.id", nullable=False, ondelete="CASCADE"
    )
    workflow_id: uuid.UUID = Field(
        foreign_key="workflow.id", nullable=False, ondelete="CASCADE"
    )
    data: dict | None = Field(default=None, sa_column=Column(JSONB))
    file_path: str | None = Field(default=None, max_length=500)
    file_hash: str | None = Field(default=None, max_length=64)
    unique_key: str = Field(index=True, unique=True, max_length=100)
    error_context: dict | None = Field(default=None, sa_column=Column(JSONB))

    # Relationships
    source: Source | None = Relationship(back_populates="records")
    workflow: Workflow | None = Relationship(back_populates="records")

    @staticmethod
    def compute_unique_key(
        source_id: uuid.UUID,
        record_date: date,
        file_content: bytes | None,
        data: dict | None,
    ) -> str:
        """Compute unique key for duplicate detection"""
        parts = [str(source_id), record_date.isoformat()]

        if file_content:
            # Use file hash if file exists
            file_hash = hashlib.sha256(file_content).hexdigest()[:16]
            parts.append(file_hash)
        elif data:
            # Use data hash if no file
            data_str = json.dumps(data, sort_keys=True)
            data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]
            parts.append(data_hash)
        else:
            # Fallback to timestamp
            parts.append(str(int(datetime.now().timestamp())))

        return ":".join(parts)


class RecordPublic(RecordBase):
    """Record properties returned via API"""

    id: uuid.UUID
    source_id: uuid.UUID
    workflow_id: uuid.UUID
    data: dict | None = None
    file_path: str | None = None
    file_hash: str | None = None
    unique_key: str
    error_context: dict | None = None


class RecordsPublic(SQLModel):
    """List of records with count"""

    data: list[RecordPublic]
    count: int


# ============================================================================
# EXPORTER MODELS
# ============================================================================


class ExporterBase(SQLModel):
    """Base exporter properties"""

    name: str = Field(min_length=1, max_length=255)
    type: ExporterType
    is_active: bool = True


class ExporterCreate(ExporterBase):
    """Properties for exporter creation"""

    workflow_id: uuid.UUID
    config: dict | None = Field(default=None, sa_column=Column(JSONB))


class ExporterUpdate(SQLModel):
    """Properties for exporter update"""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    type: ExporterType | None = None
    config: dict | None = Field(default=None, sa_column=Column(JSONB))
    is_active: bool | None = None


class Exporter(ExporterBase, table=True):
    """Exporter database model - exports records to external systems"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workflow_id: uuid.UUID = Field(
        foreign_key="workflow.id", nullable=False, ondelete="CASCADE"
    )
    config: dict | None = Field(default=None, sa_column=Column(JSONB))
    error_context: dict | None = Field(default=None, sa_column=Column(JSONB))

    # Relationships
    workflow: Workflow | None = Relationship(back_populates="exporters")
    mappers: list["Mapper"] = Relationship(
        back_populates="exporter", cascade_delete=True
    )


class ExporterPublic(ExporterBase):
    """Exporter properties returned via API"""

    id: uuid.UUID
    workflow_id: uuid.UUID
    config: dict | None = None
    error_context: dict | None = None


class ExportersPublic(SQLModel):
    """List of exporters with count"""

    data: list[ExporterPublic]
    count: int


# ============================================================================
# MAPPER MODELS
# ============================================================================


class MapperBase(SQLModel):
    """Base mapper properties"""

    name: str = Field(min_length=1, max_length=255)
    mapper_type: MapperType
    is_active: bool = True


class MapperCreate(MapperBase):
    """Properties for mapper creation"""

    exporter_id: uuid.UUID
    transformation_logic: dict | None = Field(default=None, sa_column=Column(JSONB))


class MapperUpdate(SQLModel):
    """Properties for mapper update"""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    mapper_type: MapperType | None = None
    transformation_logic: dict | None = Field(default=None, sa_column=Column(JSONB))
    is_active: bool | None = None


class Mapper(MapperBase, table=True):
    """Mapper database model - transforms records for export"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    exporter_id: uuid.UUID = Field(
        foreign_key="exporter.id", nullable=False, ondelete="CASCADE"
    )
    transformation_logic: dict | None = Field(default=None, sa_column=Column(JSONB))
    error_context: dict | None = Field(default=None, sa_column=Column(JSONB))

    # Relationships
    exporter: Exporter | None = Relationship(back_populates="mappers")


class MapperPublic(MapperBase):
    """Mapper properties returned via API"""

    id: uuid.UUID
    exporter_id: uuid.UUID
    transformation_logic: dict | None = None
    error_context: dict | None = None


class MappersPublic(SQLModel):
    """List of mappers with count"""

    data: list[MapperPublic]
    count: int


# ============================================================================
# JOB MODELS
# ============================================================================


class JobBase(SQLModel):
    """Base job properties"""

    status: JobStatus = JobStatus.queued


class JobCreate(JobBase):
    """Properties for job creation"""

    source_id: uuid.UUID
    scheduled_at: datetime | None = None


class JobUpdate(SQLModel):
    """Properties for job update"""

    status: JobStatus | None = None
    started_at: datetime | None = None
    error_context: dict | None = Field(default=None, sa_column=Column(JSONB))


class Job(JobBase, table=True):
    """Job database model - tracks source sync jobs"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_id: uuid.UUID = Field(
        foreign_key="source.id", nullable=False, ondelete="CASCADE"
    )
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    error_context: dict | None = Field(default=None, sa_column=Column(JSONB))

    # Relationships
    source: Source | None = Relationship(back_populates="jobs")


class JobPublic(JobBase):
    """Job properties returned via API"""

    id: uuid.UUID
    source_id: uuid.UUID
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    error_context: dict | None = None


class JobsPublic(SQLModel):
    """List of jobs with count"""

    data: list[JobPublic]
    count: int


# ============================================================================
# GENERIC MODELS
# ============================================================================


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
