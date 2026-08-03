"""HKEXnews 公告 provider。"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx

from ...news_models import NewsQuery
from .base import ProviderResult
from .hkex_parser import parse_rows

_BASE_URL = "https://www1.hkexnews.hk"
_HONG_KONG_TZ = ZoneInfo("Asia/Hong_Kong")


def _requested_languages(language: str | None) -> tuple[str, ...]:
    """把查询语言映射到 HKEX 搜索端点；未指定时同时取中英文。"""
    if language in {"en", "en-HK"}:
        return ("en",)
    if language in {"zh", "zh-HK"}:
        return ("zh",)
    return ("en", "zh")


class HkexNewsProvider:
    name = "hk"
    coverage = "snapshot_only"

    def __init__(self, *, timeout_s: float) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout_s,
            trust_env=False,
            headers={"User-Agent": "Mozilla/5.0 Inalpha"},
        )

    def supports(self, query: NewsQuery) -> bool:
        """HKEX 只覆盖港股单标的中英文官方披露。"""
        return bool(
            query.market == "hk"
            and query.symbol
            and (not query.kinds or "disclosure" in query.kinds)
            and (not query.language or query.language in {"en", "en-HK", "zh", "zh-HK"})
        )

    async def fetch(self, query: NewsQuery) -> ProviderResult:
        fetched_at = datetime.now(UTC)
        if query.market != "hk" or not query.symbol:
            return ProviderResult(self.name, "unsupported", fetched_at=fetched_at)
        try:
            symbol = query.symbol.split(".", 1)[0].lstrip("0") or "0"
            stock_id = await self._resolve_stock_id(symbol)
            if stock_id is None:
                return ProviderResult(self.name, "no_results", fetched_at=fetched_at)
            rows = await asyncio.gather(
                *(
                    self._search(language, stock_id, query)
                    for language in _requested_languages(query.language)
                )
            )
            items = parse_rows(
                [row for language_rows in reversed(rows) for row in language_rows],
                query,
                fetched_at,
            )
            return ProviderResult(
                self.name,
                "ok" if items else "no_results",
                fetched_at=fetched_at,
                items=items,
                coverage=self.coverage,
            )
        except httpx.TimeoutException as exc:
            return ProviderResult(self.name, "timeout", fetched_at=fetched_at, error=str(exc))
        except httpx.HTTPStatusError as exc:
            status = "rate_limited" if exc.response.status_code == 429 else "upstream_error"
            return ProviderResult(self.name, status, fetched_at=fetched_at, error=str(exc))
        except Exception as exc:
            return ProviderResult(
                self.name, "upstream_error", fetched_at=fetched_at, error=str(exc)
            )

    async def close(self) -> None:
        """关闭 client。"""
        await self._client.aclose()

    async def _resolve_stock_id(self, symbol: str) -> str | None:
        response = await self._client.get(
            f"{_BASE_URL}/search/prefix.do",
            params={
                "callback": "callback",
                "lang": "EN",
                "type": "A",
                "name": symbol,
                "market": "SEHK",
            },
        )
        response.raise_for_status()
        match = re.search(r"callback\((.*)\);?\s*$", response.text, re.S)
        if not match:
            raise ValueError("HKEX issuer lookup returned invalid JSONP")
        payload = json.loads(match.group(1))
        for candidate in payload.get("stockInfo", []):
            code = str(candidate.get("code", "")).lstrip("0") or "0"
            if code == symbol:
                return str(candidate.get("stockId"))
        return None

    async def _search(
        self, language: str, stock_id: str, query: NewsQuery
    ) -> list[dict[str, Any]]:
        end = query.as_of or datetime.now(UTC)
        start = query.since or end - timedelta(days=365)
        local_start = start.astimezone(_HONG_KONG_TZ)
        local_end = end.astimezone(_HONG_KONG_TZ)
        params = {
            "lang": language,
            "sortDir": "0",
            "sortByOptions": "DateTime",
            "category": "0",
            "market": "SEHK",
            "stockId": stock_id,
            "documentType": "-1",
            "fromDate": local_start.strftime("%Y%m%d"),
            "toDate": local_end.strftime("%Y%m%d"),
            "title": "",
        }
        response = await self._client.get(
            f"{_BASE_URL}/search/titleSearchServlet.do?{urlencode(params)}"
        )
        response.raise_for_status()
        envelope = response.json()
        result = envelope.get("result") if isinstance(envelope, dict) else None
        if not isinstance(result, str):
            raise ValueError("HKEX title search missing result")
        rows = json.loads(result)
        for row in rows:
            row["_language"] = "zh-HK" if language == "zh" else "en-HK"
        return rows
