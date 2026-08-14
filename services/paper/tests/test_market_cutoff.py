"""市场已收盘 cutoff 边界测试。"""
from datetime import UTC, datetime

from inalpha_paper.market_cutoff import expected_latest_bar_open
from inalpha_paper.market_evaluation import build_market_evaluation_context


def _context(venue: str, symbol: str, timeframe: str, as_of: datetime):
    return build_market_evaluation_context(
        venue=venue,
        symbol=symbol,
        timeframe=timeframe,
        as_of=as_of,
    )


def test_crypto_cutoff_excludes_current_hour() -> None:
    as_of = datetime(2026, 8, 12, 12, 34, tzinfo=UTC)
    context = _context("binance", "BTCUSDT", "1h", as_of)
    assert expected_latest_bar_open(context, as_of) == datetime(
        2026, 8, 12, 11, tzinfo=UTC
    )


def test_equity_daily_waits_for_session_close() -> None:
    intraday = datetime(2026, 8, 12, 18, tzinfo=UTC)
    context = _context("yfinance", "AAPL", "1d", intraday)
    assert expected_latest_bar_open(context, intraday) == datetime(
        2026, 8, 11, tzinfo=UTC
    )

    after_close = datetime(2026, 8, 12, 21, tzinfo=UTC)
    assert expected_latest_bar_open(context, after_close) == datetime(
        2026, 8, 12, tzinfo=UTC
    )


def test_equity_intraday_excludes_forming_interval() -> None:
    as_of = datetime(2026, 8, 12, 15, 45, tzinfo=UTC)
    context = _context("yfinance", "AAPL", "1h", as_of)
    assert expected_latest_bar_open(context, as_of) == datetime(
        2026, 8, 12, 14, 30, tzinfo=UTC
    )


def test_a_share_intraday_respects_lunch_break() -> None:
    as_of = datetime(2026, 8, 12, 5, 15, tzinfo=UTC)
    context = _context("baostock", "sh.600519", "1h", as_of)
    assert expected_latest_bar_open(context, as_of) == datetime(
        2026, 8, 12, 2, 30, tzinfo=UTC
    )
