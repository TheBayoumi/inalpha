"""统一财经新闻层测试。"""
from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from inalpha_data.connectors.news.dedupe import filter_and_dedupe
from inalpha_data.connectors.news.feed_models import FeedDefinition
from inalpha_data.connectors.news.hkex import HkexNewsProvider
from inalpha_data.connectors.news.hkex_parser import parse_rows
from inalpha_data.connectors.news.legacy import YahooNewsProvider
from inalpha_data.connectors.news.market_proxy import YahooMarketNewsProvider
from inalpha_data.connectors.news.rss import RssFeedProvider
from inalpha_data.connectors.news.sec_parser import parse_submissions
from inalpha_data.news_models import NewsItem, NewsQuery

pytestmark = pytest.mark.anyio


def test_sec_submissions_are_official_disclosures() -> None:
    query = NewsQuery(market="us", symbol="AAPL", as_of="2026-07-01T00:00:00Z")
    payload = {
        "name": "Apple Inc.",
        "filings": {"recent": {
            "accessionNumber": ["0000320193-26-000001", "0000320193-26-000002"],
            "acceptanceDateTime": ["2026-06-30T18:01:02Z", "2026-07-02T18:01:02Z"],
            "filingDate": ["2026-06-30", "2026-07-02"],
            "form": ["8-K", "10-Q"],
            "primaryDocument": ["aapl-8k.htm", "aapl-10q.htm"],
        }},
    }
    items = filter_and_dedupe(
        parse_submissions(payload, query, datetime.now(UTC), "0000320193"), query
    )
    assert len(items) == 1
    assert items[0].kind == "disclosure"
    assert items[0].source_tier == "official"
    assert "/320193/000032019326000001/aapl-8k.htm" in items[0].link


def test_hkex_rows_dedupe_languages_and_convert_timezone() -> None:
    query = NewsQuery(market="hk", symbol="0700.HK")
    rows = [
        {"NEWS_ID": "1", "TITLE": "Annual Results", "DATE_TIME": "28/07/2026 18:30",
         "FILE_LINK": "/listedco/listconews/sehk/2026/1.pdf", "_language": "en-HK"},
        {"NEWS_ID": "1", "TITLE": "全年業績", "DATE_TIME": "28/07/2026 18:30",
         "FILE_LINK": "/listedco/listconews/sehk/2026/1c.pdf", "_language": "zh-HK"},
    ]
    items = parse_rows(rows, query, datetime.now(UTC))
    assert len(items) == 1
    assert items[0].published_at == datetime(2026, 7, 28, 10, 30, tzinfo=UTC)


async def test_hkex_provider_respects_language_and_hong_kong_date_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HKEX 只查目标语言，并按香港自然日构造 PIT 查询窗口。"""
    seen_languages: list[str] = []
    seen_params: dict[str, list[str]] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_params
        if request.url.path.endswith("/search/prefix.do"):
            return httpx.Response(
                200,
                text='callback({"stockInfo":[{"code":"700","stockId":"42"}]});',
            )
        seen_params = parse_qs(urlsplit(str(request.url)).query)
        seen_languages.append(seen_params["lang"][0])
        return httpx.Response(200, json={"result": "[]"})

    provider = HkexNewsProvider(timeout_s=1)
    await provider._client.aclose()
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await provider.fetch(
            NewsQuery(
                market="hk",
                symbol="0700.HK",
                language="en",
                since="2026-07-29T17:00:00Z",
                as_of="2026-07-29T18:00:00Z",
            )
        )
    finally:
        await provider.close()

    assert result.status == "no_results"
    assert seen_languages == ["en"]
    assert seen_params["fromDate"] == ["20260730"]
    assert seen_params["toDate"] == ["20260730"]


@pytest.mark.parametrize(
    ("provider", "query"),
    [
        (YahooNewsProvider(), NewsQuery(market="us", symbol="AAPL")),
        (YahooMarketNewsProvider(), NewsQuery(market="us")),
    ],
)
async def test_yahoo_providers_classify_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
    provider: YahooNewsProvider | YahooMarketNewsProvider,
    query: NewsQuery,
) -> None:
    """Yahoo 限流需保留机器可读状态，不能退化成普通上游错误。"""
    class FakeConnector:
        async def fetch_news(self, symbol: str, limit: int = 20) -> list[dict[str, object]]:
            raise RuntimeError("Yahoo Finance rate limit exceeded")

    monkeypatch.setattr(
        "inalpha_data.connectors.news.legacy.yfinance_conn.get_connector",
        lambda: FakeConnector(),
    )
    result = await provider.fetch(query)
    assert result.status == "rate_limited"


async def test_rss_provider_reuses_cached_items_on_304() -> None:
    feed = FeedDefinition("test", "Test Feed", "https://feed.test/rss", "professional_media", "en")
    provider = RssFeedProvider(feed, timeout_s=1)
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                200,
                headers={"etag": '"v1"'},
                content=b"<rss version='2.0'><channel><item><guid>x</guid><title>T</title>"
                b"<link>https://x.test</link><pubDate>Tue, 28 Jul 2026 10:00:00 GMT</pubDate>"
                b"</item></channel></rss>",
            )
        assert request.headers["if-none-match"] == '"v1"'
        return httpx.Response(304)

    await provider._client.aclose()
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        first = await provider.fetch(NewsQuery(market="crypto", limit=5))
        second = await provider.fetch(NewsQuery(market="crypto", limit=5))
    finally:
        await provider.close()
    assert first.status == second.status == "ok"
    assert first.items[0].source_name == "test"
    assert second.items[0].title == "T"


def test_dedupe_prefers_url_across_provider_source_ids() -> None:
    """同一 canonical URL 跨 provider 应合并，即使各自 source_id 不同。"""
    query = NewsQuery(market="us", symbol="AAPL")
    ts = datetime(2026, 7, 28, tzinfo=UTC)
    wire = NewsItem(
        title="Event",
        link="https://x.test/a?utm_source=wire",
        published_at=ts,
        source_id="wire-1",
        source_name="wire",
        source_tier="professional_media",
    )
    aggregator = NewsItem(
        title="Event copy",
        link="https://x.test/a",
        published_at=ts,
        source_id="agg-9",
        source_name="aggregator",
        source_tier="aggregator",
    )

    result = filter_and_dedupe([aggregator, wire], query)

    assert len(result) == 1
    assert result[0].source_name == "wire"
    assert "aggregator" in result[0].alternative_sources


def test_dedupe_prefers_official_source_without_mutating_inputs() -> None:
    query = NewsQuery(market="us", symbol="AAPL")
    ts = datetime(2026, 7, 28, tzinfo=UTC)
    media = NewsItem(title="Event", link="https://x.test/a?utm_source=z", published_at=ts,
                     source_name="wire", source_tier="professional_media")
    official = NewsItem(title="Event", link="https://x.test/a", published_at=ts,
                        source_name="sec", source_tier="official", kind="disclosure")
    result = filter_and_dedupe([media, official], query)
    assert len(result) == 1
    assert result[0].source_name == "sec"
    assert "wire" in result[0].alternative_sources
    assert media.alternative_sources == []
    assert official.alternative_sources == []
