"""终态写入重试测试。"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from inalpha_evolver.owner_llm import CredentialTemporarilyUnavailable
from inalpha_evolver.runtime.finalizer import execute_managed


class _Connection:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_args):
        return None


@pytest.mark.asyncio
async def test_finalizer_retries_transient_db_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0
    unhealthy: list[str] = []

    async def fail_run(*_args, **_kwargs):
        raise RuntimeError("run failed")

    async def close_pending(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("db unavailable")
        return 0

    async def transition(*_args, **_kwargs):
        return {}

    async def no_delay(_seconds):
        return None

    monkeypatch.setattr("inalpha_evolver.runtime.finalizer.execute_run", fail_run)
    monkeypatch.setattr("inalpha_evolver.runtime.finalizer.get_conn", lambda: _Connection())
    monkeypatch.setattr("inalpha_evolver.runtime.finalizer.candidates.close_pending", close_pending)
    monkeypatch.setattr("inalpha_evolver.runtime.finalizer.runs.transition", transition)
    monkeypatch.setattr("inalpha_evolver.runtime.finalizer.asyncio.sleep", no_delay)

    await execute_managed(
        {"run_id": uuid4()},
        mutator=object(),
        settings=SimpleNamespace(evolver_run_timeout_s=10),
        should_stop=lambda: False,
        on_error=unhealthy.append,
        on_success=lambda: None,
    )

    assert attempts == 2
    assert unhealthy and "db unavailable" in unhealthy[0]


@pytest.mark.asyncio
async def test_temporary_credential_failure_requeues_without_terminal_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transitions: list[dict[str, object]] = []
    unhealthy: list[str] = []

    async def unavailable(*_args, **_kwargs):
        raise CredentialTemporarilyUnavailable("dashboard starting")

    async def transition(*_args, **kwargs):
        if not transitions:
            transitions.append({"failed_attempt": True})
            raise RuntimeError("db temporarily unavailable")
        transitions.append(kwargs)
        return {}

    async def no_delay(_seconds):
        return None

    monkeypatch.setattr("inalpha_evolver.runtime.finalizer.execute_run", unavailable)
    monkeypatch.setattr("inalpha_evolver.runtime.finalizer.get_conn", lambda: _Connection())
    monkeypatch.setattr("inalpha_evolver.runtime.finalizer.runs.transition", transition)
    monkeypatch.setattr("inalpha_evolver.runtime.finalizer.asyncio.sleep", no_delay)

    await execute_managed(
        {"run_id": uuid4()},
        mutator=None,
        settings=SimpleNamespace(evolver_run_timeout_s=10),
        should_stop=lambda: False,
        on_error=unhealthy.append,
        on_success=lambda: None,
    )

    assert len(transitions) == 2
    assert transitions[1]["to_status"] == "queued"
    assert transitions[1]["values"] == {
        "active_stage": None,
        "started_at": None,
        "failure_code": None,
        "failure_message": None,
    }
    assert unhealthy and "db temporarily unavailable" in unhealthy[0]
