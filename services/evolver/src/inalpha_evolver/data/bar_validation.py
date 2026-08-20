"""Frozen bar identity and OHLCV validation."""
from __future__ import annotations

import math
from typing import Any

from inalpha_paper.kernel.identifiers import InstrumentId
from inalpha_paper.model.data import Bar
from inalpha_shared.errors import ValidationError


def validate_identity(
    raw: dict[str, Any],
    instrument: InstrumentId,
    timeframe: str,
) -> None:
    """Fail closed when response identity differs from the request."""
    expected = {
        "venue": instrument.venue,
        "symbol": instrument.symbol,
        "timeframe": timeframe,
    }
    for field, value in expected.items():
        if field in raw and str(raw[field]) != value:
            raise ValidationError(
                f"bar {field}={raw[field]!r} does not match request {value!r}",
                code="EVOLUTION_DATA_IDENTITY_MISMATCH",
            )


def validate_values(bar: Bar) -> None:
    """Reject non-finite or internally inconsistent OHLCV values."""
    values = (bar.open, bar.high, bar.low, bar.close, bar.volume)
    if not all(math.isfinite(value) for value in values):
        raise ValidationError(
            "bar contains non-finite value", code="EVOLUTION_DATA_INVALID"
        )
    if min(bar.open, bar.high, bar.low, bar.close) <= 0 or bar.volume < 0:
        raise ValidationError(
            "bar price/volume is invalid", code="EVOLUTION_DATA_INVALID"
        )
    if bar.low > min(bar.open, bar.close) or bar.high < max(bar.open, bar.close):
        raise ValidationError(
            "bar OHLC relation is invalid", code="EVOLUTION_DATA_INVALID"
        )


__all__ = ["validate_identity", "validate_values"]
