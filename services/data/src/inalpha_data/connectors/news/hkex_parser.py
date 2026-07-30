"""HKEX 公告结果解析。"""
from __future__ import annotations

import html
import re
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from ...news_models import NewsItem, NewsQuery

_BASE_URL = "https://www1.hkexnews.hk"


def parse_rows(
    rows: list[dict[str, Any]], query: NewsQuery, fetched_at: datetime
) -> list[NewsItem]:
    """按 NEWS_ID 去重并转换公告条目。"""
    seen: set[str] = set()
    items: list[NewsItem] = []
    for row in rows:
        news_id = str(row.get("NEWS_ID") or "").strip()
        if not news_id or news_id in seen:
            continue
        seen.add(news_id)
        published = parse_hk_time(row.get("DATE_TIME"))
        file_link = str(row.get("FILE_LINK") or "").strip()
        if not published or not file_link:
            continue
        items.append(
            NewsItem(
                title=html.unescape(
                    str(row.get("TITLE") or row.get("LONG_TEXT") or "HKEX announcement")
                ),
                publisher="Hong Kong Exchanges and Clearing",
                link=str(httpx.URL(_BASE_URL).join(file_link)),
                published_at=published,
                kind="disclosure",
                source_id=news_id,
                source_name="hkexnews",
                source_tier="official",
                fetched_at=fetched_at,
                market="hk",
                symbols=[query.symbol] if query.symbol else [],
                language=str(row.get("_language") or ""),
            )
        )
    return items


def parse_hk_time(value: Any) -> datetime | None:
    """把 HKEX ``DD/MM/YYYY HH:MM`` 香港时间转成 UTC。"""
    match = re.match(r"^(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2})$", str(value or ""))
    if not match:
        return None
    source = datetime(
        int(match[3]),
        int(match[2]),
        int(match[1]),
        int(match[4]),
        int(match[5]),
        tzinfo=ZoneInfo("Asia/Hong_Kong"),
    )
    return source.astimezone(UTC)
