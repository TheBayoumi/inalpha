"""冻结行情的可复核 manifest。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from inalpha_paper.model.data import Bar


class BackfillSnapshot(BaseModel):
    """data-service 原样返回的回填审计证据。"""

    model_config = ConfigDict(frozen=True)
    venue: str
    symbol: str
    timeframe: str
    bars_fetched: int = Field(ge=0)
    bars_inserted: int = Field(ge=0)
    from_ts: datetime
    to_ts: datetime


class DatasetManifest(BaseModel):
    """一次演化运行唯一使用的数据集身份。"""

    model_config = ConfigDict(frozen=True)
    schema_version: Literal["e1.dataset.v2"] = "e1.dataset.v2"
    venue: str
    symbol: str
    requested_timeframe: str
    data_timeframe: str
    canonical_timeframe: str
    requested_from: datetime
    requested_as_of: datetime
    effective_from: datetime
    effective_to: datetime
    latest_bar_ts: datetime
    cutoff_bar_ts: datetime
    freshness_lag_seconds: float = Field(ge=0)
    data_epoch: int = Field(ge=0)
    bar_count: int = Field(ge=2, le=10_000)
    annualization_periods: int = Field(gt=0)
    calendar_code: str | None
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    hash_algorithm: Literal["sha256:e1-bars-v1"] = "sha256:e1-bars-v1"
    backfill: BackfillSnapshot
    warnings: list[str] = Field(default_factory=list, max_length=20)


@dataclass(frozen=True, slots=True)
class FrozenDataset:
    """不可变 bars 与其 manifest。"""

    bars: tuple[Bar, ...]
    manifest: DatasetManifest


__all__ = ["BackfillSnapshot", "DatasetManifest", "FrozenDataset"]
