"""Evolver API 请求与响应模型。"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator
from pydantic_core import PydanticCustomError

from ..data.datetime_policy import MAX_AS_OF_CLOCK_SKEW
from ..data.manifest import DatasetManifest


class EvolutionConfig(BaseModel):
    venue: str = Field(min_length=1, max_length=40)
    symbol: str = Field(min_length=1, max_length=80)
    timeframe: str = Field(pattern=r"^\d+(m|h|d|wk|mo)$")
    from_ts: datetime
    as_of: datetime
    initial_cash: float = Field(default=10_000.0, ge=100)
    fee_rate: float = Field(default=0.001, ge=0, le=0.1)
    validation_split: float = Field(default=0.3, ge=0, le=0.5)

    @field_validator("from_ts", "as_of")
    @classmethod
    def normalize_datetimes(cls, value: datetime, info: ValidationInfo) -> datetime:
        """拒绝无时区 cutoff，其余时间统一为 UTC。"""
        if value.tzinfo is None:
            if info.field_name == "as_of":
                raise ValueError("as_of must be timezone-aware")
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_window(self) -> EvolutionConfig:
        if self.as_of > datetime.now(UTC) + MAX_AS_OF_CLOCK_SKEW:
            raise ValueError("as_of exceeds trusted current time")
        if self.from_ts >= self.as_of:
            raise ValueError("from_ts must be earlier than as_of")
        if self.as_of - self.from_ts > timedelta(days=3650):
            raise ValueError("evolution window cannot exceed 10 years")
        return self


class EvolutionPricingSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1, max_length=80)
    currency: Literal["USD"]
    input_usd_per_million: float = Field(gt=0)
    output_usd_per_million: float = Field(gt=0)
    assumed_input_tokens: int = Field(gt=0, le=1_000_000)
    max_output_tokens: int = Field(gt=0, le=100_000)
    estimated_max_usd_per_candidate: float = Field(gt=0)


class EvolutionLLMSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config_id: str = Field(min_length=1, max_length=128)
    provider: Literal["deepseek", "openai", "kimi", "zhipu"]
    model: str = Field(min_length=1, max_length=160)
    base_url: str | None = Field(default=None, max_length=500)
    pricing: EvolutionPricingSnapshot
    config_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("LLM base_url must be an absolute HTTP URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("LLM base_url cannot contain credentials, query, or fragment")
        return value.rstrip("/")

    @model_validator(mode="after")
    def verify_config_digest(self) -> EvolutionLLMSnapshot:
        """拒绝任何未被 Mastra 审批摘要覆盖的快照字段变更。"""
        official_base_urls = {
            "deepseek": "https://api.deepseek.com",
            "openai": "https://api.openai.com/v1",
            "kimi": "https://api.moonshot.cn/v1",
            "zhipu": "https://open.bigmodel.cn/api/paas/v4",
        }
        if self.provider == "deepseek" and self.base_url == "https://api.deepseek.com/v1":
            self.base_url = "https://api.deepseek.com"
        if self.base_url != official_base_urls[self.provider]:
            raise PydanticCustomError(
                "llm_endpoint_unavailable",
                "evolution requires the official {provider} API endpoint",
                {"provider": self.provider},
            )
        priced_models = {
            "deepseek": ("deepseek-v4-pro", 0.56, 1.68),
            "openai": ("gpt-5.5", 5.0, 15.0),
            "kimi": ("kimi-k2.6", 0.6, 2.5),
            "zhipu": ("glm-5.2", 0.7, 2.8),
        }
        expected_model, expected_input_rate, expected_output_rate = priced_models[self.provider]
        pricing = self.pricing
        expected_max = (
            pricing.assumed_input_tokens * expected_input_rate
            + pricing.max_output_tokens * expected_output_rate
        ) / 1_000_000
        if (
            self.model != expected_model
            or pricing.version != "provider-estimate-2026-08"
            or pricing.assumed_input_tokens != 24_000
            or pricing.max_output_tokens != 8_192
            or pricing.input_usd_per_million != expected_input_rate
            or pricing.output_usd_per_million != expected_output_rate
            or abs(pricing.estimated_max_usd_per_candidate - expected_max) > 1e-12
        ):
            raise PydanticCustomError(
                "llm_pricing_unavailable",
                "evolution pricing is unavailable for model {provider}/{model}",
                {"provider": self.provider, "model": self.model},
            )
        expected = compute_llm_config_digest(self)
        if not hmac.compare_digest(self.config_digest, expected):
            raise PydanticCustomError(
                "llm_snapshot_digest",
                "LLM config_digest does not match the frozen snapshot",
            )
        return self


def compute_llm_config_digest(snapshot: EvolutionLLMSnapshot) -> str:
    """按与 TypeScript 相同的字段顺序和数字文本计算跨语言摘要。"""
    pricing = snapshot.pricing
    canonical = [
        snapshot.config_id,
        snapshot.provider,
        snapshot.model,
        snapshot.base_url,
        pricing.version,
        pricing.currency,
        _number_text(pricing.input_usd_per_million),
        _number_text(pricing.output_usd_per_million),
        _number_text(pricing.assumed_input_tokens),
        _number_text(pricing.max_output_tokens),
        _number_text(pricing.estimated_max_usd_per_candidate),
    ]
    encoded = json.dumps(canonical, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _number_text(value: int | float) -> str:
    text = format(Decimal(str(value)), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


class StartRunRequest(BaseModel):
    seed_strategy_id: str = Field(default="sma_cross_v1", max_length=128)
    budget: int = Field(default=4, ge=1, le=20)
    config: EvolutionConfig
    llm: EvolutionLLMSnapshot


class CandidateResponse(BaseModel):
    candidate_id: UUID
    run_id: UUID
    slot: int
    generation: int
    stage: str
    outcome: str
    source_code: str | None = None
    source_hash: str | None = None
    unified_diff: str | None = None
    mutation_hint: str | None = None
    llm_cost_usd: float | None = None
    fitness: float | None = None
    evaluation_snapshot: dict[str, Any] | None = None
    audit_snapshot: dict[str, Any] | None = None
    contract_snapshot: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    overfitting_risk: str = "high"
    data_epoch: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RunStatusResponse(BaseModel):
    run_id: UUID
    seed_strategy_id: str
    budget: int
    config: dict[str, Any]
    llm_snapshot: EvolutionLLMSnapshot | None = None
    llm_config_digest: str | None = None
    status: str
    active_stage: str | None = None
    llm_cost_usd: float = 0.0
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    dataset_manifest: DatasetManifest | None = None
    seed_report_snapshot: dict[str, Any] | None = None
    baseline_snapshot: dict[str, Any] | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    attempted: int = 0
    succeeded: int = 0
    rejected: int = 0
    candidates: list[CandidateResponse] = Field(default_factory=list)


class RunListResponse(BaseModel):
    items: list[RunStatusResponse]
    next_cursor: str | None = None
