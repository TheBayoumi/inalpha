"""冻结 bars 的关闭、质量与内容哈希校验。"""
from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
from inalpha_paper.bar_conversion import bar_from_dict
from inalpha_paper.kernel.identifiers import InstrumentId
from inalpha_paper.market_cutoff import expected_latest_bar_open
from inalpha_paper.market_evaluation import (
    MarketEvaluationContext,
    fixed_timeframe_seconds,
)
from inalpha_paper.model.data import Bar
from inalpha_shared.errors import ValidationError

from .bar_hash import bars_content_hash


def prepare_frozen_bars(
    raw_bars: list[dict[str, Any]],
    *,
    instrument_id: InstrumentId,
    context: MarketEvaluationContext,
    as_of: datetime,
) -> tuple[tuple[Bar, ...], str, float]:
    """过滤 forming bars，严格校验并返回稳定 hash。"""
    now = _utc(as_of)
    bars: list[Bar] = []
    previous_ts = -1
    for raw in raw_bars:
        _validate_identity(raw, instrument_id, context.data_timeframe)
        bar = bar_from_dict(raw, instrument_id, context.canonical_timeframe)
        if not _is_closed(bar.ts_event, context.canonical_timeframe, now):
            continue
        if bar.ts_event <= previous_ts:
            raise ValidationError(
                "bars must be strictly increasing without duplicates",
                code="EVOLUTION_DATA_ORDER_INVALID",
            )
        _validate_values(bar)
        bars.append(bar)
        previous_ts = bar.ts_event
    if len(bars) < 2:
        raise ValidationError(
            f"evolution needs at least 2 closed bars, got {len(bars)}",
            code="EVOLUTION_NO_CLOSED_BARS",
        )

    expected = expected_latest_bar_open(context, now)
    latest = datetime.fromtimestamp(bars[-1].ts_event / 1_000_000_000, tz=UTC)
    lag = max(0.0, (expected - latest).total_seconds())
    if lag > 0:
        raise ValidationError(
            f"latest closed bar is {lag:.0f}s behind expected cutoff",
            code="EVOLUTION_DATA_FRESHNESS_FAILED",
            details={"latest_bar_ts": latest.isoformat(), "expected": expected.isoformat()},
        )
    return tuple(bars), bars_content_hash(bars, instrument_id, context), lag


def _validate_identity(
    raw: dict[str, Any],
    instrument: InstrumentId,
    timeframe: str,
) -> None:
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


def _validate_values(bar: Bar) -> None:
    values = (bar.open, bar.high, bar.low, bar.close, bar.volume)
    if not all(math.isfinite(value) for value in values):
        raise ValidationError("bar contains non-finite value", code="EVOLUTION_DATA_INVALID")
    if min(bar.open, bar.high, bar.low, bar.close) <= 0 or bar.volume < 0:
        raise ValidationError("bar price/volume is invalid", code="EVOLUTION_DATA_INVALID")
    if bar.low > min(bar.open, bar.close) or bar.high < max(bar.open, bar.close):
        raise ValidationError("bar OHLC relation is invalid", code="EVOLUTION_DATA_INVALID")


def _is_closed(ts_ns: int, timeframe: str, as_of: datetime) -> bool:
    opened = datetime.fromtimestamp(ts_ns / 1_000_000_000, tz=UTC)
    seconds = fixed_timeframe_seconds(timeframe)
    if seconds is not None:
        return opened.timestamp() + seconds <= as_of.timestamp()
    return pd.Timestamp(opened) + pd.DateOffset(months=1) <= pd.Timestamp(as_of)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
