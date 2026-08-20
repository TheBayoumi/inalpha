"""Backfill audit snapshot validation."""
from __future__ import annotations

from typing import Any

from inalpha_shared.errors import ValidationError
from pydantic import ValidationError as PydanticValidationError

from .manifest import BackfillSnapshot


def backfill_snapshot(value: dict[str, Any]) -> BackfillSnapshot:
    """Preserve the data-service response instead of synthetic counters."""
    try:
        return BackfillSnapshot.model_validate(value)
    except PydanticValidationError as exc:
        raise ValidationError(
            "backfill response lacks required audit evidence",
            code="EVOLUTION_BACKFILL_AUDIT_INVALID",
            details={"errors": exc.errors(include_url=False)},
        ) from exc


__all__ = ["backfill_snapshot"]
