"""run 执行期限、终态与遗留 slot 的可重试收口。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from inalpha_shared.db import get_conn

from ..owner_llm import CredentialTemporarilyUnavailable
from ..storage import candidates, runs
from .executor import execute_run


async def execute_managed(
    run: dict[str, Any],
    *,
    mutator: Any,
    settings: Any,
    should_stop: Callable[[], bool],
    on_error: Callable[[str], None],
    on_success: Callable[[], None],
) -> None:
    """执行一个 run，并保证取消、失败和总超时都进入终态。"""
    timeout = asyncio.timeout(float(getattr(settings, "evolver_run_timeout_s", 1200)))
    try:
        async with timeout:
            await execute_run(run, mutator=mutator, settings=settings)
    except asyncio.CancelledError:
        await _finalize(
            run["run_id"],
            aborted=True,
            error=None,
            should_stop=should_stop,
            on_error=on_error,
            on_success=on_success,
        )
        raise
    except TimeoutError as exc:
        error = (
            _RunTimeoutError("evolution run exceeded its total deadline")
            if timeout.expired()
            else exc
        )
        await _finalize(
            run["run_id"],
            aborted=False,
            error=error,
            should_stop=should_stop,
            on_error=on_error,
            on_success=on_success,
        )
    except CredentialTemporarilyUnavailable:
        await asyncio.sleep(2.0)
        async with get_conn() as conn:
            await runs.transition(
                conn,
                run["run_id"],
                from_statuses=("running",),
                to_status="queued",
                values={
                    "active_stage": None,
                    "started_at": None,
                    "failure_code": None,
                    "failure_message": None,
                },
            )
    except Exception as exc:
        await _finalize(
            run["run_id"],
            aborted=False,
            error=exc,
            should_stop=should_stop,
            on_error=on_error,
            on_success=on_success,
        )


async def _finalize(
    run_id: UUID,
    *,
    aborted: bool,
    error: BaseException | None,
    should_stop: Callable[[], bool],
    on_error: Callable[[str], None],
    on_success: Callable[[], None],
) -> None:
    status = "aborted" if aborted else "failed"
    code = (
        "EVOLUTION_ABORTED" if aborted else str(getattr(error, "code", "EVOLUTION_INTERNAL_ERROR"))
    )
    message = "run cancelled" if aborted else str(error)[:1000]
    values = {
        "active_stage": status,
        "finished_at": datetime.now(UTC),
        "failure_code": code,
        "failure_message": message,
    }
    delay = 0.1
    while True:
        try:
            async with get_conn() as conn:
                await candidates.close_pending(
                    conn,
                    run_id,
                    error_code=code,
                    error_message=message,
                )
                await runs.transition(
                    conn,
                    run_id,
                    from_statuses=("running", "cancelling") if aborted else ("running",),
                    to_status=status,
                    values=values,
                )
            on_success()
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            on_error(f"finalize {run_id} failed: {type(exc).__name__}: {exc}")
            if should_stop():
                return
            await asyncio.sleep(delay)
            delay = min(delay * 2, 5.0)


class _RunTimeoutError(TimeoutError):
    code = "EVOLUTION_RUN_TIMEOUT"


__all__ = ["execute_managed"]
