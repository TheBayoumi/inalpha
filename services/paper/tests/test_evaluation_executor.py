"""一次性回测子进程执行器测试。"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from itertools import pairwise

import pytest

from inalpha_paper.evaluation_executor import KillableEngineRunner, WorkerExecutionError
from inalpha_paper.kernel.identifiers import InstrumentId
from inalpha_paper.model.data import Bar
from inalpha_paper.strategy_evaluation import evaluate_buy_and_hold, evaluate_strategy_source

_BAD_CONTRACT_SOURCE = """
class TestStrategy(Strategy):
    pass
"""

_HANGING_CLASS_SOURCE = """
class TestStrategy(Strategy):
    while True:
        pass
"""


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
    loop = asyncio.get_running_loop()
    tick_times = [loop.time()]
    while not task.done():
        await asyncio.sleep(0.01)
        tick_times.append(loop.time())
    result = await task
    gaps = [right - left for left, right in pairwise(tick_times)]

    assert gaps
    assert max(gaps) < 0.5
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


@pytest.mark.asyncio
async def test_contract_check_runs_inside_worker() -> None:
    bars = _bars()
    runner = KillableEngineRunner(timeout_s=5.0, mem_gb=2.0)

    with pytest.raises(WorkerExecutionError) as error:
        await evaluate_strategy_source(
            source_code=_BAD_CONTRACT_SOURCE,
            bars=bars,
            instrument_id=bars[0].instrument_id,
            timeframe="1h",
            run_engine=runner,
        )

    assert error.value.code == "CANDIDATE_CONTRACT_FAILED"


@pytest.mark.asyncio
async def test_class_body_hang_is_killed_by_worker_timeout() -> None:
    bars = _bars()
    runner = KillableEngineRunner(timeout_s=0.2, mem_gb=2.0)

    with pytest.raises(TimeoutError):
        await evaluate_strategy_source(
            source_code=_HANGING_CLASS_SOURCE,
            bars=bars,
            instrument_id=bars[0].instrument_id,
            timeframe="1h",
            run_engine=runner,
        )
