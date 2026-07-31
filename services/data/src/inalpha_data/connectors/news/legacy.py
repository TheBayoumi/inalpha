"""现有东财与 Yahoo 新闻能力的 provider 适配。"""
from __future__ import annotations

from datetime import UTC, datetime

from ...news_models import NewsItem, NewsQuery
from .. import yfinance_conn
from .._base import get_connector_for_venue
from ..cn_market import CnMarketError
from ..cn_market import get_connector as get_cn_market
from .base import ProviderResult


class CnNewsProvider:
    """A 股市场快讯与个股东财新闻。"""

    name = "eastmoney"
    coverage = "snapshot_only"

    def supports(self, query: NewsQuery) -> bool:
        """东财只覆盖 A 股媒体与市场快讯。"""
        market_matches = query.market == "cn" or query.venue in {"baostock", "akshare"}
        supported_kinds = {"media"} if query.symbol else {"market_news"}
        return (
            market_matches
            and not query.language
            and (not query.kinds or bool(set(query.kinds) & supported_kinds))
        )

    async def fetch(self, query: NewsQuery) -> ProviderResult:
        fetched_at = datetime.now(UTC)
        if query.market != "cn" and query.venue not in {"baostock", "akshare"}:
            return ProviderResult(self.name, "unsupported", fetched_at=fetched_at)
        try:
            if query.symbol:
                connector = get_connector_for_venue("baostock")
                raw = await connector.fetch_news(query.symbol, limit=query.limit)  # type: ignore[attr-defined]
                items = _items(raw, query, fetched_at, "media", "eastmoney", "professional_media")
            else:
                raw = await get_cn_market().fetch_market_news(limit=query.limit)
                items = _items(
                    raw, query, fetched_at, "market_news", "eastmoney", "professional_media"
                )
        except CnMarketError as exc:
            return ProviderResult(
                self.name, "upstream_error", fetched_at=fetched_at, error=str(exc)
            )
        except Exception as exc:
            return ProviderResult(
                self.name, "upstream_error", fetched_at=fetched_at, error=str(exc)
            )
        return ProviderResult(
            self.name,
            "ok" if items else "no_results",
            fetched_at=fetched_at,
            items=items,
            coverage="snapshot_only",
        )

    async def close(self) -> None:
        """底层 connector 由既有生命周期管理。"""


class YahooNewsProvider:
    """Yahoo Finance 全球 ticker 新闻聚合兜底。"""

    name = "yfinance"
    coverage = "snapshot_only"

    def supports(self, query: NewsQuery) -> bool:
        """Yahoo ticker 新闻仅覆盖非 Crypto 的媒体消息。"""
        return bool(
            query.symbol
            and query.market != "crypto"
            and not query.language
            and (not query.kinds or "media" in query.kinds)
        )

    async def fetch(self, query: NewsQuery) -> ProviderResult:
        fetched_at = datetime.now(UTC)
        if not query.symbol or query.market == "crypto":
            return ProviderResult(self.name, "unsupported", fetched_at=fetched_at)
        try:
            raw = await yfinance_conn.get_connector().fetch_news(query.symbol, limit=query.limit)
        except Exception as exc:
            return ProviderResult(
                self.name, "upstream_error", fetched_at=fetched_at, error=str(exc)
            )
        items = _items(raw, query, fetched_at, "media", "yfinance", "aggregator")
        return ProviderResult(
            self.name,
            "ok" if items else "no_results",
            fetched_at=fetched_at,
            items=items,
            coverage="snapshot_only",
        )

    async def close(self) -> None:
        """底层 connector 由既有生命周期管理。"""


def _items(
    raw: list[dict[str, object]],
    query: NewsQuery,
    fetched_at: datetime,
    kind: str,
    source_name: str,
    source_tier: str,
) -> list[NewsItem]:
    """批量适配既有 connector 字段。"""
    return [
        _item(value, query, fetched_at, kind, source_name, source_tier) for value in raw
    ]


def _item(
    value: dict[str, object],
    query: NewsQuery,
    fetched_at: datetime,
    kind: str,
    source_name: str,
    source_tier: str,
) -> NewsItem:
    """把既有 connector 字段转为统一模型。"""
    published = value.get("published_at")
    return NewsItem(
        title=str(value.get("title") or ""),
        publisher=str(value.get("publisher") or ""),
        link=str(value.get("link") or ""),
        published_at=published,  # type: ignore[arg-type]
        summary=str(value.get("summary") or ""),
        kind=kind,  # type: ignore[arg-type]
        source_id=str(value.get("source_id") or ""),
        source_name=source_name,
        source_tier=source_tier,  # type: ignore[arg-type]
        fetched_at=fetched_at,
        market=query.market,
        symbols=[query.symbol] if query.symbol else [],
        language=query.language,
    )
