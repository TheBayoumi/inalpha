"""Calendar-specific bar label generation."""
from __future__ import annotations

import math
from datetime import UTC, datetime

import pandas as pd  # type: ignore[import-untyped]

from .market_evaluation import MarketEvaluationContext, fixed_timeframe_seconds

_CLOSE_LABEL_CONNECTORS = {"akshare", "baostock"}


def calendar_bar_timestamps(
    calendar: object,
    schedule: pd.DataFrame,
    context: MarketEvaluationContext,
    now: datetime,
) -> list[datetime]:
    """Generate completed connector timestamps from a market schedule."""
    timeframe = context.canonical_timeframe
    if timeframe in {"1d", "1w", "1M"}:
        return _period_grid(calendar, schedule, context, now)
    seconds = fixed_timeframe_seconds(timeframe)
    assert seconds is not None
    return _intraday_grid(schedule, context.connector, seconds, now)


def _period_grid(
    calendar: object,
    schedule: pd.DataFrame,
    context: MarketEvaluationContext,
    now: datetime,
) -> list[datetime]:
    timeframe = context.canonical_timeframe
    if timeframe == "1d":
        keys = list(schedule.index)
    elif timeframe == "1w":
        keys = [(d.isocalendar().year, d.isocalendar().week) for d in schedule.index]
    else:
        keys = [(d.year, d.month) for d in schedule.index]
    groups = schedule.groupby(pd.Series(keys, index=schedule.index))
    values: list[datetime] = []
    for _key, rows in groups:
        if rows.iloc[-1]["close"] > pd.Timestamp(now):
            continue
        if context.connector in _CLOSE_LABEL_CONNECTORS:
            label = rows.index[-1]
            values.append(datetime(label.year, label.month, label.day, tzinfo=UTC))
            continue
        first = rows.index[0]
        if timeframe == "1w":
            first -= pd.Timedelta(days=first.weekday())
        elif timeframe == "1M":
            first = pd.Timestamp(first.year, first.month, 1)
        values.append(
            datetime(
                first.year,
                first.month,
                first.day,
                tzinfo=calendar.tz,  # type: ignore[attr-defined]
            ).astimezone(UTC)
        )
    return values


def _intraday_grid(
    schedule: pd.DataFrame,
    connector: str,
    seconds: int,
    now: datetime,
) -> list[datetime]:
    values: list[datetime] = []
    close_label = connector in _CLOSE_LABEL_CONNECTORS
    for _label, row in schedule.iterrows():
        segments = [(row["open"], row["close"])]
        if not pd.isna(row["break_start"]) and not pd.isna(row["break_end"]):
            segments = [
                (row["open"], row["break_start"]),
                (row["break_end"], row["close"]),
            ]
        for start, end in segments:
            count = math.ceil((end - start).total_seconds() / seconds)
            for index in range(count):
                opened = start + pd.Timedelta(seconds=index * seconds)
                closed = min(opened + pd.Timedelta(seconds=seconds), end)
                if closed <= pd.Timestamp(now):
                    values.append((closed if close_label else opened).to_pydatetime())
    return values


__all__ = ["calendar_bar_timestamps"]
