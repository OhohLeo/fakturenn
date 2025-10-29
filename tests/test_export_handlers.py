"""Tests for export handlers."""

import tempfile
from pathlib import Path

import pytest

from app.export.base import ExportResult
from app.export.local_storage import LocalStorageExportHandler


class TestLocalStorageExportHandler:
    """Test LocalStorage export handler."""

    @pytest.fixture
    def handler(self) -> LocalStorageExportHandler:
        """Create a test handler."""
        config = {
            "base_path": tempfile.gettempdir(),
            "path_template": "{year}/{month}/{source}_{invoice_id}.pdf",
            "create_directories": True,
        }
        return LocalStorageExportHandler(config)

    @pytest.fixture
    def test_file(self) -> Path:
        """Create a temporary test file."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            f.write(b"test pdf content")
            return Path(f.name)

    def test_handler_initialization(self, handler):
        """Test handler initialization."""
        assert handler.config["base_path"] == tempfile.gettempdir()
        assert (
            handler.config["path_template"]
            == "{year}/{month}/{source}_{invoice_id}.pdf"
        )
        assert handler.config["create_directories"] is True

    @pytest.mark.asyncio
    async def test_export_success(
        self,
        handler: LocalStorageExportHandler,
        test_file: Path,
    ):
        """Test successful export."""
        invoice_data = {
            "file_path": str(test_file),
            "amount_eur": 99.99,
        }
        context = {
            "invoice_id": "INV-001",
            "date": "2025-10-29",
            "amount_eur": 99.99,
            "month": "10",
            "year": "2025",
            "source": "Free",
        }

        result = await handler.export(invoice_data, context)

        assert result.status == "success"
        assert result.external_reference is not None
        assert Path(result.external_reference).exists()

        # Clean up
        Path(result.external_reference).unlink()
        Path(result.external_reference).parent.rmdir()

    @pytest.mark.asyncio
    async def test_export_missing_invoice_data(
        self,
        handler: LocalStorageExportHandler,
    ):
        """Test export with missing invoice data."""
        invoice_data = {}  # Missing file_path
        context = {
            "invoice_id": "INV-001",
            "date": "2025-10-29",
        }

        result = await handler.export(invoice_data, context)

        assert result.status == "failed"
        assert "Missing required invoice data fields" in result.error_message

    @pytest.mark.asyncio
    async def test_export_invalid_path_template(
        self,
        handler: LocalStorageExportHandler,
        test_file: Path,
    ):
        """Test export with invalid path template."""
        handler.config["path_template"] = "{invalid_variable}/test.pdf"

        invoice_data = {
            "file_path": str(test_file),
        }
        context = {
            "invoice_id": "INV-001",
        }

        result = await handler.export(invoice_data, context)

        assert result.status == "failed"
        assert "Unknown variable" in result.error_message

    @pytest.mark.asyncio
    async def test_export_missing_context(
        self,
        handler: LocalStorageExportHandler,
        test_file: Path,
    ):
        """Test export with missing context."""
        invoice_data = {
            "file_path": str(test_file),
        }
        context = {}  # Missing required context

        result = await handler.export(invoice_data, context)

        assert result.status == "failed"
        assert "Missing required context fields" in result.error_message

    @pytest.mark.asyncio
    async def test_export_missing_source_file(
        self,
        handler: LocalStorageExportHandler,
    ):
        """Test export when source file doesn't exist."""
        invoice_data = {
            "file_path": "/nonexistent/file.pdf",
        }
        context = {
            "invoice_id": "INV-001",
            "date": "2025-10-29",
            "amount_eur": 99.99,
            "month": "10",
            "year": "2025",
            "source": "Free",
        }

        result = await handler.export(invoice_data, context)

        assert result.status == "failed"
        assert "Source file not found" in result.error_message


class TestExportResult:
    """Test ExportResult dataclass."""

    def test_successful_result(self):
        """Test successful export result."""
        result = ExportResult(
            status="success",
            external_reference="transaction-123",
        )
        assert result.status == "success"
        assert result.external_reference == "transaction-123"
        assert result.error_message is None

    def test_failed_result(self):
        """Test failed export result."""
        result = ExportResult(
            status="failed",
            error_message="Connection timeout",
        )
        assert result.status == "failed"
        assert result.error_message == "Connection timeout"
        assert result.external_reference is None

    def test_duplicate_skipped_result(self):
        """Test duplicate skipped result."""
        result = ExportResult(
            status="duplicate_skipped",
            error_message="Duplicate entry already exists",
        )
        assert result.status == "duplicate_skipped"
        assert result.error_message == "Duplicate entry already exists"
