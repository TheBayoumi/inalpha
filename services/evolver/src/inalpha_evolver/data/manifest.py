"""冻结行情的可复核 manifest。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from inalpha_paper.model.data import Bar


class DatasetManifest(BaseModel):
    """一次演化运行唯一使用的数据集身份。"""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["e1.dataset.v1"] = "e1.dataset.v1"
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
    bar_count: int = Field(ge=2, le=10_000)
    freshness_lag_seconds: float = Field(ge=0)
    annualization_periods: int = Field(gt=0)
    calendar_code: str | None
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    hash_algorithm: Literal["sha256:e1-bars-v1"] = "sha256:e1-bars-v1"
    backfill: dict[str, Any]
    warnings: list[str] = Field(default_factory=list, max_length=20)


@dataclass(frozen=True, slots=True)
class FrozenDataset:
    """不可变 bars 与其 manifest。"""

    bars: tuple[Bar, ...]
    manifest: DatasetManifest


__all__ = ["DatasetManifest", "FrozenDataset"]
