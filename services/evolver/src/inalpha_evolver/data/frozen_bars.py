from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from inalpha_paper.data_client import DataClient, DataServiceError
from inalpha_paper.kernel.identifiers import InstrumentId
from inalpha_paper.market_evaluation import build_market_evaluation_context
from inalpha_shared.errors import ValidationError

from .bar_quality import prepare_frozen_bars
from .manifest import DatasetManifest, FrozenDataset


class FrozenBarsLoader:

    def __init__(self, data_client: DataClient) -> None:
        self._data_client = data_client

    async def load(
        self,
        *,
        venue: str,
        symbol: str,
        timeframe: str,
        from_ts: datetime,
        as_of: datetime,
    ) -> FrozenDataset:
        start = _utc(from_ts)
        cutoff = _utc(as_of)
        if start >= cutoff:
            raise ValidationError(
                "evolution from_ts must be earlier than as_of",
                code="EVOLUTION_DATA_RANGE_INVALID",
            )
        context = build_market_evaluation_context(
            venue=venue,
            symbol=symbol,
            timeframe=timeframe,
            as_of=cutoff,
        )
        try:
            backfill = await self._data_client.backfill_bars(
                venue=venue,
                symbol=symbol,
                timeframe=context.data_timeframe,
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
        try:
            raw_bars = await self._data_client.get_bars(
                venue=venue,
                symbol=symbol,
                timeframe=context.data_timeframe,
                from_ts=start,
                to_ts=cutoff,
                limit=10_001,
                fresh=False,
            )
        except DataServiceError as exc:
            raise ValidationError(
                str(exc),
                code="EVOLUTION_DATA_UNREACHABLE",
            ) from exc
        if len(raw_bars) > 10_000:
            raise ValidationError(
                "evolution dataset exceeds 10000 bars",
                code="EVOLUTION_DATA_LIMIT_EXCEEDED",
            )

        instrument = InstrumentId(symbol=symbol, venue=venue)
        bars, content_hash, lag = prepare_frozen_bars(
            raw_bars,
            instrument_id=instrument,
            context=context,
            as_of=cutoff,
        )
        first = datetime.fromtimestamp(bars[0].ts_event / 1_000_000_000, tz=UTC)
        latest = datetime.fromtimestamp(bars[-1].ts_event / 1_000_000_000, tz=UTC)
        manifest = DatasetManifest(
            venue=venue,
            symbol=symbol,
            requested_timeframe=timeframe,
            data_timeframe=context.data_timeframe,
            canonical_timeframe=context.canonical_timeframe,
            requested_from=start,
            requested_as_of=cutoff,
            effective_from=first,
            effective_to=latest,
            latest_bar_ts=latest,
            bar_count=len(bars),
            freshness_lag_seconds=lag,
            annualization_periods=context.annualization_periods,
            calendar_code=context.calendar_code,
            content_sha256=content_hash,
            backfill=_backfill_snapshot(backfill),
        )
        return FrozenDataset(bars=bars, manifest=manifest)


def _backfill_snapshot(value: dict[str, Any]) -> dict[str, Any]:
    allowed = {"inserted", "updated", "count", "source", "from_ts", "to_ts"}
    return {key: value[key] for key in allowed if key in value}


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


__all__ = ["FrozenBarsLoader"]
