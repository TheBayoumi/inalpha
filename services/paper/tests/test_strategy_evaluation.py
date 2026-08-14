"""临时源码评估成功路径。"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from inalpha_paper.engine.report import BacktestReport
from inalpha_paper.kernel.identifiers import InstrumentId
from inalpha_paper.model.data import Bar
from inalpha_paper.strategy_evaluation import evaluate_strategy_source

_SOURCE = """
class TestStrategy(Strategy):
    def __init__(self, name, clock, msgbus, instrument_id, timeframe="1h"):
        super().__init__(name, clock, msgbus)
        self._instrument_id = instrument_id

    def on_bar(self, bar):
        pass
"""


def _bars(count: int = 40) -> list[Bar]:
    instrument = InstrumentId(symbol="BTC/USDT", venue="binance")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    result: list[Bar] = []
    for index in range(count):
        price = 100.0 + index
        ts = int((start + timedelta(hours=index)).timestamp() * 1_000_000_000)
        result.append(
            Bar(
                instrument_id=instrument,
                timeframe="1h",
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=10.0,
                ts_event=ts,
                ts_init=ts,
            )
        )
    return result


def _report(bars: list[Bar]) -> BacktestReport:
    curve = [(bar.ts_event, 10_000.0 + index * 10.0) for index, bar in enumerate(bars)]
    return BacktestReport(
        initial_cash=10_000.0,
        final_equity=curve[-1][1],
        total_return_pct=(curve[-1][1] / curve[0][1] - 1.0) * 100.0,
        num_trades=6,
        total_fees=1.5,
        num_bars_processed=len(bars),
        period_start=datetime.fromtimestamp(bars[0].ts_event / 1e9, tz=UTC),
        period_end=datetime.fromtimestamp(bars[-1].ts_event / 1e9, tz=UTC),
        positions={},
        sharpe=1.2,
        sortino=1.5,
        max_drawdown_pct=2.0,
        equity_curve=curve,
    )


@pytest.mark.asyncio
async def test_source_evaluation_returns_json_snapshot() -> None:
    bars = _bars()
    calls: list[dict[str, Any]] = []

    async def run_engine(**kwargs: Any) -> BacktestReport:
        calls.append(kwargs)
        return _report(kwargs["bars"])

    result = await evaluate_strategy_source(
        source_code=_SOURCE,
        bars=bars,
        instrument_id=bars[0].instrument_id,
        timeframe="1h",
        run_engine=run_engine,
        annualization_periods=8760.0,
    )

    assert calls[0]["bars"] is bars
    assert calls[0]["candidate_code"] == _SOURCE
    assert result.snapshot.fitness > 0
    assert result.snapshot.validation is not None
    assert "equity_curve" not in result.snapshot.model_dump()
    json.dumps(result.snapshot.model_dump(mode="json"))
