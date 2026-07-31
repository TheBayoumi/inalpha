"""统一财经新闻的数据契约。"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

NewsKind = Literal["market_news", "media", "disclosure"]
SourceTier = Literal["official", "professional_media", "aggregator"]
ProviderStatusCode = Literal[
    "ok", "no_results", "timeout", "rate_limited", "upstream_error", "unsupported"
]


class NewsQuery(BaseModel):
    """``GET /news`` 查询参数；兼容旧 ``venue + symbol`` 调用。"""

    venue: str | None = Field(default=None)
    market: str | None = Field(default=None)
    symbol: str | None = Field(default=None)
    as_of: datetime | None = Field(default=None)
    since: datetime | None = Field(default=None)
    kinds: list[NewsKind] | None = Field(default=None)
    language: str | None = Field(default=None, max_length=35)
    limit: int = Field(default=10, ge=1, le=50)

    @field_validator("kinds", mode="before")
    @classmethod
    def split_kinds(cls, value: object) -> object:
        """兼容 HTTP client 发送的逗号分隔 kinds。"""
        values = [value] if isinstance(value, str) else value
        if not isinstance(values, list):
            return values
        return [part.strip() for item in values for part in str(item).split(",") if part.strip()]

    @field_validator("as_of", "since", mode="after")
    @classmethod
    def assume_utc_if_naive(cls, value: datetime | None) -> datetime | None:
        """与 bars 契约一致：无时区输入按 UTC 解释。"""
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_scope(self) -> NewsQuery:
        """要求 market 或 symbol 至少存在一个，并校验时间窗口。"""
        if not self.market and not self.symbol:
            raise ValueError("market or symbol is required")
        if self.since and self.as_of and self.since > self.as_of:
            raise ValueError("since must not be later than as_of")
        return self


class NewsItem(BaseModel):
    """标准化新闻或披露事件。"""

    title: str
    publisher: str = ""
    link: str = ""
    published_at: datetime | None = None
    summary: str = ""
    kind: NewsKind = "media"
    source_id: str = ""
    source_name: str = ""
    source_tier: SourceTier = "aggregator"
    fetched_at: datetime | None = None
    accepted_at: datetime | None = None
    market: str | None = None
    symbols: list[str] = Field(default_factory=list)
    language: str | None = None
    alternative_sources: list[str] = Field(default_factory=list)


class NewsProviderStatus(BaseModel):
    """单个 provider 的可观察结果。"""

    provider: str
    status: ProviderStatusCode
    error: str | None = None
    fetched_at: datetime
    item_count: int = 0
    coverage: Literal["complete", "snapshot_only"] = "complete"


class NewsResponse(BaseModel):
    """统一新闻响应，保留旧 venue/symbol 字段。"""

    venue: str | None = None
    market: str | None = None
    symbol: str | None = None
    as_of: datetime | None = None
    since: datetime | None = None
    fetched_at: datetime
    items: list[NewsItem] = Field(default_factory=list)
    providers: list[NewsProviderStatus] = Field(default_factory=list)
    is_partial: bool = False
    coverage_complete: bool = True
