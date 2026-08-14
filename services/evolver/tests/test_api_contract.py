"""Evolver API schema 与 presenter 单测。"""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from inalpha_evolver.api.presenters import run_response
from inalpha_evolver.api.request_hash import normalized_request
from inalpha_evolver.api.schemas import EvolutionConfig, StartRunRequest


def _request(symbol: str = "BTCUSDT") -> StartRunRequest:
    now = datetime(2026, 8, 12, 12, tzinfo=UTC)
    return StartRunRequest(
        config=EvolutionConfig(
            venue="binance",
            symbol=symbol,
            timeframe="1h",
            from_ts=now - timedelta(days=30),
            as_of=now,
        )
    )


def test_request_hash_is_stable_and_payload_sensitive() -> None:
    config_a, hash_a = normalized_request(_request())
    config_b, hash_b = normalized_request(_request())
    _config_c, hash_c = normalized_request(_request("ETHUSDT"))

    assert config_a == config_b
    assert hash_a == hash_b
    assert hash_a != hash_c


def test_invalid_window_is_rejected() -> None:
    now = datetime(2026, 8, 12, 12, tzinfo=UTC)
    with pytest.raises(ValueError):
        EvolutionConfig(
            venue="binance",
            symbol="BTCUSDT",
            timeframe="1h",
            from_ts=now,
            as_of=now,
        )


def test_run_presenter_converts_numeric_cost() -> None:
    now = datetime(2026, 8, 12, 12, tzinfo=UTC)
    response = run_response(
        {
            "run_id": uuid4(),
            "seed_strategy_id": "sma_cross_v1",
            "budget": 4,
            "config": {},
            "status": "queued",
            "llm_cost_usd": "0.1250",
            "queued_at": now,
        },
        summary={"attempted": 2, "succeeded": 1, "rejected": 1},
    )
    assert response.llm_cost_usd == pytest.approx(0.125)
    assert response.attempted == 2
