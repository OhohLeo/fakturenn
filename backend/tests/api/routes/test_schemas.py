"""Tests for SDUI schema API routes."""

from fastapi.testclient import TestClient

from app.core.config import settings


def test_get_source_gmail_schema(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test getting Gmail source schema."""
    response = client.get(
        f"{settings.API_V1_STR}/schemas/source/gmail",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    schema = response.json()
    assert schema["type"] == "object"
    assert "properties" in schema
    # Check for Gmail-specific properties
    assert "query" in schema["properties"] or "filters" in schema["properties"]


def test_get_source_xls_schema(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test getting XLS source schema."""
    response = client.get(
        f"{settings.API_V1_STR}/schemas/source/xls",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    schema = response.json()
    assert schema["type"] == "object"
    assert "properties" in schema


def test_get_exporter_paheko_schema(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test getting Paheko exporter schema."""
    response = client.get(
        f"{settings.API_V1_STR}/schemas/exporter/paheko",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    schema = response.json()
    assert schema["type"] == "object"
    assert "properties" in schema
    # Check for Paheko-specific properties
    assert "api_url" in schema["properties"]


def test_get_exporter_gdrive_schema(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test getting Google Drive exporter schema."""
    response = client.get(
        f"{settings.API_V1_STR}/schemas/exporter/gdrive",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    schema = response.json()
    assert schema["type"] == "object"
    assert "properties" in schema
    # Check for GDrive-specific properties
    assert "folder_id" in schema["properties"]


def test_get_parser_mail2record_schema(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test getting mail2record parser schema."""
    response = client.get(
        f"{settings.API_V1_STR}/schemas/parser/mail2record",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    schema = response.json()
    assert schema["type"] == "object"
    assert "properties" in schema


def test_get_parser_xls2record_schema(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test getting xls2record parser schema."""
    response = client.get(
        f"{settings.API_V1_STR}/schemas/parser/xls2record",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    schema = response.json()
    assert schema["type"] == "object"
    assert "properties" in schema


def test_get_mapper_record2paheko_schema(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test getting record2paheko mapper schema."""
    response = client.get(
        f"{settings.API_V1_STR}/schemas/mapper/record2paheko",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    schema = response.json()
    assert schema["type"] == "object"
    assert "properties" in schema


def test_get_mapper_record2gdrive_schema(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test getting record2gdrive mapper schema."""
    response = client.get(
        f"{settings.API_V1_STR}/schemas/mapper/record2gdrive",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    schema = response.json()
    assert schema["type"] == "object"
    assert "properties" in schema


def test_get_schema_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test getting non-existent schema."""
    response = client.get(
        f"{settings.API_V1_STR}/schemas/source/nonexistent",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


def test_list_available_schemas(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test listing all available schemas."""
    response = client.get(
        f"{settings.API_V1_STR}/schemas/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    schemas = response.json()
    assert isinstance(schemas, dict)
    # Should have source, exporter, parser, mapper categories
    assert "source" in schemas or len(schemas) > 0
