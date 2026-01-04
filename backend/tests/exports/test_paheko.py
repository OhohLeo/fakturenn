"""Tests for Paheko exporter implementation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exports.paheko import PahekoExporter


@pytest.fixture
def paheko_config():
    """Paheko exporter configuration."""
    return {
        "api_url": "https://test.paheko.cloud",
        "default_year": 1,
    }


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client."""
    client = MagicMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.aclose = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_paheko_exporter_connect(paheko_config, mock_http_client):
    """Test Paheko exporter connection."""
    with patch("httpx.AsyncClient", return_value=mock_http_client):
        exporter = PahekoExporter(paheko_config)
        exporter.api_key = "test-api-key"

        await exporter.connect()

        assert exporter.is_connected
        await exporter.disconnect()


@pytest.mark.asyncio
async def test_paheko_exporter_create_entry(paheko_config, mock_http_client):
    """Test creating a transaction in Paheko."""
    mock_http_client.post.return_value = MagicMock(
        status_code=201,
        json=MagicMock(return_value={"id": 123}),
    )

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        exporter = PahekoExporter(paheko_config)
        exporter.api_key = "test-api-key"

        await exporter.connect()

        transaction_data = {
            "id_year": 1,
            "label": "Test Transaction",
            "date": "2024-01-15",
            "type": "EXPENSE",
            "amount": 100.00,
            "debit": "601",
            "credit": "512A",
            "reference": "INV-001",
        }

        entry_id = await exporter.create_entry(transaction_data)

        assert entry_id == "123"
        mock_http_client.post.assert_called_once()

        await exporter.disconnect()


@pytest.mark.asyncio
async def test_paheko_exporter_check_duplicate(paheko_config, mock_http_client):
    """Test checking for duplicate transactions."""
    # Mock response with existing transaction
    mock_http_client.get.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"results": [{"id": 1, "reference": "INV-001"}]}),
    )

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        exporter = PahekoExporter(paheko_config)
        exporter.api_key = "test-api-key"

        await exporter.connect()

        is_duplicate = await exporter.check_duplicate("INV-001")

        assert is_duplicate is True

        await exporter.disconnect()


@pytest.mark.asyncio
async def test_paheko_exporter_check_not_duplicate(paheko_config, mock_http_client):
    """Test checking non-duplicate transactions."""
    # Mock response with no results
    mock_http_client.get.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"results": []}),
    )

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        exporter = PahekoExporter(paheko_config)
        exporter.api_key = "test-api-key"

        await exporter.connect()

        is_duplicate = await exporter.check_duplicate("INV-NEW")

        assert is_duplicate is False

        await exporter.disconnect()


@pytest.mark.asyncio
async def test_paheko_exporter_get_accounting_years(paheko_config, mock_http_client):
    """Test getting accounting years."""
    mock_http_client.get.return_value = MagicMock(
        status_code=200,
        json=MagicMock(
            return_value=[
                {"id": 1, "label": "2024", "start_date": "2024-01-01", "end_date": "2024-12-31"},
                {"id": 2, "label": "2023", "start_date": "2023-01-01", "end_date": "2023-12-31"},
            ]
        ),
    )

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        exporter = PahekoExporter(paheko_config)
        exporter.api_key = "test-api-key"

        await exporter.connect()

        years = await exporter.get_accounting_years()

        assert len(years) == 2
        assert years[0]["label"] == "2024"

        await exporter.disconnect()


@pytest.mark.asyncio
async def test_paheko_exporter_match_fiscal_year(paheko_config, mock_http_client):
    """Test matching fiscal year by date."""
    mock_http_client.get.return_value = MagicMock(
        status_code=200,
        json=MagicMock(
            return_value=[
                {"id": 1, "label": "2024", "start_date": "2024-01-01", "end_date": "2024-12-31"},
                {"id": 2, "label": "2023", "start_date": "2023-01-01", "end_date": "2023-12-31"},
            ]
        ),
    )

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        exporter = PahekoExporter(paheko_config)
        exporter.api_key = "test-api-key"

        await exporter.connect()

        year_id = await exporter.match_fiscal_year("2024-06-15")

        assert year_id == 1

        await exporter.disconnect()


@pytest.mark.asyncio
async def test_paheko_exporter_context_manager(paheko_config, mock_http_client):
    """Test using Paheko exporter as context manager."""
    with patch("httpx.AsyncClient", return_value=mock_http_client):
        async with PahekoExporter(paheko_config) as exporter:
            exporter.api_key = "test-api-key"
            assert exporter.is_connected

        assert not exporter.is_connected
