"""严格冻结行情加载器测试。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from inalpha_shared.errors import ValidationError

from inalpha_evolver.data.frozen_bars import FrozenBarsLoader

_AS_OF = datetime(2026, 8, 12, 12, tzinfo=UTC)


class FakeDataClient:
    def __init__(
        self,
        bars: list[dict[str, Any]],
        *,
        backfill_error: Exception | None = None,
    ) -> None:
        self.bars = bars
        self.backfill_error = backfill_error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def backfill_bars(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("backfill", kwargs))
        if self.backfill_error:
            raise self.backfill_error
        return {"count": len(self.bars), "source": "test"}

    async def get_bars(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append(("get", kwargs))
        return self.bars


def _hourly_bars(count: int = 3, *, end: datetime = _AS_OF) -> list[dict[str, Any]]:
    start = end - timedelta(hours=count)
    return [
        {
            "venue": "binance",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "ts": (start + timedelta(hours=index)).isoformat(),
            "open": 100.0 + index,
            "high": 101.0 + index,
            "low": 99.0 + index,
            "close": 100.5 + index,
            "volume": 10.0,
        }
        for index in range(count)
    ]


@pytest.mark.asyncio
async def test_load_backfills_then_reads_without_fresh_fallback() -> None:
    client = FakeDataClient(_hourly_bars())
    dataset = await FrozenBarsLoader(client).load(  # type: ignore[arg-type]
        venue="binance",
        symbol="BTCUSDT",
        timeframe="1h",
        from_ts=_AS_OF - timedelta(days=1),
        as_of=_AS_OF,
    )

    assert [call[0] for call in client.calls] == ["backfill", "get"]
    assert client.calls[1][1]["fresh"] is False
    assert client.calls[1][1]["limit"] == 10_001
    assert dataset.manifest.bar_count == 3
    assert dataset.manifest.latest_bar_ts == _AS_OF - timedelta(hours=1)
    assert len(dataset.manifest.content_sha256) == 64


@pytest.mark.asyncio
async def test_forming_bar_is_removed() -> None:
    bars = _hourly_bars()
    bars.append({**bars[-1], "ts": _AS_OF.isoformat()})
    client = FakeDataClient(bars)
    dataset = await FrozenBarsLoader(client).load(  # type: ignore[arg-type]
        venue="binance",
        symbol="BTCUSDT",
        timeframe="1h",
        from_ts=_AS_OF - timedelta(days=1),
        as_of=_AS_OF,
    )
    assert dataset.manifest.bar_count == 3


@pytest.mark.asyncio
async def test_stale_tail_fails_closed() -> None:
    client = FakeDataClient(_hourly_bars(end=_AS_OF - timedelta(hours=1)))
    with pytest.raises(ValidationError) as error:
        await FrozenBarsLoader(client).load(  # type: ignore[arg-type]
            venue="binance",
            symbol="BTCUSDT",
            timeframe="1h",
            from_ts=_AS_OF - timedelta(days=1),
            as_of=_AS_OF,
        )
    assert error.value.code == "EVOLUTION_DATA_FRESHNESS_FAILED"


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["duplicate", "nan", "bad_ohlc"])
async def test_bad_bars_fail_closed(mutation: str) -> None:
    bars = _hourly_bars()
    if mutation == "duplicate":
        bars[1]["ts"] = bars[0]["ts"]
    elif mutation == "nan":
        bars[1]["close"] = float("nan")
    else:
        bars[1]["high"] = 50.0
    client = FakeDataClient(bars)
    with pytest.raises(ValidationError):
        await FrozenBarsLoader(client).load(  # type: ignore[arg-type]
            venue="binance",
            symbol="BTCUSDT",
            timeframe="1h",
            from_ts=_AS_OF - timedelta(days=1),
            as_of=_AS_OF,
        )
