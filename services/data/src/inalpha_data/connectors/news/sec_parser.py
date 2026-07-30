"""SEC submissions JSON 转统一披露事件。"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ...news_models import NewsItem, NewsQuery

_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"


def parse_submissions(
    payload: dict[str, Any], query: NewsQuery, fetched_at: datetime, cik: str
) -> list[NewsItem]:
    """把 submissions.recent 的并行数组转成披露事件。"""
    recent = payload.get("filings", {}).get("recent", {})
    if not isinstance(recent, dict):
        return []
    accessions = recent.get("accessionNumber", [])
    items: list[NewsItem] = []
    for index, accession in enumerate(accessions):
        if not accession:
            continue
        accepted = _parse_datetime(_at(recent, "acceptanceDateTime", index))
        published = accepted or _parse_datetime(_at(recent, "filingDate", index))
        primary = str(_at(recent, "primaryDocument", index) or "")
        form = str(_at(recent, "form", index) or "Filing")
        accession_path = str(accession).replace("-", "")
        link = f"{_ARCHIVES_URL}/{int(cik)}/{accession_path}/{primary}" if primary else ""
        items.append(
            NewsItem(
                title=f"SEC {form}: {payload.get('name') or query.symbol}",
                publisher="U.S. Securities and Exchange Commission",
                link=link,
                published_at=published,
                accepted_at=accepted,
                summary=f"Official SEC filing {form}; primary document: {primary}",
                kind="disclosure",
                source_id=str(accession),
                source_name="sec_edgar",
                source_tier="official",
                fetched_at=fetched_at,
                market="us",
                symbols=[query.symbol] if query.symbol else [],
                language="en",
            )
        )
    return items


def _at(data: dict[str, Any], key: str, index: int) -> Any:
    values = data.get(key)
    return values[index] if isinstance(values, list) and index < len(values) else None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
