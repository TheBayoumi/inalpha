"""Derive completed bar timestamps from connector grids and calendars."""
from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import exchange_calendars as xcals  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]
from inalpha_shared.errors import ValidationError

from .market_evaluation import MarketEvaluationContext, fixed_timeframe_seconds
from .market_grid import calendar_bar_timestamps


def expected_latest_bar_open(
    context: MarketEvaluationContext,
    as_of: datetime,
) -> datetime:
    """Return the latest completed timestamp supplied by the connector."""
    now = _utc(as_of)
    if context.calendar_code is None:
        timeframe = context.canonical_timeframe
        if timeframe == "1M":
            current = datetime(now.year, now.month, 1, tzinfo=UTC)
            prior = current - timedelta(days=1)
            return datetime(prior.year, prior.month, 1, tzinfo=UTC)
        seconds = fixed_timeframe_seconds(timeframe)
        assert seconds is not None
        anchor = 4 * 86_400 if timeframe == "1w" else 0
        timestamp = (
            math.floor((now.timestamp() - anchor) / seconds) * seconds
            + anchor
            - seconds
        )
        return datetime.fromtimestamp(timestamp, tz=UTC)
    values = expected_bar_timestamps(context, now - timedelta(days=100), now)
    if not values:
        raise ValidationError(
            "market calendar has no completed bar before as_of",
            code="EVOLUTION_NO_CLOSED_BARS",
        )
    return values[-1]


def expected_bar_timestamps(
    context: MarketEvaluationContext,
    start: datetime,
    as_of: datetime,
) -> tuple[datetime, ...]:
    """Return completed connector timestamps within the requested interval."""
    begin, now = _utc(start), _utc(as_of)
    if context.calendar_code is None:
        return _continuous_grid(context.canonical_timeframe, begin, now)
    timeframe = context.canonical_timeframe
    if timeframe == "3d":
        raise ValidationError(
            "unsupported calendar timeframe: 3d",
            code="EVOLUTION_TIMEFRAME_UNSUPPORTED",
        )
    calendar = xcals.get_calendar(context.calendar_code)
    end = pd.Timestamp(now.date()) + pd.offsets.MonthEnd(1) + pd.Timedelta(days=7)
    schedule = calendar.schedule.loc[
        str((begin - timedelta(days=35)).date()) : str(end.date())
    ]
    values = calendar_bar_timestamps(calendar, schedule, context, now)
    return tuple(value for value in values if begin <= value <= now)


def _continuous_grid(
    timeframe: str,
    start: datetime,
    now: datetime,
) -> tuple[datetime, ...]:
    if timeframe == "1M":
        cursor = datetime(start.year, start.month, 1, tzinfo=UTC)
        values: list[datetime] = []
        while True:
            following = (pd.Timestamp(cursor) + pd.DateOffset(months=1)).to_pydatetime()
            if following > now:
                break
            if cursor >= start:
                values.append(cursor)
            cursor = following
        return tuple(values)
    seconds = fixed_timeframe_seconds(timeframe)
    assert seconds is not None
    anchor = 4 * 86_400 if timeframe == "1w" else 0
    first = math.ceil((start.timestamp() - anchor) / seconds) * seconds + anchor
    last = math.floor((now.timestamp() - anchor) / seconds) * seconds + anchor - seconds
    return tuple(
        datetime.fromtimestamp(timestamp, tz=UTC)
        for timestamp in range(int(first), int(last) + 1, seconds)
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = ["expected_bar_timestamps", "expected_latest_bar_open"]
