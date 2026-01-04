"""Structured logging utilities for error tracking.

Provides consistent error context formatting for:
- Sources
- Parsers
- Exporters
- Mappers
- Workers
"""

import logging
import traceback
from datetime import datetime
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


def format_error_context(
    error: Exception,
    component: str,
    entity_id: UUID | str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Format error context for storage in database.

    Args:
        error: The exception that occurred
        component: Component name (source, parser, exporter, mapper, worker)
        entity_id: Optional entity UUID (source_id, exporter_id, etc.)
        extra: Additional context data

    Returns:
        Structured error context dict for storage
    """
    context: dict[str, Any] = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "component": component,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if entity_id:
        context["entity_id"] = str(entity_id)

    if extra:
        context["details"] = extra

    # Add truncated traceback for debugging
    tb = traceback.format_exc()
    if tb and tb != "NoneType: None\n":
        # Keep last 5 frames to avoid huge context
        tb_lines = tb.split("\n")
        context["traceback"] = "\n".join(tb_lines[-20:])

    return context


def log_error_context(
    error: Exception,
    component: str,
    entity_id: UUID | str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Log error and return formatted context.

    Combines logging with context formatting for consistency.

    Args:
        error: The exception that occurred
        component: Component name
        entity_id: Optional entity UUID
        extra: Additional context data

    Returns:
        Structured error context dict
    """
    context = format_error_context(error, component, entity_id, extra)

    # Log with structured data
    logger.error(
        f"[{component}] Error in {entity_id or 'unknown'}: {error}",
        extra={"error_context": context},
    )

    return context


class ErrorContextMixin:
    """Mixin for classes that need error context tracking.

    Provides consistent error handling and context formatting.
    """

    _component_name: str = "unknown"

    def _format_error(
        self,
        error: Exception,
        entity_id: UUID | str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Format error for this component."""
        return format_error_context(
            error=error,
            component=self._component_name,
            entity_id=entity_id,
            extra=extra,
        )

    def _log_error(
        self,
        error: Exception,
        entity_id: UUID | str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Log and format error for this component."""
        return log_error_context(
            error=error,
            component=self._component_name,
            entity_id=entity_id,
            extra=extra,
        )
