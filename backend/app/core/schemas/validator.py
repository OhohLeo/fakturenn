"""JSON Schema validation for SDUI config fields."""

from typing import Any

from jsonschema import ValidationError, validate

from app.core.schemas.registry import SchemaRegistry


class SchemaValidationError(Exception):
    """Raised when config validation fails."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


def validate_config(
    entity_type: str,
    provider_type: str,
    config: dict[str, Any],
) -> None:
    """Validate config against the registered JSON Schema.

    Args:
        entity_type: Type of entity (e.g., 'source', 'exporter')
        provider_type: Specific provider (e.g., 'gmail', 'paheko')
        config: Configuration dict to validate

    Raises:
        SchemaValidationError: If validation fails or schema not found
    """
    schema = SchemaRegistry.get(entity_type, provider_type)

    if schema is None:
        raise SchemaValidationError(
            f"No schema registered for {entity_type}/{provider_type}"
        )

    try:
        validate(instance=config, schema=schema)
    except ValidationError as e:
        # Collect all validation errors
        errors = [e.message]
        for error in e.context:
            errors.append(f"{error.json_path}: {error.message}")
        raise SchemaValidationError(
            f"Config validation failed for {entity_type}/{provider_type}",
            errors=errors,
        ) from e


def get_schema_or_404(entity_type: str, provider_type: str) -> dict[str, Any]:
    """Get schema or raise error with 404-friendly message.

    Args:
        entity_type: Type of entity
        provider_type: Specific provider

    Returns:
        JSON Schema definition

    Raises:
        SchemaValidationError: If schema not found
    """
    schema = SchemaRegistry.get(entity_type, provider_type)
    if schema is None:
        raise SchemaValidationError(
            f"Schema not found for {entity_type}/{provider_type}"
        )
    return schema
