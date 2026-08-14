"""一次性回测子进程执行器测试。"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from inalpha_paper.evaluation_executor import KillableEngineRunner
from inalpha_paper.kernel.identifiers import InstrumentId
from inalpha_paper.model.data import Bar
from inalpha_paper.strategy_evaluation import evaluate_buy_and_hold


def _bars() -> list[Bar]:
    instrument = InstrumentId(symbol="BTCUSDT", venue="binance")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    result: list[Bar] = []
    for index in range(20):
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


@pytest.mark.asyncio
async def test_killable_runner_keeps_event_loop_responsive() -> None:
    bars = _bars()
    runner = KillableEngineRunner(timeout_s=10.0, mem_gb=2.0)
    task = asyncio.create_task(
        evaluate_buy_and_hold(
            bars=bars,
            instrument_id=bars[0].instrument_id,
            timeframe="1h",
            run_engine=runner,
        )
    )
    ticks = 0
    while not task.done():
        ticks += 1
        await asyncio.sleep(0.01)
    result = await task

    assert ticks > 0
    assert result.snapshot.num_bars == len(bars)


@pytest.mark.asyncio
async def test_killable_runner_enforces_wall_timeout() -> None:
    bars = _bars()
    runner = KillableEngineRunner(timeout_s=0.001, mem_gb=2.0)

    with pytest.raises(TimeoutError):
        await evaluate_buy_and_hold(
            bars=bars,
            instrument_id=bars[0].instrument_id,
            timeframe="1h",
            run_engine=runner,
        )
