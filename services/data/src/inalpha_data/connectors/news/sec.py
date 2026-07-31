"""SEC EDGAR 官方披露 provider。"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from time import monotonic
from typing import Any

import httpx

from ...news_models import NewsQuery
from .base import ProviderResult
from .sec_parser import parse_submissions

_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"


class SecNewsProvider:
    """通过 SEC 官方 JSON 获取美国上市公司披露。"""

    name = "us"
    coverage = "snapshot_only"

    def __init__(self, *, user_agent: str, timeout_s: float, min_interval_s: float) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout_s,
            trust_env=False,
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
        )
        self._min_interval_s = min_interval_s
        self._request_lock = asyncio.Lock()
        self._last_request_at = 0.0
        self._ticker_map: dict[str, str] | None = None

    def supports(self, query: NewsQuery) -> bool:
        """SEC 只覆盖美国单标的英文官方披露。"""
        return bool(
            query.market == "us"
            and query.symbol
            and (not query.kinds or "disclosure" in query.kinds)
            and (not query.language or query.language == "en")
        )

    async def fetch(self, query: NewsQuery) -> ProviderResult:
        """返回 ticker 截至查询时点的近期 SEC filings。"""
        fetched_at = datetime.now(UTC)
        if query.market != "us" or not query.symbol:
            return ProviderResult(self.name, "unsupported", fetched_at=fetched_at)
        try:
            cik = await self._resolve_cik(query.symbol)
            if cik is None:
                return ProviderResult(self.name, "no_results", fetched_at=fetched_at)
            payload = await self._get_json(_SUBMISSIONS_URL.format(cik=cik))
            items = parse_submissions(payload, query, fetched_at, cik)
            return ProviderResult(
                self.name,
                "ok" if items else "no_results",
                fetched_at=fetched_at,
                items=items,
                coverage="snapshot_only",
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
        """关闭 SEC HTTP client。"""
        await self._client.aclose()

    async def _resolve_cik(self, symbol: str) -> str | None:
        if self._ticker_map is None:
            payload = await self._get_json(_TICKERS_URL)
            self._ticker_map = {
                str(value.get("ticker", "")).upper(): str(value.get("cik_str", "")).zfill(10)
                for value in payload.values()
                if isinstance(value, dict)
            }
        ticker = symbol.split(".", 1)[0].upper()
        return self._ticker_map.get(ticker)

    async def _get_json(self, url: str) -> dict[str, Any]:
        async with self._request_lock:
            wait_s = self._min_interval_s - (monotonic() - self._last_request_at)
            if wait_s > 0:
                await asyncio.sleep(wait_s)
            response = await self._client.get(url)
            self._last_request_at = monotonic()
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("SEC returned a non-object payload")
        return payload
