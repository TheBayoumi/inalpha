"""财经新闻 provider 的共享类型与错误分类。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, Protocol

from ...news_models import NewsItem, NewsQuery, ProviderStatusCode


@dataclass(slots=True)
class ProviderResult:
    """单个 provider 的标准化返回。"""

    provider: str
    status: ProviderStatusCode
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    items: list[NewsItem] = field(default_factory=list)
    error: str | None = None
    coverage: Literal["complete", "snapshot_only"] = "complete"


class NewsProvider(Protocol):
    """新闻 provider 的最小接口。"""

    name: str
    coverage: Literal["complete", "snapshot_only"]

    def supports(self, query: NewsQuery) -> bool:
        """当前 provider 是否真实覆盖查询 scope。"""
        ...

    async def fetch(self, query: NewsQuery) -> ProviderResult:
        """拉取并标准化当前 provider 能覆盖的事件。"""
        ...

    async def close(self) -> None:
        """释放底层资源。"""
        ...
