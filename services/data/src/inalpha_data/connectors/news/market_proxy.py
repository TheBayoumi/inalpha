"""Yahoo 代表性指数/ETF 的市场级新闻代理。"""
from __future__ import annotations

from datetime import UTC, datetime

from ...news_models import NewsItem, NewsQuery
from .. import yfinance_conn
from .base import ProviderResult

_MARKET_PROXIES = {
    "us": ("SPY", "S&P 500 market proxy"),
    "hk": ("^HSI", "Hang Seng Index market proxy"),
    "jp": ("^N225", "Nikkei 225 market proxy"),
    "kr": ("^KS11", "KOSPI market proxy"),
    "au": ("^AXJO", "S&P/ASX 200 market proxy"),
    "in": ("^NSEI", "Nifty 50 market proxy"),
    "uk": ("^FTSE", "FTSE 100 market proxy"),
    "de": ("^GDAXI", "DAX market proxy"),
    "fr": ("^FCHI", "CAC 40 market proxy"),
    "ca": ("^GSPTSE", "S&P/TSX Composite market proxy"),
    "br": ("^BVSP", "Bovespa market proxy"),
    "global": ("ACWI", "MSCI ACWI ETF market proxy"),
}


class YahooMarketNewsProvider:
    """用代表性市场载体聚合无 symbol 市场新闻。"""

    name = "yfinance_market_proxy"

    def supports(self, query: NewsQuery) -> bool:
        """市场代理只覆盖无标的的 market_news。"""
        return bool(
            not query.symbol
            and query.market in _MARKET_PROXIES
            and not query.language
            and (not query.kinds or "market_news" in query.kinds)
        )

    async def fetch(self, query: NewsQuery) -> ProviderResult:
        """拉市场代理 ticker 新闻，并明确标注其代理性质。"""
        fetched_at = datetime.now(UTC)
        proxy = _MARKET_PROXIES.get(query.market or "")
        if query.symbol or proxy is None:
            return ProviderResult(self.name, "unsupported", fetched_at=fetched_at)
        ticker, label = proxy
        try:
            raw = await yfinance_conn.get_connector().fetch_news(ticker, limit=query.limit)
        except Exception as exc:
            return ProviderResult(
                self.name, "upstream_error", fetched_at=fetched_at, error=str(exc)
            )
        items = [_item(value, query, fetched_at, ticker, label) for value in raw]
        return ProviderResult(
            self.name, "ok" if items else "no_results", fetched_at=fetched_at, items=items
        )

    async def close(self) -> None:
        """底层 Yahoo connector 由既有生命周期管理。"""


def _item(
    value: dict[str, object],
    query: NewsQuery,
    fetched_at: datetime,
    ticker: str,
    label: str,
) -> NewsItem:
    """把 Yahoo 结果转换为明确标记的市场代理新闻。"""
    summary = str(value.get("summary") or "")
    note = f"Market-level proxy via {ticker} ({label}); not a complete market newswire."
    return NewsItem(
        title=str(value.get("title") or ""),
        publisher=str(value.get("publisher") or ""),
        link=str(value.get("link") or ""),
        published_at=value.get("published_at"),  # type: ignore[arg-type]
        summary=f"{note} {summary}".strip(),
        kind="market_news",
        source_id=str(value.get("source_id") or ""),
        source_name=self_source(query.market),
        source_tier="aggregator",
        fetched_at=fetched_at,
        market=query.market,
        symbols=[ticker],
        language=query.language,
    )


def self_source(market: str | None) -> str:
    """给 provider 状态之外的条目生成稳定来源 ID。"""
    return f"yfinance_{market}_market_proxy"
