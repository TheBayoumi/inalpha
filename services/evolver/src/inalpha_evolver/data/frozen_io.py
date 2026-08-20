"""Fail-closed I/O for frozen bars."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from inalpha_paper.data_client import DataClient, DataServiceError
from inalpha_shared.errors import ValidationError


async def backfill(
    client: DataClient,
    venue: str,
    symbol: str,
    timeframe: str,
    start: datetime,
    cutoff: datetime,
) -> dict[str, Any]:
    """Backfill once and preserve the upstream response."""
    try:
        return await client.backfill_bars(
            venue=venue,
            symbol=symbol,
            timeframe=timeframe,
            from_ts=start,
            to_ts=cutoff,
        )
    except DataServiceError as exc:
        code = (
            "EVOLUTION_DATA_UNREACHABLE"
            if exc.code == "DATA_SERVICE_UNREACHABLE"
            else "EVOLUTION_DATA_FRESHNESS_FAILED"
        )
        raise ValidationError(str(exc), code=code) from exc


async def read_bars(
    client: DataClient,
    venue: str,
    symbol: str,
    timeframe: str,
    start: datetime,
    cutoff: datetime,
) -> list[dict[str, Any]]:
    """Read only the freshly backfilled snapshot without a second refresh."""
    try:
        return await client.get_bars(
            venue=venue,
            symbol=symbol,
            timeframe=timeframe,
            from_ts=start,
            to_ts=cutoff,
            limit=10_001,
            fresh=False,
        )
    except DataServiceError as exc:
        raise ValidationError(str(exc), code="EVOLUTION_DATA_UNREACHABLE") from exc


__all__ = ["backfill", "read_bars"]
