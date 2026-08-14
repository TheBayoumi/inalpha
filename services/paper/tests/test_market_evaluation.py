"""市场评估周期与年化契约测试。"""
from datetime import UTC, datetime

import pytest
from inalpha_shared.errors import ValidationError

from inalpha_paper.kernel.identifiers import InstrumentId
from inalpha_paper.market_evaluation import (
    build_market_evaluation_context,
    canonical_timeframe,
    fixed_timeframe_seconds,
)
from inalpha_paper.model.data import Bar
from inalpha_paper.runner import run_engine_in_subprocess

_AS_OF = datetime(2026, 8, 11, 12, tzinfo=UTC)


def test_crypto_uses_24_7_annualization_and_alias() -> None:
    context = build_market_evaluation_context(
        venue="binance",
        symbol="BTCUSDT",
        timeframe="1wk",
        as_of=_AS_OF,
    )
    assert context.canonical_timeframe == "1w"
    assert context.annualization_periods == 52
    assert context.calendar_code is None


def test_equity_uses_exchange_sessions() -> None:
    context = build_market_evaluation_context(
        venue="yfinance",
        symbol="AAPL",
        timeframe="1d",
        as_of=_AS_OF,
    )
    assert context.calendar_code == "XNYS"
    assert 245 <= context.annualization_periods <= 255
    assert context.annualization_periods != 365


def test_intraday_equity_uses_session_minutes() -> None:
    context = build_market_evaluation_context(
        venue="baostock",
        symbol="sh.600519",
        timeframe="1h",
        as_of=_AS_OF,
    )
    assert context.calendar_code == "XSHG"
    assert 900 <= context.annualization_periods <= 1100


def test_timeframe_helpers_are_explicit() -> None:
    assert canonical_timeframe("1mo") == "1M"
    assert fixed_timeframe_seconds("1wk") == 7 * 86_400
    assert fixed_timeframe_seconds("1mo") is None


@pytest.mark.parametrize(
    ("venue", "symbol", "code"),
    [
        ("fred", "GDP", "EVOLUTION_MARKET_UNSUPPORTED"),
        ("unknown", "ABC", "EVOLUTION_MARKET_CALENDAR_UNKNOWN"),
    ],
)
def test_non_tradable_or_unknown_market_fails_closed(
    venue: str,
    symbol: str,
    code: str,
) -> None:
    with pytest.raises(ValidationError) as error:
        build_market_evaluation_context(
            venue=venue,
            symbol=symbol,
            timeframe="1d",
            as_of=_AS_OF,
        )
    assert error.value.code == code


def test_engine_report_uses_explicit_annualization() -> None:
    instrument = InstrumentId(symbol="TEST", venue="yfinance")
    prices = [100.0, 102.0, 99.0, 104.0, 101.0]
    bars = [
        Bar(
            instrument_id=instrument,
            timeframe="1d",
            open=price,
            high=price + 1.0,
            low=price - 1.0,
            close=price,
            volume=100.0,
            ts_event=(index + 1) * 86_400_000_000_000,
            ts_init=(index + 1) * 86_400_000_000_000,
        )
        for index, price in enumerate(prices)
    ]
    common = {
        "bars": bars,
        "instrument_id": instrument,
        "timeframe": "1d",
        "strategy_id": "buy_and_hold",
        "params": {"trade_size": 1.0},
        "initial_cash": 10_000.0,
        "fee_rate": 0.0,
    }
    report_252 = run_engine_in_subprocess(**common, annualization_periods=252)
    report_365 = run_engine_in_subprocess(**common, annualization_periods=365)

    assert report_252.sharpe is not None
    assert report_365.sharpe is not None
    assert report_252.sharpe / report_365.sharpe == pytest.approx((252 / 365) ** 0.5)
