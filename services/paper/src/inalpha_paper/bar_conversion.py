"""data-service bar 响应到 paper 内核模型的转换。"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .kernel.clock import datetime_to_ns
from .kernel.identifiers import InstrumentId
from .model.data import Bar


def bar_from_dict(
    data: dict[str, Any],
    instrument_id: InstrumentId,
    timeframe: str,
) -> Bar:
    """把 data-service ``BarResponse`` 转成内核 ``Bar``。"""
    raw_ts = data["ts"]
    timestamp = (
        datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        if isinstance(raw_ts, str)
        else raw_ts
    )
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    ts_ns = datetime_to_ns(timestamp)
    return Bar(
        instrument_id=instrument_id,
        timeframe=timeframe,
        open=float(data["open"]),
        high=float(data["high"]),
        low=float(data["low"]),
        close=float(data["close"]),
        volume=float(data["volume"]),
        ts_event=ts_ns,
        ts_init=ts_ns,
    )


__all__ = ["bar_from_dict"]
