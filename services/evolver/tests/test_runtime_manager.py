"""EvolutionRunManager 状态收口测试。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from inalpha_evolver.runtime.manager import EvolutionRunManager


class FakeContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_args):
        return None


@pytest.mark.asyncio
async def test_execute_failure_is_persisted(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = EvolutionRunManager(
        mutator=object(),
        settings=SimpleNamespace(evolver_max_running_runs=1),  # type: ignore[arg-type]
    )
    calls = []

    async def fail(*_args, **_kwargs):
        raise RuntimeError("boom")

    async def transition(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr("inalpha_evolver.runtime.manager.execute_run", fail)
    monkeypatch.setattr("inalpha_evolver.runtime.manager.get_conn", lambda: FakeContext())
    monkeypatch.setattr("inalpha_evolver.runtime.manager.runs.transition", transition)
    run_id = uuid4()
    await manager._execute({"run_id": run_id})

    assert calls[0][1]["to_status"] == "failed"
    assert calls[0][1]["values"]["failure_code"] == "EVOLUTION_INTERNAL_ERROR"


@pytest.mark.asyncio
async def test_cancelled_run_becomes_aborted(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = EvolutionRunManager(
        mutator=object(),
        settings=SimpleNamespace(evolver_max_running_runs=1),  # type: ignore[arg-type]
    )
    calls = []

    async def cancel(*_args, **_kwargs):
        raise asyncio.CancelledError

    async def transition(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr("inalpha_evolver.runtime.manager.execute_run", cancel)
    monkeypatch.setattr("inalpha_evolver.runtime.manager.get_conn", lambda: FakeContext())
    monkeypatch.setattr("inalpha_evolver.runtime.manager.runs.transition", transition)
    with pytest.raises(asyncio.CancelledError):
        await manager._execute({"run_id": uuid4()})

    assert calls[0][1]["to_status"] == "aborted"
