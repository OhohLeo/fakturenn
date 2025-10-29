"""Initial schema creation.

Revision ID: 001
Revises:
Create Date: 2025-10-29 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=True, server_default="fr"),
        sa.Column("timezone", sa.String(length=50), nullable=True, server_default="Europe/Paris"),
        sa.Column("role", sa.String(length=20), nullable=True, server_default="user"),
        sa.Column("active", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("role IN ('admin', 'user')"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_username", "users", ["username"])

    # Create automations table
    op.create_table(
        "automations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("schedule", sa.String(length=100), nullable=True),
        sa.Column("from_date_rule", sa.String(length=50), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_automation_user_name"),
    )
    op.create_index("idx_automations_user", "automations", ["user_id"])
    op.create_index("ix_automations_id", "automations", ["id"])

    # Create sources table
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("automation_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("email_sender_from", sa.String(length=255), nullable=True),
        sa.Column("email_subject_contains", sa.String(length=255), nullable=True),
        sa.Column("extraction_params", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("max_results", sa.Integer(), nullable=True, server_default="30"),
        sa.Column("active", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("type IN ('FreeInvoice', 'FreeMobileInvoice', 'Gmail')"),
        sa.ForeignKeyConstraint(["automation_id"], ["automations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sources_automation", "sources", ["automation_id"])
    op.create_index("ix_sources_id", "sources", ["id"])

    # Create exports table
    op.create_table(
        "exports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("automation_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("configuration", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("type IN ('Paheko', 'LocalStorage', 'GoogleDrive')"),
        sa.ForeignKeyConstraint(["automation_id"], ["automations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_exports_automation", "exports", ["automation_id"])
    op.create_index("ix_exports_id", "exports", ["id"])

    # Create source_export_mappings table
    op.create_table(
        "source_export_mappings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("export_id", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("conditions", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(["export_id"], ["exports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "export_id", name="uq_source_export"),
    )
    op.create_index("idx_mappings_export", "source_export_mappings", ["export_id"])
    op.create_index("idx_mappings_source", "source_export_mappings", ["source_id"])
    op.create_index("ix_source_export_mappings_id", "source_export_mappings", ["id"])

    # Create jobs table
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("automation_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("from_date", sa.Date(), nullable=True),
        sa.Column("max_results", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("stats", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("status IN ('pending', 'running', 'completed', 'failed')"),
        sa.ForeignKeyConstraint(["automation_id"], ["automations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_jobs_automation", "jobs", ["automation_id"])
    op.create_index("idx_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_id", "jobs", ["id"])

    # Create export_history table
    op.create_table(
        "export_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("export_id", sa.Integer(), nullable=True),
        sa.Column("export_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("exported_at", sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("context", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.CheckConstraint("status IN ('success', 'failed', 'duplicate_skipped')"),
        sa.ForeignKeyConstraint(["export_id"], ["exports.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_export_history_export", "export_history", ["export_id"])
    op.create_index("idx_export_history_job", "export_history", ["job_id"])
    op.create_index("idx_export_history_status", "export_history", ["status"])
    op.create_index("ix_export_history_id", "export_history", ["id"])

    # Create audit_log table
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=True),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("details", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_log_resource", "audit_log", ["resource_type", "resource_id"])
    op.create_index("idx_audit_log_timestamp", "audit_log", ["timestamp"], reverse_order=False)
    op.create_index("idx_audit_log_user", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_id", "audit_log", ["id"])


def downgrade() -> None:
    # Drop all tables in reverse order
    op.drop_index("ix_audit_log_id", table_name="audit_log")
    op.drop_index("idx_audit_log_user", table_name="audit_log")
    op.drop_index("idx_audit_log_timestamp", table_name="audit_log")
    op.drop_index("idx_audit_log_resource", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index("ix_export_history_id", table_name="export_history")
    op.drop_index("idx_export_history_status", table_name="export_history")
    op.drop_index("idx_export_history_job", table_name="export_history")
    op.drop_index("idx_export_history_export", table_name="export_history")
    op.drop_table("export_history")

    op.drop_index("ix_jobs_id", table_name="jobs")
    op.drop_index("idx_jobs_status", table_name="jobs")
    op.drop_index("idx_jobs_automation", table_name="jobs")
    op.drop_table("jobs")

    op.drop_index("ix_source_export_mappings_id", table_name="source_export_mappings")
    op.drop_index("idx_mappings_source", table_name="source_export_mappings")
    op.drop_index("idx_mappings_export", table_name="source_export_mappings")
    op.drop_table("source_export_mappings")

    op.drop_index("ix_exports_id", table_name="exports")
    op.drop_index("idx_exports_automation", table_name="exports")
    op.drop_table("exports")

    op.drop_index("ix_sources_id", table_name="sources")
    op.drop_index("idx_sources_automation", table_name="sources")
    op.drop_table("sources")

    op.drop_index("ix_automations_id", table_name="automations")
    op.drop_index("idx_automations_user", table_name="automations")
    op.drop_table("automations")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
