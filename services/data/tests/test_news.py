"""Tests for GET /news endpoint — extended to support baostock venue."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from inalpha_data.connectors.news.legacy import CnNewsProvider
from inalpha_data.news_models import NewsQuery

pytestmark = pytest.mark.anyio


def test_news_requires_auth(client: TestClient) -> None:
    """GET /news without token returns 401."""
    r = client.get("/news", params={"venue": "yfinance", "symbol": "AAPL"})
    assert r.status_code == 401


def test_news_yfinance_venue(client: TestClient, auth_headers: dict[str, str]) -> None:
    """GET /news with venue=yfinance returns results."""
    from inalpha_data.connectors import yfinance_conn as yf

    original = yf._connector.fetch_news

    async def mock_news(symbol, limit=20):
        return [
            {
                "title": "Test",
                "publisher": "Reuters",
                "link": "https://x.com",
                "published_at": "2026-05-29T00:00:00+00:00",
                "summary": "test",
            }
        ]

    yf._connector.fetch_news = mock_news
    try:
        r = client.get(
            "/news",
            headers=auth_headers,
            params={"venue": "yfinance", "symbol": "AAPL"},
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["title"] == "Test"
    finally:
        yf._connector.fetch_news = original


def test_news_baostock_venue(client: TestClient, auth_headers: dict[str, str]) -> None:
    """GET /news with venue=baostock returns A-share news."""
    from inalpha_data.connectors import baostock as bs

    original = bs._connector.fetch_news

    async def mock_news(symbol, limit=20):
        return [
            {
                "title": "茅台发布2026年Q1财报",
                "publisher": "东方财富",
                "link": "https://example.com",
                "published_at": "2026-05-29T10:30:00+00:00",
                "summary": "贵州茅台发布Q1报告...",
            }
        ]

    bs._connector.fetch_news = mock_news
    try:
        r = client.get(
            "/news",
            headers=auth_headers,
            params={"venue": "baostock", "symbol": "sh.600519"},
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 1
        assert "茅台" in body["items"][0]["title"]
    finally:
        bs._connector.fetch_news = original


def test_news_legacy_akshare_alias_normalizes_symbol(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """旧 venue 和大小写前缀应统一传给 Baostock connector。"""
    from inalpha_data.connectors import baostock as bs

    original = bs._connector.fetch_news
    seen: list[str] = []

    async def mock_news(symbol, limit=20):
        seen.append(symbol)
        return []

    bs._connector.fetch_news = mock_news
    try:
        r = client.get(
            "/news",
            headers=auth_headers,
            params={"venue": "akshare", "symbol": "SH.600519"},
        )
        assert r.status_code == 200
        assert seen == ["sh.600519"]
    finally:
        bs._connector.fetch_news = original


def test_news_unsupported_venue(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Venue=binance should return 400."""
    r = client.get(
        "/news",
        headers=auth_headers,
        params={"venue": "binance", "symbol": "BTC/USDT"},
    )
    assert r.status_code == 400
    assert "NEWS" in r.json()["code"]



def test_news_normalizes_legacy_venue_before_validation(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """旧客户端的 venue 大小写和空白继续兼容，响应仍回显原请求。"""
    from inalpha_data.connectors import yfinance_conn as yf

    original = yf._connector.fetch_news

    async def mock_news(symbol: str, limit: int = 20):
        return []

    yf._connector.fetch_news = mock_news
    try:
        r = client.get(
            "/news",
            headers=auth_headers,
            params={"venue": " YFINANCE ", "symbol": " AAPL "},
        )
    finally:
        yf._connector.fetch_news = original
    assert r.status_code == 200
    assert r.json()["venue"] == " YFINANCE "
    assert r.json()["symbol"] == " AAPL "


def test_news_naive_as_of_is_assumed_utc(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """无 offset 的查询时间按 UTC 解释，避免 PIT 比较触发 500。"""
    from inalpha_data.connectors import yfinance_conn as yf

    original = yf._connector.fetch_news

    async def mock_news(symbol: str, limit: int = 20):
        return [{"title": "Before cutoff", "published_at": "2026-07-29T11:00:00Z"}]

    yf._connector.fetch_news = mock_news
    try:
        r = client.get(
            "/news",
            headers=auth_headers,
            params={
                "market": "us",
                "symbol": "AAPL",
                "kinds": "media",
                "as_of": "2026-07-29T12:00:00",
            },
        )
    finally:
        yf._connector.fetch_news = original
    assert r.status_code == 200
    assert r.json()["as_of"] == "2026-07-29T12:00:00Z"
    assert len(r.json()["items"]) == 1


def test_market_only_news_does_not_claim_yfinance_venue(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """市场级 scope 与实际 provider 分离，响应不回填错误 venue。"""
    from inalpha_data.connectors import yfinance_conn as yf

    original = yf._connector.fetch_news

    async def mock_news(symbol: str, limit: int = 20):
        return []

    yf._connector.fetch_news = mock_news
    try:
        r = client.get(
            "/news",
            headers=auth_headers,
            params={"market": "us", "limit": 5},
        )
    finally:
        yf._connector.fetch_news = original
    assert r.status_code == 200
    assert r.json()["venue"] is None


def test_crypto_symbol_news_reports_scope_not_supported(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """市场级 RSS 不得把单标的无覆盖伪装成没有新闻。"""
    r = client.get(
        "/news",
        headers=auth_headers,
        params={"market": "crypto", "symbol": "BTC/USDT", "limit": 5},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "NEWS_SCOPE_NOT_SUPPORTED"


def test_crypto_symbol_provider_reports_unsupported() -> None:
    from inalpha_data.connectors.news.feed_models import DEFAULT_CRYPTO_FEEDS
    from inalpha_data.connectors.news.rss import RssFeedProvider
    from inalpha_data.news_models import NewsQuery

    provider = RssFeedProvider(DEFAULT_CRYPTO_FEEDS[0], timeout_s=1)

    async def run():
        try:
            return await provider.fetch(
                NewsQuery(market="crypto", symbol="BTC/USDT", limit=5)
            )
        finally:
            await provider.close()

    result = asyncio.run(run())
    assert result.items == []
    assert result.status == "unsupported"


def test_news_rejects_uncovered_kind_and_language(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """类型或语言没有 provider 覆盖时必须显式返回 422。"""
    cases = (
        {"market": "jp", "symbol": "6758.T", "kinds": "disclosure"},
        {"market": "us", "symbol": "AAPL", "kinds": "media", "language": "fr"},
    )
    for params in cases:
        r = client.get("/news", headers=auth_headers, params=params)
        assert r.status_code == 422
        assert r.json()["code"] == "NEWS_SCOPE_NOT_SUPPORTED"


def test_global_stock_news_uses_symbol_not_market_proxy(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """全球单股新闻必须查标的 ticker，不能被市场代理覆盖。"""
    from inalpha_data.connectors import yfinance_conn as yf

    original = yf._connector.fetch_news
    seen: list[str] = []

    async def mock_news(symbol: str, limit: int = 20) -> list[dict[str, object]]:
        seen.append(symbol)
        return [{"title": "Sony news", "published_at": "2026-07-29T05:00:00Z"}]

    yf._connector.fetch_news = mock_news
    try:
        r = client.get(
            "/news",
            headers=auth_headers,
            params={"market": "jp", "symbol": "6758.T", "kinds": "media"},
        )
    finally:
        yf._connector.fetch_news = original
    assert r.status_code == 200
    assert seen == ["6758.T"]
    assert r.json()["providers"][0]["provider"] == "yfinance"


async def test_cn_provider_preserves_failure_and_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """东财故障不能伪装空结果，成功条目也不能误标 Yahoo 或官方来源。"""
    from inalpha_data.connectors.news import legacy

    class FakeConnector:
        async def fetch_news(self, symbol: str, limit: int = 20):
            raise RuntimeError("eastmoney unavailable")

    monkeypatch.setattr(legacy, "get_connector_for_venue", lambda venue: FakeConnector())
    provider = CnNewsProvider()
    failed = await provider.fetch(NewsQuery(market="cn", symbol="sh.600519"))
    assert failed.status == "upstream_error"

    async def mock_news(self, symbol: str, limit: int = 20):
        return [{"title": "公告摘要", "published_at": "2026-07-29T08:00:00Z"}]

    monkeypatch.setattr(FakeConnector, "fetch_news", mock_news)
    succeeded = await provider.fetch(NewsQuery(market="cn", symbol="sh.600519"))
    assert succeeded.items[0].source_name == "eastmoney"
    assert succeeded.items[0].source_tier == "professional_media"


def test_news_accepts_comma_separated_kinds(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TS client 的逗号分隔 kinds 应在 FastAPI list 包装后继续展开。"""
    from inalpha_data.connectors import yfinance_conn as yf

    async def mock_news(symbol: str, limit: int = 20) -> list[dict[str, object]]:
        assert symbol == "SPY"
        return []

    monkeypatch.setattr(yf._connector, "fetch_news", mock_news)
    r = client.get(
        "/news",
        headers=auth_headers,
        params={"market": "us", "kinds": "market_news,media", "limit": 5},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["market"] == "us"
    assert body["providers"][0]["provider"] == "yfinance_market_proxy"
