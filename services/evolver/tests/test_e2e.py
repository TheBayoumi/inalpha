"""Evolver API DB/auth 契约测试。"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from inalpha_evolver.config import get_evolver_settings
from inalpha_evolver.main import app

from .llm_snapshot_fixtures import approval_token, llm_snapshot

_SECRET = "evolver-test-secret-at-least-32-bytes-long"


def _headers(key: str | None = None, *, include_approval: bool = True) -> dict[str, str]:
    subject = f"test:{uuid4()}"
    token = jwt.encode(
        {"sub": subject, "exp": int(time.time()) + 3600},
        _SECRET,
        algorithm="HS256",
    )
    headers = {"Authorization": f"Bearer {token}"}
    if key:
        headers["Idempotency-Key"] = key
        if include_approval:
            headers["X-Evolution-Approval"] = approval_token(
                subject=subject,
                operation_id=key,
                secret=_SECRET,
            )
    return headers


@pytest.fixture(scope="module")
def client() -> TestClient:
    os.environ["DATABASE_URL"] = os.environ.get(
        "EVOLVER_TEST_DATABASE_URL",
        "postgresql+psycopg://quant:devpass@localhost:5433/inalpha_evo_test",
    )
    os.environ["JWT_SECRET"] = _SECRET
    get_evolver_settings.cache_clear()
    with TestClient(app) as value:
        yield value
    get_evolver_settings.cache_clear()


def _payload() -> dict:
    now = datetime.now(UTC)
    return {
        "seed_strategy_id": "sma_cross_v1",
        "budget": 1,
        "config": {
            "venue": "binance",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "from_ts": (now - timedelta(days=1)).isoformat(),
            "as_of": now.isoformat(),
            "initial_cash": 10_000,
        },
        "llm": llm_snapshot(),
    }


def test_business_endpoints_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/runs").status_code == 401


def test_start_requires_idempotency_key(client: TestClient) -> None:
    assert client.post("/api/v1/runs", json=_payload(), headers=_headers()).status_code == 400


def test_start_requires_explicit_approval_assertion(client: TestClient) -> None:
    headers = _headers(f"api-test-{uuid4()}", include_approval=False)
    assert client.post("/api/v1/runs", json=_payload(), headers=headers).status_code == 400


def test_start_rejects_approval_for_another_operation(client: TestClient) -> None:
    key = f"api-test-{uuid4()}"
    headers = _headers(key)
    token = headers["X-Evolution-Approval"]
    payload = jwt.decode(token, _SECRET, algorithms=["HS256"])
    headers["X-Evolution-Approval"] = approval_token(
        subject=payload["sub"],
        operation_id=f"other-{uuid4()}",
        secret=_SECRET,
    )
    assert client.post("/api/v1/runs", json=_payload(), headers=headers).status_code == 403


def test_start_rejects_tampered_snapshot_before_approval(client: TestClient) -> None:
    key = f"api-test-{uuid4()}"
    payload = _payload()
    payload["llm"]["model"] = "tampered-model"
    assert client.post("/api/v1/runs", json=payload, headers=_headers(key)).status_code == 400


def test_start_returns_queued_and_is_idempotent(client: TestClient) -> None:
    key = f"api-test-{uuid4()}"
    headers = _headers(key)
    payload = _payload()
    first = client.post("/api/v1/runs", json=payload, headers=headers)
    second = client.post("/api/v1/runs", json=payload, headers=headers)

    assert first.status_code == 202
    assert first.json()["status"] == "queued"
    assert second.status_code == 202
    assert second.json()["run_id"] == first.json()["run_id"]
