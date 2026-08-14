"""交易执行的 fresh ticker 跨服务契约回归测试。"""
from __future__ import annotations

from typing import Any

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from inalpha_paper.data_client import DataClient

from .conftest import fresh_account_token

pytestmark = pytest.mark.integration


def _ticker_response(
    *,
    venue: str,
    symbol: str,
    price: float,
    source: str,
    is_stale: bool = False,
    stale_seconds: int = 1,
) -> dict[str, Any]:
    """构造 data-service 的完整 ticker 响应。"""
    return {
        "venue": venue,
        "symbol": symbol,
        "price": price,
        "ts": "2026-08-13T02:20:00Z",
        "source": source,
        "is_stale": is_stale,
        "stale_seconds": stale_seconds,
    }


@pytest.mark.parametrize(
    ("fresh", "expected"),
    [(True, "true"), (False, "false"), (None, None)],
)
@respx.mock
async def test_data_client_serializes_fresh_query(
    fresh: bool | None, expected: str | None
) -> None:
    """DataClient 只在 caller 明确选择时发送 fresh 参数。"""
    route = respx.get("http://data-mock.test/ticker").mock(
        return_value=Response(
            200,
            json=_ticker_response(
                venue="baostock",
                symbol="sh.600519",
                price=1_415.0,
                source="baostock_ticker",
            ),
        )
    )

    async with DataClient("http://data-mock.test", "test-token") as data_client:
        await data_client.get_ticker(
            venue="baostock",
            symbol="sh.600519",
            fresh=fresh,
        )

    assert route.called
    request = route.calls.last.request
    assert request.url.params.get("venue") == "baostock"
    assert request.url.params.get("symbol") == "sh.600519"
    assert request.url.params.get("fresh") == expected


@respx.mock
def test_submit_order_without_ref_price_requests_fresh_ticker(
    client: TestClient,
) -> None:
    """直接下单的自动参考价必须来自 fresh ticker，而不是 DB bar 缓存。"""
    _, token = fresh_account_token("fresh-order")
    route = respx.get(
        "http://data-mock.test/ticker",
        params={"venue": "binance", "symbol": "BTC/USDT", "fresh": "true"},
    ).mock(
        return_value=Response(
            200,
            json=_ticker_response(
                venue="binance",
                symbol="BTC/USDT",
                price=50_000.0,
                source="binance_ticker",
            ),
        )
    )

    response = client.post(
        "/orders/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "venue": "binance",
            "symbol": "BTC/USDT",
            "side": "BUY",
            "type": "MARKET",
            "quantity": 0.01,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "FILLED"
    assert body["avg_fill_price"] == 50_000.0
    assert route.call_count == 1


@respx.mock
def test_submit_order_rejects_stale_execution_ticker(client: TestClient) -> None:
    """交易执行不得把 data 明确标记的陈旧报价当作成交价。"""
    _, token = fresh_account_token("stale-order")
    route = respx.get(
        "http://data-mock.test/ticker",
        params={"venue": "binance", "symbol": "BTC/USDT", "fresh": "true"},
    ).mock(
        return_value=Response(
            200,
            json=_ticker_response(
                venue="binance",
                symbol="BTC/USDT",
                price=50_000.0,
                source="binance_ticker",
                is_stale=True,
                stale_seconds=900,
            ),
        )
    )

    response = client.post(
        "/orders/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "venue": "binance",
            "symbol": "BTC/USDT",
            "side": "BUY",
            "type": "MARKET",
            "quantity": 0.01,
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["code"] == "REF_PRICE_UNAVAILABLE"
    assert route.call_count == 1


@pytest.mark.parametrize(
    "first_response",
    [
        pytest.param(
            Response(
                404,
                json={
                    "code": "NO_PRICE_AVAILABLE",
                    "message": "no cached or live price available",
                },
            ),
            id="unavailable",
        ),
        pytest.param(
            Response(
                200,
                json=_ticker_response(
                    venue="baostock",
                    symbol="sh.600519",
                    price=1_415.0,
                    source="baostock_ticker",
                    is_stale=True,
                    stale_seconds=900,
                ),
            ),
            id="stale",
        ),
    ],
)
@respx.mock
def test_a_share_plan_retries_same_token_after_fresh_quote_recovers(
    client: TestClient,
    first_response: Response,
) -> None:
    """A 股报价失败不消费 token，恢复后同一 plan 可按 fresh ticker 成交。"""
    _, token = fresh_account_token("fresh-a-share-plan")
    headers = {"Authorization": f"Bearer {token}"}
    route = respx.get(
        "http://data-mock.test/ticker",
        params={"venue": "baostock", "symbol": "sh.600519", "fresh": "true"},
    ).mock(
        side_effect=[
            first_response,
            Response(
                200,
                json=_ticker_response(
                    venue="baostock",
                    symbol="sh.600519",
                    price=1_415.0,
                    source="baostock_ticker",
                ),
            ),
        ]
    )

    created = client.post(
        "/plans",
        headers=headers,
        json={
            "intent": "open_long",
            "venue": "baostock",
            "symbol": "sh.600519",
            "side": "BUY",
            "type": "MARKET",
            "quantity": 1,
            "rationale": "verify A-share fresh quote execution",
            "expire_in_seconds": 300,
        },
    )
    assert created.status_code == 200, created.text
    plan_id = created.json()["plan_id"]

    approved = client.post(
        f"/plans/{plan_id}/approve",
        headers=headers,
        json={"approver": "tester"},
    )
    assert approved.status_code == 200, approved.text
    approval_token = approved.json()["approval_token"]

    first = client.post(
        f"/plans/{plan_id}/execute",
        headers=headers,
        json={"approvalToken": approval_token},
    )
    assert first.status_code == 400, first.text
    assert first.json()["code"] == "REF_PRICE_UNAVAILABLE"

    after_failure = client.get(f"/plans/{plan_id}", headers=headers)
    assert after_failure.status_code == 200, after_failure.text
    assert after_failure.json()["status"] == "approved"
    assert after_failure.json()["resulting_order_id"] is None

    second = client.post(
        f"/plans/{plan_id}/execute",
        headers=headers,
        json={"approvalToken": approval_token},
    )
    assert second.status_code == 200, second.text
    result = second.json()
    assert result["plan_status"] == "executed"
    assert result["order"]["status"] == "FILLED"
    assert result["order"]["avg_fill_price"] == 1_415.0
    assert route.call_count == 2
