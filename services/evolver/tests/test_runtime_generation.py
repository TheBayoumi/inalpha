"""seed/baseline 并行评估收口测试。"""

from __future__ import annotations

import asyncio

import pytest

from inalpha_evolver.runtime.generation import _evaluate_seed_and_baseline


class _FailingEvaluator:
    def __init__(self) -> None:
        self.baseline_cancelled = asyncio.Event()

    async def evaluate(self, _source: str):
        await asyncio.sleep(0)
        raise RuntimeError("seed failed")

    async def evaluate_baseline(self):
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            self.baseline_cancelled.set()
            raise


@pytest.mark.asyncio
async def test_seed_failure_cancels_and_awaits_baseline() -> None:
    evaluator = _FailingEvaluator()

    with pytest.raises(RuntimeError, match="seed failed"):
        await _evaluate_seed_and_baseline(evaluator, "source")  # type: ignore[arg-type]

    assert evaluator.baseline_cancelled.is_set()
