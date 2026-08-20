"""Evolver API schema 与 presenter 单测。"""
from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from inalpha_evolver.api.presenters import candidate_response, run_response
from inalpha_evolver.api.request_hash import normalized_request
from inalpha_evolver.api.schemas import (
    EvolutionConfig,
    RunStatusResponse,
    StartRunRequest,
)


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


def test_datetime_inputs_normalize_or_fail_without_type_error() -> None:
    now = datetime.now(UTC) - timedelta(minutes=1)
    config = EvolutionConfig(
        venue="binance", symbol="BTCUSDT", timeframe="1h",
        from_ts=(now - timedelta(days=1)).replace(tzinfo=None),
        as_of=now.astimezone(timezone(timedelta(hours=9))),
    )
    assert config.from_ts.tzinfo == UTC
    assert config.as_of.tzinfo == UTC
    with pytest.raises(ValueError, match="timezone-aware"):
        EvolutionConfig(
            venue="binance", symbol="BTCUSDT", timeframe="1h",
            from_ts=now - timedelta(days=1), as_of=now.replace(tzinfo=None))


def test_future_as_of_returns_http_422() -> None:
    app = FastAPI()

    @app.post("/validate")
    async def validate(body: StartRunRequest) -> dict[str, bool]:
        return {"ok": bool(body)}

    future = datetime.now(UTC) + timedelta(minutes=1)
    response = TestClient(app).post(
        "/validate",
        json={"config": {"venue": "binance", "symbol": "BTCUSDT",
                         "timeframe": "1h",
                         "from_ts": (future - timedelta(days=1)).isoformat(),
                         "as_of": future.isoformat()}},
    )
    assert response.status_code == 422
    assert "trusted current time" in response.text


def test_candidate_response_exposes_data_epoch() -> None:
    candidate_id, run_id = uuid4(), uuid4()
    response = candidate_response({
        "candidate_id": candidate_id, "run_id": run_id, "slot": 1,
        "generation": 1, "stage": "evaluation", "outcome": "succeeded",
        "data_epoch": 1_786_000_000_000,
    })
    assert response.data_epoch == 1_786_000_000_000


def test_run_dto_exposes_manifest_cutoff_and_lag() -> None:
    manifest = RunStatusResponse.model_json_schema()["$defs"]["DatasetManifest"]
    required = set(manifest["required"])
    assert {"latest_bar_ts", "cutoff_bar_ts", "freshness_lag_seconds",
            "data_epoch", "backfill"} <= required
