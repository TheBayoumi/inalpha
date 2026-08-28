"""Point-in-time event ordering and conservative execution regression tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from inalpha_paper.engine.backtest import BacktestEngine
from inalpha_paper.execution.exchange import EventExecutionPolicy
from inalpha_paper.kernel.identifiers import ClientOrderId, InstrumentId
from inalpha_paper.model.data import Bar
from inalpha_paper.model.market_events import MarketEvent
from inalpha_paper.model.orders import Order, OrderSide, OrderType
from inalpha_paper.strategy.base import Strategy


def _bars() -> list[Bar]:
    instrument = InstrumentId(symbol="BTC/USDT", venue="binance")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        Bar(
            instrument_id=instrument,
            timeframe="1h",
            open=100 + index,
            high=101 + index,
            low=99 + index,
            close=100 + index,
            volume=1_000,
            ts_open=int((start + timedelta(hours=index)).timestamp() * 1e9),
            ts_event=int((start + timedelta(hours=index + 1)).timestamp() * 1e9),
            ts_init=int((start + timedelta(hours=index + 1)).timestamp() * 1e9),
        )
        for index in range(5)
    ]


class EventRecorder(Strategy):
    def __init__(self, *args: object, instrument_id: InstrumentId) -> None:
        super().__init__(*args)  # type: ignore[arg-type]
        self.instrument_id = instrument_id
        self.calls: list[tuple[str, str | int]] = []

    def on_start(self) -> None:
        self.subscribe_bars(self.instrument_id, "1h")

    def on_market_event(self, event: MarketEvent) -> None:
        self.calls.append(("event", event.event_id))
        self.submit_order(
            Order(
                client_order_id=ClientOrderId(f"event-{event.event_id}"),
                instrument_id=self.instrument_id,
                side=OrderSide.BUY,
                type=OrderType.MARKET,
                quantity=0.01,
            )
        )

    def on_bar(self, bar: Bar) -> None:
        self.calls.append(("bar", bar.bar_known_at))


def test_event_is_stably_deduplicated_before_bar_and_fills_next_open() -> None:
    bars = _bars()
    available_at = bars[1].bar_open_at + 30 * 60 * 1_000_000_000
    event = MarketEvent(
        event_id="event-1",
        event_type="listing",
        assets=("BTC",),
        action="lists BTC pair",
        severity=0.8,
        confidence=0.9,
        effective_at=available_at,
        available_at=available_at,
        evidence_ids=("fact-1:0",),
        metadata={"actor": "exchange", "version": 1},
    )
    engine = BacktestEngine(
        fee_rate=0,
        event_execution_policy=EventExecutionPolicy(liquidity_floor_bps=10),
    )
    strategy = EventRecorder(
        "events",
        engine.clock,
        engine.msgbus,
        instrument_id=bars[0].instrument_id,
    )
    engine.add_strategy(strategy)

    report = engine.run(bars, events=[event, event])

    event_index = strategy.calls.index(("event", "event-1"))
    assert strategy.calls[event_index + 1] == ("bar", bars[1].bar_known_at)
    assert sum(call == ("event", "event-1") for call in strategy.calls) == 1
    assert report.num_trades == 1
    assert report.fills[0].ts_ns == bars[2].bar_known_at
    assert report.fills[0].fill_price > bars[2].open


def test_no_event_input_is_identical_to_legacy_call() -> None:
    bars = _bars()
    left = BacktestEngine().run(bars)
    right = BacktestEngine().run(bars, events=[])
    assert left == right
