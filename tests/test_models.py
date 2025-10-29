"""Tests for SQLAlchemy ORM models."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    User,
    Automation,
    Source,
    Export,
    SourceExportMapping,
    Job,
    ExportHistory,
)


class TestUserModel:
    """Test User model."""

    @pytest.mark.asyncio
    async def test_user_creation(self, db_session: AsyncSession):
        """Test creating a user."""
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_pass",
            language="fr",
            timezone="Europe/Paris",
            role="user",
            active=True,
        )
        db_session.add(user)
        await db_session.commit()

        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == "user"
        assert user.active is True

    @pytest.mark.asyncio
    async def test_user_relationships(self, db_session: AsyncSession, test_user: User):
        """Test user relationships."""
        from sqlalchemy import select

        # Create automation for user
        automation = Automation(
            user_id=test_user.id,
            name="Test Automation",
            active=True,
        )
        db_session.add(automation)
        await db_session.commit()

        # Query automations for the user
        result = await db_session.execute(
            select(Automation).where(Automation.user_id == test_user.id)
        )
        automations = result.scalars().all()

        # Verify relationship
        assert len(automations) == 1
        assert automations[0].name == "Test Automation"


class TestAutomationModel:
    """Test Automation model."""

    @pytest.mark.asyncio
    async def test_automation_creation(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test creating an automation."""
        automation = Automation(
            user_id=test_user.id,
            name="Invoice Processing",
            description="Process Free invoices",
            schedule="0 9 * * *",  # Daily at 9am
            active=True,
        )
        db_session.add(automation)
        await db_session.commit()

        assert automation.id is not None
        assert automation.user_id == test_user.id
        assert automation.name == "Invoice Processing"
        assert automation.schedule == "0 9 * * *"

    @pytest.mark.asyncio
    async def test_automation_unique_constraint(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test unique constraint on (user_id, name)."""
        automation1 = Automation(
            user_id=test_user.id,
            name="Unique Name",
        )
        db_session.add(automation1)
        await db_session.commit()

        # Try to create another with same name for same user
        automation2 = Automation(
            user_id=test_user.id,
            name="Unique Name",
        )
        db_session.add(automation2)

        with pytest.raises(Exception):  # IntegrityError
            await db_session.commit()


class TestSourceModel:
    """Test Source model."""

    @pytest.mark.asyncio
    async def test_source_creation(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test creating a source."""
        automation = Automation(
            user_id=test_user.id,
            name="Test Automation",
        )
        db_session.add(automation)
        await db_session.commit()

        source = Source(
            automation_id=automation.id,
            name="Gmail Invoices",
            type="Gmail",
            email_sender_from="billing@example.com",
            email_subject_contains="Invoice",
            max_results=50,
            active=True,
        )
        db_session.add(source)
        await db_session.commit()

        assert source.id is not None
        assert source.type == "Gmail"
        assert source.email_sender_from == "billing@example.com"

    @pytest.mark.asyncio
    async def test_source_type_constraint(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test source type constraint."""
        automation = Automation(
            user_id=test_user.id,
            name="Test Automation",
        )
        db_session.add(automation)
        await db_session.commit()

        source = Source(
            automation_id=automation.id,
            name="Invalid Source",
            type="InvalidType",  # Invalid type
        )
        db_session.add(source)

        with pytest.raises(Exception):  # IntegrityError from CHECK constraint
            await db_session.commit()


class TestExportModel:
    """Test Export model."""

    @pytest.mark.asyncio
    async def test_export_creation(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test creating an export."""
        automation = Automation(
            user_id=test_user.id,
            name="Test Automation",
        )
        db_session.add(automation)
        await db_session.commit()

        export = Export(
            automation_id=automation.id,
            name="Paheko Accounting",
            type="Paheko",
            configuration={
                "paheko_type": "EXPENSE",
                "label_template": "Invoice {invoice_id}",
                "debit": "601",
                "credit": "401",
            },
            active=True,
        )
        db_session.add(export)
        await db_session.commit()

        assert export.id is not None
        assert export.type == "Paheko"
        assert export.configuration["label_template"] == "Invoice {invoice_id}"


class TestJobModel:
    """Test Job model."""

    @pytest.mark.asyncio
    async def test_job_creation(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test creating a job."""
        automation = Automation(
            user_id=test_user.id,
            name="Test Automation",
        )
        db_session.add(automation)
        await db_session.commit()

        job = Job(
            automation_id=automation.id,
            status="pending",
            max_results=30,
        )
        db_session.add(job)
        await db_session.commit()

        assert job.id is not None
        assert job.status == "pending"
        assert job.started_at is None

    @pytest.mark.asyncio
    async def test_job_status_constraint(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test job status constraint."""
        automation = Automation(
            user_id=test_user.id,
            name="Test Automation",
        )
        db_session.add(automation)
        await db_session.commit()

        job = Job(
            automation_id=automation.id,
            status="invalid_status",  # Invalid status
        )
        db_session.add(job)

        with pytest.raises(Exception):  # IntegrityError from CHECK constraint
            await db_session.commit()


class TestSourceExportMappingModel:
    """Test SourceExportMapping model."""

    @pytest.mark.asyncio
    async def test_mapping_creation(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test creating a source-export mapping."""
        automation = Automation(
            user_id=test_user.id,
            name="Test Automation",
        )
        db_session.add(automation)
        await db_session.commit()

        source = Source(
            automation_id=automation.id,
            name="Gmail",
            type="Gmail",
        )
        db_session.add(source)

        export = Export(
            automation_id=automation.id,
            name="Paheko",
            type="Paheko",
            configuration={},
        )
        db_session.add(export)
        await db_session.commit()

        mapping = SourceExportMapping(
            source_id=source.id,
            export_id=export.id,
            priority=1,
        )
        db_session.add(mapping)
        await db_session.commit()

        assert mapping.id is not None
        assert mapping.source_id == source.id
        assert mapping.export_id == export.id

    @pytest.mark.asyncio
    async def test_mapping_unique_constraint(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test unique constraint on (source_id, export_id)."""
        automation = Automation(
            user_id=test_user.id,
            name="Test Automation",
        )
        db_session.add(automation)
        await db_session.commit()

        source = Source(
            automation_id=automation.id,
            name="Gmail",
            type="Gmail",
        )
        export = Export(
            automation_id=automation.id,
            name="Paheko",
            type="Paheko",
            configuration={},
        )
        db_session.add(source)
        db_session.add(export)
        await db_session.commit()

        mapping1 = SourceExportMapping(
            source_id=source.id,
            export_id=export.id,
        )
        db_session.add(mapping1)
        await db_session.commit()

        # Try to create duplicate
        mapping2 = SourceExportMapping(
            source_id=source.id,
            export_id=export.id,
        )
        db_session.add(mapping2)

        with pytest.raises(Exception):  # IntegrityError
            await db_session.commit()


class TestExportHistoryModel:
    """Test ExportHistory model."""

    @pytest.mark.asyncio
    async def test_export_history_creation(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test creating export history record."""
        automation = Automation(
            user_id=test_user.id,
            name="Test Automation",
        )
        db_session.add(automation)
        await db_session.commit()

        job = Job(
            automation_id=automation.id,
            status="completed",
        )
        db_session.add(job)
        await db_session.commit()

        history = ExportHistory(
            job_id=job.id,
            export_type="Paheko",
            status="success",
            context={"invoice_id": "INV-001"},
            external_reference="trans-123",
        )
        db_session.add(history)
        await db_session.commit()

        assert history.id is not None
        assert history.status == "success"
        assert history.external_reference == "trans-123"
