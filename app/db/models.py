"""SQLAlchemy ORM models for Fakturenn."""

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Index,
    JSON,
    Date,
    INET,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """User model for multi-tenant support."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    language = Column(String(10), default="fr")
    timezone = Column(String(50), default="Europe/Paris")
    role = Column(String(20), default="user")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    automations = relationship(
        "Automation", back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs = relationship("AuditLog", back_populates="user")

    __table_args__ = (CheckConstraint("role IN ('admin', 'user')"),)


class Automation(Base):
    """High-level automation orchestration."""

    __tablename__ = "automations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    schedule = Column(String(100), nullable=True)  # Cron expression
    from_date_rule = Column(String(50), nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="automations")
    sources = relationship(
        "Source", back_populates="automation", cascade="all, delete-orphan"
    )
    exports = relationship(
        "Export", back_populates="automation", cascade="all, delete-orphan"
    )
    jobs = relationship(
        "Job", back_populates="automation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_automation_user_name"),
        Index("idx_automations_user", "user_id"),
    )


class Source(Base):
    """Reusable source definitions."""

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    automation_id = Column(
        Integer, ForeignKey("automations.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)
    email_sender_from = Column(String(255), nullable=True)
    email_subject_contains = Column(String(255), nullable=True)
    extraction_params = Column(JSON, nullable=True)
    max_results = Column(Integer, default=30)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    automation = relationship("Automation", back_populates="sources")
    export_mappings = relationship(
        "SourceExportMapping", back_populates="source", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("type IN ('FreeInvoice', 'FreeMobileInvoice', 'Gmail')"),
        Index("idx_sources_automation", "automation_id"),
    )


class Export(Base):
    """Reusable export definitions (Paheko, LocalStorage, GoogleDrive)."""

    __tablename__ = "exports"

    id = Column(Integer, primary_key=True, index=True)
    automation_id = Column(
        Integer, ForeignKey("automations.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)  # Paheko, LocalStorage, GoogleDrive
    configuration = Column(JSON, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    automation = relationship("Automation", back_populates="exports")
    export_mappings = relationship(
        "SourceExportMapping", back_populates="export", cascade="all, delete-orphan"
    )
    export_histories = relationship("ExportHistory", back_populates="export")

    __table_args__ = (
        CheckConstraint("type IN ('Paheko', 'LocalStorage', 'GoogleDrive')"),
        Index("idx_exports_automation", "automation_id"),
    )


class SourceExportMapping(Base):
    """Many-to-many mapping between sources and exports."""

    __tablename__ = "source_export_mappings"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(
        Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    export_id = Column(
        Integer, ForeignKey("exports.id", ondelete="CASCADE"), nullable=False
    )
    priority = Column(Integer, default=1)
    conditions = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    source = relationship("Source", back_populates="export_mappings")
    export = relationship("Export", back_populates="export_mappings")

    __table_args__ = (
        UniqueConstraint("source_id", "export_id", name="uq_source_export"),
        Index("idx_mappings_source", "source_id"),
        Index("idx_mappings_export", "export_id"),
    )


class Job(Base):
    """Job execution tracking."""

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    automation_id = Column(
        Integer, ForeignKey("automations.id", ondelete="CASCADE"), nullable=False
    )
    status = Column(String(20), nullable=False, default="pending")
    from_date = Column(Date, nullable=True)
    max_results = Column(Integer, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    stats = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    automation = relationship("Automation", back_populates="jobs")
    export_histories = relationship(
        "ExportHistory", back_populates="job", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'running', 'completed', 'failed')"),
        Index("idx_jobs_automation", "automation_id"),
        Index("idx_jobs_status", "status"),
    )


class ExportHistory(Base):
    """Export audit trail (no invoice metadata stored)."""

    __tablename__ = "export_history"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    export_id = Column(
        Integer, ForeignKey("exports.id", ondelete="SET NULL"), nullable=True
    )
    export_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    exported_at = Column(DateTime, default=datetime.utcnow)
    error_message = Column(Text, nullable=True)
    context = Column(
        JSON, nullable=True
    )  # {invoice_id, date, amount_eur, month, year, file_path}
    external_reference = Column(
        String(255), nullable=True
    )  # Paheko transaction ID, Google Drive file ID, etc.

    # Relationships
    job = relationship("Job", back_populates="export_histories")
    export = relationship("Export", back_populates="export_histories")

    __table_args__ = (
        CheckConstraint("status IN ('success', 'failed', 'duplicate_skipped')"),
        Index("idx_export_history_job", "job_id"),
        Index("idx_export_history_export", "export_id"),
        Index("idx_export_history_status", "status"),
    )


class AuditLog(Base):
    """Audit log for compliance and debugging."""

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_log_user", "user_id"),
        Index("idx_audit_log_timestamp", "timestamp"),
        Index("idx_audit_log_resource", "resource_type", "resource_id"),
    )
