"""Annualization derived from the generated exchange-calendar grid."""
from __future__ import annotations

import math
from datetime import datetime

import exchange_calendars as xcals  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]
from inalpha_shared.errors import ValidationError

_MINUTES = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "2h": 120,
    "4h": 240,
    "6h": 360,
    "8h": 480,
    "12h": 720,
}


def calendar_periods(code: str, timeframe: str, as_of: datetime) -> int:
    """Count actual generated bars per year for an exchange calendar."""
    calendar = xcals.get_calendar(code)
    end = pd.Timestamp(as_of)
    end = end.tz_localize("UTC") if end.tz is None else end.tz_convert("UTC")
    start = max(end - pd.DateOffset(years=3), calendar.first_session.tz_localize("UTC"))
    schedule = calendar.schedule.loc[str(start.date()) : str(end.date())]
    if schedule.empty:
        raise ValidationError(
            f"calendar {code} has no sessions near {end.isoformat()}",
            code="EVOLUTION_MARKET_CALENDAR_EMPTY",
        )
    years = max((end - start).total_seconds() / (365.2425 * 86_400), 1.0)
    if timeframe == "1d":
        count = len(schedule)
    elif timeframe == "3d":
        count = math.ceil(len(schedule) / 3)
    elif timeframe == "1w":
        count = len(
            {(day.isocalendar().year, day.isocalendar().week) for day in schedule.index}
        )
    elif timeframe == "1M":
        count = len({(day.year, day.month) for day in schedule.index})
    else:
        seconds = _MINUTES[timeframe] * 60
        count = sum(_session_count(row, seconds) for _, row in schedule.iterrows())
    return max(1, round(count / years))


def _session_count(row: pd.Series, seconds: int) -> int:
    segments = [(row["open"], row["close"])]
    if not pd.isna(row["break_start"]) and not pd.isna(row["break_end"]):
        segments = [
            (row["open"], row["break_start"]),
            (row["break_end"], row["close"]),
        ]
    return sum(
        math.ceil((end - start).total_seconds() / seconds)
        for start, end in segments
        if end > start
    )


__all__ = ["calendar_periods"]
