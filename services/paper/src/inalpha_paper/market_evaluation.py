from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import exchange_calendars as xcals  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]
from inalpha_shared.errors import ValidationError

from .engine.metrics import periods_per_year
from .execution.risk_rules.exchange_resolver import (
    is_crypto_venue,
    resolve_calendar_code,
)

_ALIASES = {"1wk": "1w", "1mo": "1M"}
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
_DAYS = {"1d": 1, "3d": 3}


@dataclass(frozen=True, slots=True)
class MarketEvaluationContext:
    requested_timeframe: str
    data_timeframe: str
    canonical_timeframe: str
    annualization_periods: int
    calendar_code: str | None


def build_market_evaluation_context(
    *,
    venue: str,
    symbol: str,
    timeframe: str,
    as_of: datetime,
) -> MarketEvaluationContext:
    canonical = _ALIASES.get(timeframe, timeframe)
    try:
        crypto_periods = periods_per_year(canonical)
    except ValueError as exc:
        raise ValidationError(
            f"unsupported evaluation timeframe: {timeframe}",
            code="EVOLUTION_TIMEFRAME_UNSUPPORTED",
        ) from exc
    if is_crypto_venue(venue):
        return MarketEvaluationContext(
            timeframe,
            timeframe,
            canonical,
            crypto_periods,
            None,
        )
    if venue.strip().lower() == "fred":
        raise ValidationError(
            "FRED series are not tradable evolution instruments",
            code="EVOLUTION_MARKET_UNSUPPORTED",
        )
    calendar_code = resolve_calendar_code(venue, symbol)
    if calendar_code is None:
        raise ValidationError(
            f"cannot resolve market calendar for {symbol}@{venue}",
            code="EVOLUTION_MARKET_CALENDAR_UNKNOWN",
        )
    annualization = _calendar_periods(calendar_code, canonical, as_of)
    return MarketEvaluationContext(
        timeframe,
        timeframe,
        canonical,
        annualization,
        calendar_code,
    )


def canonical_timeframe(timeframe: str) -> str:
    return _ALIASES.get(timeframe, timeframe)


def fixed_timeframe_seconds(timeframe: str) -> int | None:
    canonical = canonical_timeframe(timeframe)
    if canonical in _MINUTES:
        return _MINUTES[canonical] * 60
    if canonical in _DAYS:
        return _DAYS[canonical] * 86_400
    if canonical == "1w":
        return 7 * 86_400
    if canonical == "1M":
        return None
    raise ValidationError(
        f"unsupported evaluation timeframe: {timeframe}",
        code="EVOLUTION_TIMEFRAME_UNSUPPORTED",
    )


def _calendar_periods(code: str, timeframe: str, as_of: datetime) -> int:
    if timeframe == "1w":
        return 52
    if timeframe == "1M":
        return 12
    calendar = xcals.get_calendar(code)
    end = pd.Timestamp(as_of)
    end = end.tz_localize("UTC") if end.tz is None else end.tz_convert("UTC")
    start = max(
        end - pd.DateOffset(years=3), calendar.first_session.tz_localize("UTC")
    )
    schedule = calendar.schedule.loc[str(start.date()) : str(end.date())]
    if schedule.empty:
        raise ValidationError(
            f"calendar {code} has no sessions near {as_of.astimezone(UTC).isoformat()}",
            code="EVOLUTION_MARKET_CALENDAR_EMPTY",
        )
    span_years = max((end - start).total_seconds() / (365.2425 * 86_400), 1.0)
    if timeframe in _DAYS:
        return max(1, round(len(schedule) / span_years / _DAYS[timeframe]))
    minutes = _MINUTES[timeframe]
    duration = (schedule["close"] - schedule["open"]).dt.total_seconds() / 60
    breaks = (schedule["break_end"] - schedule["break_start"]).dt.total_seconds() / 60
    tradable = duration - breaks.fillna(0.0)
    return max(1, round((tradable / minutes).sum() / span_years))
