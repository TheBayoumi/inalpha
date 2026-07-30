"""统一财经新闻层测试。"""
from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from inalpha_data.connectors.news.dedupe import filter_and_dedupe
from inalpha_data.connectors.news.feed_models import FeedDefinition
from inalpha_data.connectors.news.hkex_parser import parse_rows
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


def test_dedupe_prefers_official_source() -> None:
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
