"""API routes for SDUI JSON Schema endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser
from app.core.schemas.registry import SchemaRegistry
from app.core.schemas.validator import get_schema_or_404, SchemaValidationError

router = APIRouter(prefix="/schemas", tags=["schemas"])


@router.get("/")
def list_schemas(
    _current_user: CurrentUser,
    entity_type: str | None = None,
) -> list[dict[str, str]]:
    """
    List all available schemas.

    Optional filter by entity_type (source, parser, exporter, mapper).
    """
    return SchemaRegistry.list_schemas(entity_type)


@router.get("/{entity_type}/{provider_type}")
def get_schema(
    _current_user: CurrentUser,
    entity_type: str,
    provider_type: str,
) -> dict[str, Any]:
    """
    Get JSON Schema for a specific entity type and provider.

    The schema can be used to render dynamic forms in the frontend.
    """
    try:
        return get_schema_or_404(entity_type, provider_type)
    except SchemaValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{entity_type}/{provider_type}/validate")
def validate_config(
    _current_user: CurrentUser,
    entity_type: str,
    provider_type: str,
    config: dict[str, Any],
) -> dict[str, str]:
    """
    Validate a config against its schema.

    Returns success message or validation errors.
    """
    from app.core.schemas.validator import validate_config as do_validate

    try:
        do_validate(entity_type, provider_type, config)
        return {"status": "valid", "message": "Configuration is valid"}
    except SchemaValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={"status": "invalid", "message": str(e), "errors": e.errors},
        )
