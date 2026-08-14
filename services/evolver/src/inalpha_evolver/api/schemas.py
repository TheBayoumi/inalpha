"""Evolver API 请求与响应模型。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class EvolutionConfig(BaseModel):
    venue: str = Field(min_length=1, max_length=40)
    symbol: str = Field(min_length=1, max_length=80)
    timeframe: str = Field(pattern=r"^\d+(m|h|d|wk|mo)$")
    from_ts: datetime
    as_of: datetime
    initial_cash: float = Field(default=10_000.0, ge=100)
    fee_rate: float = Field(default=0.001, ge=0, le=0.1)
    validation_split: float = Field(default=0.3, ge=0, le=0.5)

    @model_validator(mode="after")
    def validate_window(self) -> EvolutionConfig:
        if self.from_ts >= self.as_of:
            raise ValueError("from_ts must be earlier than as_of")
        if self.as_of - self.from_ts > timedelta(days=3650):
            raise ValueError("evolution window cannot exceed 10 years")
        return self


class StartRunRequest(BaseModel):
    seed_strategy_id: str = Field(default="sma_cross_v1", max_length=128)
    budget: int = Field(default=4, ge=1, le=20)
    config: EvolutionConfig


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
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RunStatusResponse(BaseModel):
    run_id: UUID
    seed_strategy_id: str
    budget: int
    config: dict[str, Any]
    status: str
    active_stage: str | None = None
    llm_cost_usd: float = 0.0
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    dataset_manifest: dict[str, Any] | None = None
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
