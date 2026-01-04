"""Schema Registry for SDUI dynamic forms.

Maps (entity_type, provider_type) to JSON Schema definitions that are used
to generate dynamic forms in the frontend.
"""

from typing import Any


class SchemaRegistry:
    """Registry for JSON Schema definitions used by SDUI forms."""

    _schemas: dict[tuple[str, str], dict[str, Any]] = {}

    @classmethod
    def register(cls, entity_type: str, provider_type: str, schema: dict[str, Any]) -> None:
        """Register a schema for a given entity type and provider.

        Args:
            entity_type: Type of entity (e.g., 'source', 'exporter', 'parser', 'mapper')
            provider_type: Specific provider (e.g., 'gmail', 'paheko', 'mail2record')
            schema: JSON Schema definition
        """
        cls._schemas[(entity_type, provider_type)] = schema

    @classmethod
    def get(cls, entity_type: str, provider_type: str) -> dict[str, Any] | None:
        """Get schema for a given entity type and provider.

        Args:
            entity_type: Type of entity
            provider_type: Specific provider

        Returns:
            JSON Schema definition or None if not found
        """
        return cls._schemas.get((entity_type, provider_type))

    @classmethod
    def list_schemas(cls, entity_type: str | None = None) -> list[dict[str, str]]:
        """List all registered schemas.

        Args:
            entity_type: Optional filter by entity type

        Returns:
            List of dicts with entity_type and provider_type keys
        """
        result = []
        for (etype, ptype) in cls._schemas:
            if entity_type is None or entity_type == etype:
                result.append({"entity_type": etype, "provider_type": ptype})
        return result

    @classmethod
    def clear(cls) -> None:
        """Clear all registered schemas (mainly for testing)."""
        cls._schemas.clear()


def _register_all_schemas() -> None:
    """Register all provider schemas at import time."""
    from app.core.schemas.providers import (
        exporter_gdrive,
        exporter_paheko,
        mapper_record2gdrive,
        mapper_record2paheko,
        parser_mail2record,
        parser_xls2record,
        source_gmail,
        source_xls,
    )

    # Register source schemas
    SchemaRegistry.register("source", "gmail", source_gmail.SCHEMA)
    SchemaRegistry.register("source", "xls", source_xls.SCHEMA)

    # Register parser schemas
    SchemaRegistry.register("parser", "mail2record", parser_mail2record.SCHEMA)
    SchemaRegistry.register("parser", "xls2record", parser_xls2record.SCHEMA)

    # Register exporter schemas
    SchemaRegistry.register("exporter", "paheko", exporter_paheko.SCHEMA)
    SchemaRegistry.register("exporter", "gdrive", exporter_gdrive.SCHEMA)

    # Register mapper schemas
    SchemaRegistry.register("mapper", "record2paheko", mapper_record2paheko.SCHEMA)
    SchemaRegistry.register("mapper", "record2gdrive", mapper_record2gdrive.SCHEMA)


# Register schemas on module import
_register_all_schemas()
