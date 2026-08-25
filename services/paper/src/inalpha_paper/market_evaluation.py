from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from inalpha_shared.errors import ValidationError

from .engine.metrics import periods_per_year
from .execution.risk_rules.exchange_resolver import is_crypto_venue, resolve_calendar_code
from .market_annualization import calendar_periods

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
    connector: str


def build_market_evaluation_context(
    *,
    venue: str,
    symbol: str,
    timeframe: str,
    as_of: datetime,
) -> MarketEvaluationContext:
    canonical = canonical_timeframe(timeframe)
    try:
        crypto_periods = periods_per_year(canonical)
    except ValueError as exc:
        raise ValidationError(
            f"unsupported evaluation timeframe: {timeframe}",
            code="EVOLUTION_TIMEFRAME_UNSUPPORTED",
        ) from exc
    connector = venue.strip().lower()
    if is_crypto_venue(venue):
        return MarketEvaluationContext(
            timeframe, timeframe, canonical, crypto_periods, None, connector
        )
    if connector == "fred":
        raise ValidationError(
            "FRED series are not tradable evolution instruments",
            code="EVOLUTION_MARKET_UNSUPPORTED",
        )
    code = resolve_calendar_code(venue, symbol)
    if code is None:
        raise ValidationError(
            f"cannot resolve market calendar for {symbol}@{venue}",
            code="EVOLUTION_MARKET_CALENDAR_UNKNOWN",
        )
    return MarketEvaluationContext(
        timeframe,
        timeframe,
        canonical,
        calendar_periods(code, canonical, as_of),
        code,
        connector,
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
