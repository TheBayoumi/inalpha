"""冻结数据集 evaluator 测试。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from inalpha_paper.engine.report import BacktestReport
from inalpha_paper.kernel.identifiers import InstrumentId
from inalpha_paper.model.data import Bar

from inalpha_evolver.data.manifest import DatasetManifest, FrozenDataset
from inalpha_evolver.evaluator.frozen import FrozenDatasetEvaluator


def _dataset() -> FrozenDataset:
    instrument = InstrumentId(symbol="BTCUSDT", venue="binance")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars = tuple(
        Bar(
            instrument_id=instrument,
            timeframe="1h",
            open=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            close=100.5 + index,
            volume=10.0,
            ts_event=int((start + timedelta(hours=index)).timestamp() * 1e9),
            ts_init=int((start + timedelta(hours=index)).timestamp() * 1e9),
        )
        for index in range(40)
    )
    manifest = DatasetManifest(
        venue="binance",
        symbol="BTCUSDT",
        requested_timeframe="1h",
        data_timeframe="1h",
        canonical_timeframe="1h",
        requested_from=start,
        requested_as_of=start + timedelta(hours=41),
        effective_from=start,
        effective_to=start + timedelta(hours=39),
        latest_bar_ts=start + timedelta(hours=39),
        bar_count=40,
        freshness_lag_seconds=0,
        annualization_periods=8760,
        calendar_code=None,
        content_sha256="a" * 64,
        backfill={"count": 40},
    )
    return FrozenDataset(bars=bars, manifest=manifest)


class FakeRunner:
    async def __call__(self, **kwargs: Any) -> BacktestReport:
        bars = kwargs["bars"]
        curve = [(bar.ts_event, 10_000.0 + index) for index, bar in enumerate(bars)]
        return BacktestReport(
            initial_cash=10_000.0,
            final_equity=curve[-1][1],
            total_return_pct=0.39,
            num_trades=6,
            total_fees=1.0,
            num_bars_processed=len(bars),
            period_start=_dataset().manifest.effective_from,
            period_end=_dataset().manifest.effective_to,
            positions={},
            sharpe=1.0,
            max_drawdown_pct=2.0,
            equity_curve=curve,
        )


@pytest.mark.asyncio
async def test_frozen_evaluator_uses_manifest_epoch_and_snapshot() -> None:
    evaluator = FrozenDatasetEvaluator(
        dataset=_dataset(),
        runner=FakeRunner(),  # type: ignore[arg-type]
    )
    source = """
class TestStrategy(Strategy):
    def __init__(self, name, clock, msgbus, instrument_id, timeframe="1h"):
        super().__init__(name, clock, msgbus)
    def on_bar(self, bar):
        pass
"""
    result = await evaluator.evaluate(source)

    assert result.data_epoch == int(_dataset().manifest.latest_bar_ts.timestamp() * 1000)
    assert result.report["schema_version"] == "e1.report.v1"
    assert "equity_curve" not in result.report
    assert result.fitness == result.report["fitness"]


@pytest.mark.asyncio
async def test_frozen_evaluator_builds_baseline_snapshot() -> None:
    evaluator = FrozenDatasetEvaluator(
        dataset=_dataset(),
        runner=FakeRunner(),  # type: ignore[arg-type]
    )
    snapshot = await evaluator.evaluate_baseline()

    assert snapshot["schema_version"] == "e1.report.v1"
    assert snapshot["annualization_periods"] == 8760.0
    assert "equity_curve" not in snapshot
