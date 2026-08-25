"""EvolutionRunManager 状态收口与竞态测试。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from inalpha_evolver.runtime.dispatcher import dispatch_runs
from inalpha_evolver.runtime.manager import EvolutionRunManager


class FakeContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_args):
        return None


def _manager(*, timeout: float = 10.0) -> EvolutionRunManager:
    return EvolutionRunManager(
        mutator=object(),
        settings=SimpleNamespace(
            evolver_max_running_runs=1,
            evolver_run_timeout_s=timeout,
        ),  # type: ignore[arg-type]
    )


def _patch_finalizer(monkeypatch: pytest.MonkeyPatch, calls: list) -> None:
    async def close_pending(*_args, **kwargs):
        calls.append(("slots", kwargs))
        return 1

    async def transition(*_args, **kwargs):
        calls.append(("run", kwargs))
        return {}

    monkeypatch.setattr("inalpha_evolver.runtime.finalizer.get_conn", lambda: FakeContext())
    monkeypatch.setattr("inalpha_evolver.runtime.finalizer.candidates.close_pending", close_pending)
    monkeypatch.setattr("inalpha_evolver.runtime.finalizer.runs.transition", transition)


@pytest.mark.asyncio
async def test_execute_failure_closes_slots_and_run(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager()
    calls: list = []

    async def fail(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("inalpha_evolver.runtime.finalizer.execute_run", fail)
    _patch_finalizer(monkeypatch, calls)
    await manager._execute({"run_id": uuid4()})

    assert calls[0][0] == "slots"
    assert calls[1][1]["to_status"] == "failed"
    assert calls[1][1]["values"]["failure_code"] == "EVOLUTION_INTERNAL_ERROR"


@pytest.mark.asyncio
async def test_cancelled_run_becomes_aborted(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager()
    calls: list = []

    async def cancel(*_args, **_kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr("inalpha_evolver.runtime.finalizer.execute_run", cancel)
    _patch_finalizer(monkeypatch, calls)
    with pytest.raises(asyncio.CancelledError):
        await manager._execute({"run_id": uuid4()})

    assert calls[1][1]["to_status"] == "aborted"


@pytest.mark.asyncio
async def test_repeated_abort_only_cancels_once() -> None:
    manager = _manager()
    run_id = uuid4()
    task = asyncio.create_task(asyncio.sleep(10))
    manager.tasks[run_id] = task  # type: ignore[assignment]

    await manager.abort(run_id)
    await manager.abort(run_id)

    assert task.cancelling() == 1
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_dispatch_error_releases_permit(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager()

    async def fail_claim(_conn):
        raise RuntimeError("db down")

    async def stop_after_error(_delay):
        manager.closing = True

    monkeypatch.setattr("inalpha_evolver.runtime.dispatcher.get_conn", lambda: FakeContext())
    monkeypatch.setattr("inalpha_evolver.runtime.dispatcher.run_queries.claim_next", fail_claim)
    monkeypatch.setattr("inalpha_evolver.runtime.dispatcher.asyncio.sleep", stop_after_error)

    await dispatch_runs(manager)

    assert manager.semaphore._value == 1
    assert manager.unhealthy_reason and "db down" in manager.unhealthy_reason


@pytest.mark.asyncio
async def test_run_total_deadline_is_persisted(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager(timeout=0.001)
    calls: list = []

    async def hang(*_args, **_kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr("inalpha_evolver.runtime.finalizer.execute_run", hang)
    _patch_finalizer(monkeypatch, calls)
    await manager._execute({"run_id": uuid4()})

    assert calls[1][1]["values"]["failure_code"] == "EVOLUTION_RUN_TIMEOUT"
