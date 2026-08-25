"""Trusted-time policy for frozen evolution datasets."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from inalpha_shared.errors import ValidationError

MAX_AS_OF_CLOCK_SKEW = timedelta(seconds=5)


def normalize_datetime(
    value: datetime,
    *,
    field: str,
    require_aware: bool,
) -> datetime:
    """Normalize to UTC, rejecting a naive cutoff instead of raising TypeError."""
    if value.tzinfo is None:
        if require_aware:
            raise ValidationError(
                f"{field} must be timezone-aware",
                code="EVOLUTION_DATETIME_NAIVE",
                details={"field": field},
            )
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def reject_future_as_of(value: datetime) -> None:
    """Reject a cutoff beyond trusted wall-clock time."""
    if value > datetime.now(UTC) + MAX_AS_OF_CLOCK_SKEW:
        raise ValidationError(
            "evolution as_of exceeds trusted current time",
            code="EVOLUTION_AS_OF_IN_FUTURE",
            details={"as_of": value.isoformat()},
        )


__all__ = ["MAX_AS_OF_CLOCK_SKEW", "normalize_datetime", "reject_future_as_of"]
