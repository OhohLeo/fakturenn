"""SDUI Schema Registry for dynamic form configuration."""

from app.core.schemas.registry import SchemaRegistry
from app.core.schemas.validator import validate_config

__all__ = ["SchemaRegistry", "validate_config"]
