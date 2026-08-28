"""Hypothesis DSL, statistical selection, and event-study unit tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from inalpha_paper.strategy_authoring import audit_strategy_code, load_strategy_class
from inalpha_shared_llm.types import CacheMetrics, MutationResponse

from inalpha_evolver.hypothesis.compiler import (
    canonical_spec_hash,
    compile_hypothesis,
    expand_implementations,
)
from inalpha_evolver.hypothesis.models import HypothesisSpec
from inalpha_evolver.hypothesis.proposer import propose_generation
from inalpha_evolver.hypothesis.selection import (
    HypothesisScore,
    benjamini_hochberg,
    plan_next_generation,
)
from inalpha_evolver.mutator import Mutator
from inalpha_evolver.runtime.campaign import _clone, _mutate


def _spec() -> HypothesisSpec:
    return HypothesisSpec(
        lane="event",
        thesis="交易所上币后价格发现可能延迟，成交量确认能够过滤虚假反应。",
        evidence_ids=["fact-1:0"],
        event_types=["listing"],
        assets=["BTC"],
        direction="long",
        trigger_mode="confirmed",
    )


def test_strong_event_expands_to_three_auditable_ablation_arms() -> None:
    spec = _spec()
    arms = expand_implementations(spec)
    assert [item.trigger_mode for item in arms] == ["direct", "confirmed", "hybrid"]
    for arm in arms:
        compiled = compile_hypothesis(arm)
        assert audit_strategy_code(compiled.source_code).ok
        assert load_strategy_class(compiled.source_code).__name__.startswith("EventHypothesis_")


def test_spec_hash_ignores_storage_identity_but_not_mechanism() -> None:
    spec = _spec()
    clone = spec.model_copy(update={"hypothesis_id": uuid4()})
    changed = clone.model_copy(update={"direction": "short"})
    assert canonical_spec_hash(spec) == canonical_spec_hash(clone)
    assert canonical_spec_hash(spec) != canonical_spec_hash(changed)


def test_generation_plan_has_fixed_2_4_1_1_topology() -> None:
    scores = [
        HypothesisScore(
            hypothesis_id=uuid4(),
            lane="event" if index < 4 else "regime",
            event_family=f"family-{index}",
            trigger_mode="confirmed",
            credit=float(index),
            objectives=(float(index), -index, 0.5, 0.2, 0.8, index / 10),
        )
        for index in range(8)
    ]
    plan = plan_next_generation(scores, seed=7)
    assert len(plan.elites) == 2
    assert len(plan.mutation_parents) == 4
    assert len(plan.crossover_parents) == 2
    assert plan.restart_slots == 1


def test_restart_parent_becomes_a_regular_lane_when_inherited() -> None:
    restart = HypothesisSpec(
        lane="restart",
        lineage_kind="restart",
        thesis="随机重启探索安全事件冲击后的延迟价格反应与成交量确认机制。",
        event_types=["exploit"],
        direction="short",
        trigger_mode="confirmed",
    )

    elite = _clone(
        restart,
        lineage_kind="elite",
        parent_ids=[restart.hypothesis_id],
    )
    mutation = _mutate(restart, 0, lineage_kind="mutation")

    assert elite.lane == "event"
    assert elite.lineage_kind == "elite"
    assert mutation.lane == "event"
    assert mutation.lineage_kind == "mutation"


def test_benjamini_hochberg_controls_the_whole_generation() -> None:
    assert benjamini_hochberg([0.001, 0.01, 0.04, 0.2], q=0.05) == [True, True, False, False]


class _ProposalClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    async def mutate(self, _request: object) -> MutationResponse:
        self.calls += 1
        return MutationResponse(
            content=self.content,
            cache_metrics=CacheMetrics(input_tokens=100, output_tokens=40),
        )

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_agent_proposer_uses_exactly_two_calls_and_preserves_platform_evidence() -> None:
    client = _ProposalClient(
        """[
        {"thesis":"事件发生后流动性重定价可能形成可证伪的延迟价格反应","trigger_mode":"confirmed"},
        {"thesis":"重大事件冲击可能存在需要成交量确认的延迟反应窗口","trigger_mode":"hybrid"},
        {"thesis":"高置信事件的价格反应持续时间可能显著长于低置信事件"},
        {"thesis":"使用波动状态约束事件触发条件可能减少无效交易和误报"}
        ]"""
    )
    scaffolds = [
        _spec().model_copy(
            update={
                "hypothesis_id": uuid4(),
                "evidence_ids": [f"fact-{index}:0"],
                "lane": "event" if index < 4 else "event_regime",
            }
        )
        for index in range(8)
    ]
    result = await propose_generation(
        Mutator(
            llm_client=client,  # type: ignore[arg-type]
            input_usd_per_million=1.0,
            output_usd_per_million=2.0,
        ),
        generation=1,
        scaffolds=scaffolds,
        feedback=[],
    )

    assert client.calls == 2
    assert len(result.hypotheses) == 8
    assert result.fallback_calls == 0
    assert result.cost_usd == pytest.approx(0.00036)
    assert [item.evidence_ids for item in result.hypotheses] == [
        item.evidence_ids for item in scaffolds
    ]
    assert [item.lane for item in result.hypotheses] == [item.lane for item in scaffolds]


@pytest.mark.asyncio
async def test_invalid_agent_batches_fall_back_without_losing_direction_coverage() -> None:
    client = _ProposalClient("not-json")
    scaffolds = [_spec().model_copy(update={"hypothesis_id": uuid4()}) for _ in range(8)]

    result = await propose_generation(
        Mutator(llm_client=client),  # type: ignore[arg-type]
        generation=2,
        scaffolds=scaffolds,
        feedback=[{"selected": True}],
    )

    assert client.calls == 2
    assert result.fallback_calls == 2
    assert result.hypotheses == tuple(scaffolds)
