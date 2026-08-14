"""演化 slot 的准备、评估与持久化。"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from inalpha_paper.strategy_preparation import prepare_strategy_source
from inalpha_shared.db import get_conn

from ..evaluator.frozen import FrozenDatasetEvaluator
from ..storage import candidates


async def persist_mutation(
    run_id: UUID,
    slot: int,
    mutation: Any,
) -> str | None:
    """校验变异；失败落终态，成功落源码并返回。"""
    if mutation.unified_diff is None:
        await reject_slot(run_id, slot, "no_change", None)
        return None
    try:
        prepared = prepare_strategy_source(mutation.new_source)
    except Exception as exc:
        code = getattr(exc, "code", "EVOLUTION_AST_REJECTED")
        outcome = "contract_rejected" if "CONTRACT" in code else "ast_rejected"
        await reject_slot(run_id, slot, outcome, exc)
        return None
    async with get_conn() as conn:
        if await candidates.source_exists(conn, run_id, mutation.source_hash):
            await candidates.update_slot(
                conn,
                run_id,
                slot,
                stage="completed",
                outcome="duplicate",
                unified_diff=mutation.unified_diff,
                llm_cost_usd=mutation.llm_cost_usd,
                cache_hit_tokens=mutation.cache_hit_tokens,
            )
            return None
        await candidates.update_slot(
            conn,
            run_id,
            slot,
            stage="evaluation",
            source_code=prepared.source_code,
            source_hash=mutation.source_hash,
            unified_diff=mutation.unified_diff,
            llm_cost_usd=mutation.llm_cost_usd,
            cache_hit_tokens=mutation.cache_hit_tokens,
            audit_snapshot={"ok": True},
            contract_snapshot={"ok": True, "class_name": prepared.class_name},
        )
    return prepared.source_code


async def evaluate_slot(
    run_id: UUID,
    slot: int,
    source: str,
    evaluator: FrozenDatasetEvaluator,
) -> None:
    try:
        result = await evaluator.evaluate(source)
    except Exception as exc:
        await reject_slot(run_id, slot, "evaluation_failed", exc)
        return
    async with get_conn() as conn:
        await candidates.update_slot(
            conn,
            run_id,
            slot,
            stage="completed",
            outcome="succeeded",
            fitness=result.fitness,
            evaluation_snapshot=result.report,
            report=result.report,
            data_epoch=result.data_epoch,
            overfitting_risk=result.overfitting_risk,
        )


async def reject_slot(
    run_id: UUID,
    slot: int,
    outcome: str,
    error: BaseException | None,
) -> None:
    async with get_conn() as conn:
        await candidates.update_slot(
            conn,
            run_id,
            slot,
            stage="completed",
            outcome=outcome,
            error_code=getattr(error, "code", None),
            error_message=str(error)[:1000] if error else None,
        )
