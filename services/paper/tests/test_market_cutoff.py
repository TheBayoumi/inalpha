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
        2026, 8, 11, 4, tzinfo=UTC
    )

    after_close = datetime(2026, 8, 12, 21, tzinfo=UTC)
    assert expected_latest_bar_open(context, after_close) == datetime(
        2026, 8, 12, 4, tzinfo=UTC
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
        2026, 8, 12, 3, 30, tzinfo=UTC
    )


def test_us_hourly_grid_keeps_regular_and_half_day_short_tail() -> None:
    regular = datetime(2026, 8, 12, 20, 1, tzinfo=UTC)
    context = _context("yfinance", "AAPL", "1h", regular)
    assert expected_latest_bar_open(context, regular) == datetime(
        2026, 8, 12, 19, 30, tzinfo=UTC
    )

    half_day = datetime(2026, 11, 27, 18, 1, tzinfo=UTC)
    context = _context("yfinance", "AAPL", "1h", half_day)
    assert expected_latest_bar_open(context, half_day) == datetime(
        2026, 11, 27, 17, 30, tzinfo=UTC
    )


def test_us_hourly_grid_tracks_dst() -> None:
    before = datetime(2026, 3, 6, 15, 31, tzinfo=UTC)
    after = datetime(2026, 3, 9, 14, 31, tzinfo=UTC)
    context = _context("yfinance", "AAPL", "1h", before)
    assert expected_latest_bar_open(context, before).hour == 14
    assert expected_latest_bar_open(context, after).hour == 13


def test_break_markets_restart_grid_after_lunch() -> None:
    hong_kong = datetime(2026, 8, 12, 6, 1, tzinfo=UTC)
    hk_context = _context("yfinance", "0700.HK", "1h", hong_kong)
    assert expected_latest_bar_open(hk_context, hong_kong) == datetime(
        2026, 8, 12, 5, tzinfo=UTC
    )

    tokyo = datetime(2026, 8, 12, 4, 31, tzinfo=UTC)
    jp_context = _context("yfinance", "7203.T", "1h", tokyo)
    assert expected_latest_bar_open(jp_context, tokyo) == datetime(
        2026, 8, 12, 3, 30, tzinfo=UTC
    )


def test_week_and_month_wait_for_actual_last_session_close() -> None:
    before_week_close = datetime(2026, 8, 14, 6, 59, tzinfo=UTC)
    after_week_close = datetime(2026, 8, 14, 7, 1, tzinfo=UTC)
    weekly = _context("baostock", "sh.600519", "1wk", before_week_close)
    assert expected_latest_bar_open(weekly, before_week_close) == datetime(
        2026, 8, 7, tzinfo=UTC
    )
    assert expected_latest_bar_open(weekly, after_week_close) == datetime(
        2026, 8, 14, tzinfo=UTC
    )

    before_month_close = datetime(2026, 8, 31, 6, 59, tzinfo=UTC)
    after_month_close = datetime(2026, 8, 31, 7, 1, tzinfo=UTC)
    monthly = _context("baostock", "sh.600519", "1mo", before_month_close)
    assert expected_latest_bar_open(monthly, before_month_close) == datetime(
        2026, 7, 31, tzinfo=UTC
    )
    assert expected_latest_bar_open(monthly, after_month_close) == datetime(
        2026, 8, 31, tzinfo=UTC
    )
