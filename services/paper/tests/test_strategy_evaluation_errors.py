"""临时源码评估拒绝路径。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from inalpha_shared.errors import ValidationError

from inalpha_paper.engine.report import BacktestReport
from inalpha_paper.kernel.identifiers import InstrumentId
from inalpha_paper.model.data import Bar
from inalpha_paper.strategy_evaluation import (
    evaluate_buy_and_hold,
    evaluate_strategy_source,
)

_SOURCE = """
class TestStrategy(Strategy):
    def __init__(self, name, clock, msgbus, instrument_id, timeframe="1h"):
        super().__init__(name, clock, msgbus)

    def on_bar(self, bar):
        pass
"""


def _bars(count: int = 2, *, second_open: float = 101.0) -> list[Bar]:
    instrument = InstrumentId(symbol="BTC/USDT", venue="binance")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    result: list[Bar] = []
    for index in range(count):
        price = second_open if index == 1 else 100.0
        ts = int((start + timedelta(hours=index)).timestamp() * 1_000_000_000)
        result.append(
            Bar(
                instrument_id=instrument,
                timeframe="1h",
                open=price,
                high=max(price, 101.0),
                low=min(price, 99.0),
                close=100.0,
                volume=10.0,
                ts_event=ts,
                ts_init=ts,
            )
        )
    return result


async def _unreachable(**_kwargs: Any) -> BacktestReport:
    raise AssertionError("unreachable")


@pytest.mark.asyncio
async def test_invalid_source_is_rejected_before_engine() -> None:
    bars = _bars()
    with pytest.raises(ValidationError) as error:
        await evaluate_strategy_source(
            source_code="import os",
            bars=bars,
            instrument_id=bars[0].instrument_id,
            timeframe="1h",
            run_engine=_unreachable,
        )
    assert error.value.code == "CANDIDATE_REAUDIT_FAILED"


@pytest.mark.asyncio
async def test_baseline_validates_price_before_engine() -> None:
    bars = _bars(second_open=0.0)
    with pytest.raises(ValidationError) as error:
        await evaluate_buy_and_hold(
            bars=bars,
            instrument_id=bars[0].instrument_id,
            timeframe="1h",
            run_engine=_unreachable,
        )
    assert error.value.code == "INVALID_BAR_PRICE"


@pytest.mark.asyncio
async def test_evaluation_requires_two_bars() -> None:
    bars = _bars(1)
    with pytest.raises(ValidationError) as error:
        await evaluate_strategy_source(
            source_code=_SOURCE,
            bars=bars,
            instrument_id=bars[0].instrument_id,
            timeframe="1h",
            run_engine=_unreachable,
        )
    assert error.value.code == "NO_BARS_AVAILABLE"
