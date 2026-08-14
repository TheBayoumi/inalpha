"""按市场日历推导最近应存在的已收盘 bar。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import exchange_calendars as xcals  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]
from inalpha_shared.errors import ValidationError

from .market_evaluation import MarketEvaluationContext, fixed_timeframe_seconds


def expected_latest_bar_open(
    context: MarketEvaluationContext,
    as_of: datetime,
) -> datetime:
    """返回 ``as_of`` 时最近应存在的已收盘 bar 开始时间。"""
    now = _utc(as_of)
    seconds = fixed_timeframe_seconds(context.canonical_timeframe)
    if context.calendar_code is None:
        if seconds is None:
            current_month = datetime(now.year, now.month, 1, tzinfo=UTC)
            previous = current_month - timedelta(days=1)
            return datetime(previous.year, previous.month, 1, tzinfo=UTC)
        epoch = int(now.timestamp())
        return datetime.fromtimestamp((epoch // seconds - 1) * seconds, tz=UTC)

    calendar = xcals.get_calendar(context.calendar_code)
    schedule = calendar.schedule.loc[: str(now.date())]
    timeframe = context.canonical_timeframe
    if timeframe == "1d":
        completed = schedule[schedule["close"] <= pd.Timestamp(now)]
        return _session_label(completed.index[-1])
    if timeframe == "1w":
        week_start = pd.Timestamp(now.date()) - pd.Timedelta(days=now.weekday())
        prior = schedule[schedule.index < week_start]
        label = prior.index[-1]
        monday = label - pd.Timedelta(days=label.weekday())
        return _session_label(monday)
    if timeframe == "1M":
        month_start = pd.Timestamp(now.year, now.month, 1)
        prior = schedule[schedule.index < month_start]
        label = prior.index[-1]
        return datetime(label.year, label.month, 1, tzinfo=UTC)
    if timeframe == "3d" or seconds is None:
        raise ValidationError(
            f"unsupported calendar timeframe: {timeframe}",
            code="EVOLUTION_TIMEFRAME_UNSUPPORTED",
        )
    return _latest_intraday_open(schedule, pd.Timestamp(now), seconds)


def _latest_intraday_open(
    schedule: pd.DataFrame,
    now: pd.Timestamp,
    seconds: int,
) -> datetime:
    for _label, row in schedule.iloc[::-1].iterrows():
        if pd.isna(row["break_start"]) or pd.isna(row["break_end"]):
            segments = [(row["open"], row["close"])]
        else:
            segments = [
                (row["open"], row["break_start"]),
                (row["break_end"], row["close"]),
            ]
        for start, end in reversed(segments):
            if pd.isna(start) or pd.isna(end) or now <= start:
                continue
            cutoff = min(now, end)
            complete = int((cutoff - start).total_seconds() // seconds)
            if complete > 0:
                return (start + pd.Timedelta(seconds=(complete - 1) * seconds)).to_pydatetime()
    raise ValidationError(
        "market calendar has no completed bar before as_of",
        code="EVOLUTION_NO_CLOSED_BARS",
    )


def _session_label(value: object) -> datetime:
    timestamp = pd.Timestamp(value)
    timestamp = timestamp.tz_localize("UTC") if timestamp.tz is None else timestamp.tz_convert("UTC")
    return timestamp.to_pydatetime()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


__all__ = ["expected_latest_bar_open"]
