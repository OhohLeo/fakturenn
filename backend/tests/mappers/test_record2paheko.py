"""Tests for Record2Paheko mapper implementation."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.exports.paheko import PahekoExporter
from app.mappers.record2paheko import Record2PahekoMapper
from app.models import Record, RecordStatus


@pytest.fixture
def sample_record():
    """Create a sample record for testing."""
    return Record(
        id=uuid4(),
        source_id=uuid4(),
        workflow_id=uuid4(),
        date=date(2024, 1, 15),
        data={
            "invoice_id": "INV-001",
            "amount_text": "100,50 €",
            "description": "Test invoice",
        },
        unique_key="test-unique-key",
        status=RecordStatus.pending,
    )


@pytest.fixture
def mapper_rules():
    """Mapper transformation rules."""
    return {
        "transaction_type": "EXPENSE",
        "label_template": "{invoice_id} - {month} {year}",
        "debit_account": "601",
        "credit_account": "512A",
        "reference_field": "invoice_id",
        "amount_field": "amount_text",
        "year_matching": "auto",
        "amount_parsing": {
            "decimal_separator": ",",
            "thousands_separator": " ",
            "currency_symbol": "€",
        },
    }


@pytest.fixture
def mock_paheko_exporter():
    """Create a mock Paheko exporter."""
    exporter = MagicMock(spec=PahekoExporter)
    exporter.check_duplicate = AsyncMock(return_value=False)
    exporter.create_entry = AsyncMock(return_value="123")
    exporter.match_fiscal_year = AsyncMock(return_value=1)
    return exporter


@pytest.mark.asyncio
async def test_record2paheko_mapper_basic(
    sample_record, mapper_rules, mock_paheko_exporter
):
    """Test basic record to Paheko mapping."""
    mapper = Record2PahekoMapper(exporter=mock_paheko_exporter, rules=mapper_rules)

    result = await mapper.transform_and_export(sample_record)

    assert result is True
    mock_paheko_exporter.create_entry.assert_called_once()

    # Check the transaction data passed to create_entry
    call_args = mock_paheko_exporter.create_entry.call_args[0][0]
    assert call_args["id_year"] == 1
    assert call_args["type"] == "EXPENSE"
    assert call_args["debit"] == "601"
    assert call_args["credit"] == "512A"
    assert call_args["reference"] == "INV-001"


@pytest.mark.asyncio
async def test_record2paheko_mapper_label_template(
    sample_record, mapper_rules, mock_paheko_exporter
):
    """Test label template rendering."""
    mapper = Record2PahekoMapper(exporter=mock_paheko_exporter, rules=mapper_rules)

    await mapper.transform_and_export(sample_record)

    call_args = mock_paheko_exporter.create_entry.call_args[0][0]
    # Label should be rendered with invoice_id, month (January in French), and year
    assert "INV-001" in call_args["label"]
    assert "Janvier" in call_args["label"]
    assert "2024" in call_args["label"]


@pytest.mark.asyncio
async def test_record2paheko_mapper_amount_parsing(
    sample_record, mapper_rules, mock_paheko_exporter
):
    """Test amount parsing with European format."""
    mapper = Record2PahekoMapper(exporter=mock_paheko_exporter, rules=mapper_rules)

    await mapper.transform_and_export(sample_record)

    call_args = mock_paheko_exporter.create_entry.call_args[0][0]
    # Amount "100,50 €" should be parsed to 100.50
    assert call_args["amount"] == 100.50


@pytest.mark.asyncio
async def test_record2paheko_mapper_skip_duplicate(
    sample_record, mapper_rules, mock_paheko_exporter
):
    """Test skipping duplicate records."""
    mock_paheko_exporter.check_duplicate.return_value = True

    mapper = Record2PahekoMapper(exporter=mock_paheko_exporter, rules=mapper_rules)

    result = await mapper.transform_and_export(sample_record)

    assert result is False
    mock_paheko_exporter.create_entry.assert_not_called()


@pytest.mark.asyncio
async def test_record2paheko_mapper_fixed_year(
    sample_record, mapper_rules, mock_paheko_exporter
):
    """Test using fixed fiscal year."""
    mapper_rules["year_matching"] = "fixed"
    mapper_rules["fixed_year_id"] = 5

    mapper = Record2PahekoMapper(exporter=mock_paheko_exporter, rules=mapper_rules)

    await mapper.transform_and_export(sample_record)

    call_args = mock_paheko_exporter.create_entry.call_args[0][0]
    assert call_args["id_year"] == 5
    mock_paheko_exporter.match_fiscal_year.assert_not_called()


@pytest.mark.asyncio
async def test_record2paheko_mapper_no_fiscal_year(
    sample_record, mapper_rules, mock_paheko_exporter
):
    """Test error when no matching fiscal year."""
    mock_paheko_exporter.match_fiscal_year.return_value = None

    mapper = Record2PahekoMapper(exporter=mock_paheko_exporter, rules=mapper_rules)

    with pytest.raises(Exception) as exc_info:
        await mapper.transform_and_export(sample_record)

    assert "fiscal year" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_record2paheko_mapper_invalid_amount(
    sample_record, mapper_rules, mock_paheko_exporter
):
    """Test error with invalid amount."""
    sample_record.data["amount_text"] = "invalid"

    mapper = Record2PahekoMapper(exporter=mock_paheko_exporter, rules=mapper_rules)

    with pytest.raises(Exception) as exc_info:
        await mapper.transform_and_export(sample_record)

    assert "amount" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_record2paheko_mapper_missing_accounts(
    sample_record, mock_paheko_exporter
):
    """Test error when missing debit/credit accounts."""
    rules = {
        "transaction_type": "EXPENSE",
        "label_template": "{invoice_id}",
        # Missing debit and credit accounts
    }

    mapper = Record2PahekoMapper(exporter=mock_paheko_exporter, rules=rules)

    with pytest.raises(Exception) as exc_info:
        await mapper.transform_and_export(sample_record)

    assert "debit" in str(exc_info.value).lower() or "credit" in str(exc_info.value).lower()
