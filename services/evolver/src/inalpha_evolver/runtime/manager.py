from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from inalpha_shared.db import get_conn

from ..config import EvolverSettings
from ..storage import run_queries, runs
from .executor import execute_run


class EvolutionRunManager:
    def __init__(self, *, mutator: Any, settings: EvolverSettings) -> None:
        self.mutator = mutator
        self.settings = settings
        self.tasks: dict[UUID, asyncio.Task[None]] = {}
        self.wake = asyncio.Event()
        self.dispatcher: asyncio.Task[None] | None = None
        self.semaphore = asyncio.Semaphore(settings.evolver_max_running_runs)
        self.closing = False
    async def start(self) -> None:
        async with get_conn() as conn:
            await run_queries.reconcile_interrupted(conn)
        self.dispatcher = asyncio.create_task(self._dispatch(), name="evo-dispatch")
    async def notify_async(self) -> None:
        self.wake.set()
    async def abort(self, run_id: UUID) -> None:
        task = self.tasks.get(run_id)
        if task is not None:
            task.cancel()
    async def close(self) -> None:
        self.closing = True
        self.wake.set()
        if self.dispatcher:
            self.dispatcher.cancel()
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        pending = tasks + ([self.dispatcher] if self.dispatcher else [])
        await asyncio.gather(*pending, return_exceptions=True)
        close = getattr(getattr(self.mutator, "llm_client", None), "close", None)
        if close is not None:
            await close()
    async def _dispatch(self) -> None:
        while not self.closing:
            await self.semaphore.acquire()
            async with get_conn() as conn:
                run = await run_queries.claim_next(conn)
            if run is None:
                self.semaphore.release()
                self.wake.clear()
                try:
                    await asyncio.wait_for(self.wake.wait(), timeout=1.0)
                except TimeoutError:
                    pass
                continue
            task = asyncio.create_task(self._execute(run), name=f"evo-{run['run_id']}")
            self.tasks[run["run_id"]] = task
            task.add_done_callback(lambda done, rid=run["run_id"]: self._done(rid, done))
    async def _execute(self, run: dict[str, Any]) -> None:
        try:
            await execute_run(run, mutator=self.mutator, settings=self.settings)
        except asyncio.CancelledError:
            await self._finish_cancelled(run["run_id"])
            raise
        except Exception as exc:
            await self._finish_failed(run["run_id"], exc)
    def _done(self, run_id: UUID, task: asyncio.Task[None]) -> None:
        self.tasks.pop(run_id, None)
        self.semaphore.release()
        self.wake.set()
        if not task.cancelled():
            task.exception()
    async def _finish_cancelled(self, run_id: UUID) -> None:
        async with get_conn() as conn:
            await runs.transition(
                conn,
                run_id,
                from_statuses=("running", "cancelling"),
                to_status="aborted",
                values={"active_stage": "aborted", "finished_at": datetime.now(UTC)},
            )
    async def _finish_failed(self, run_id: UUID, exc: Exception) -> None:
        async with get_conn() as conn:
            await runs.transition(
                conn,
                run_id,
                from_statuses=("running",),
                to_status="failed",
                values={
                    "active_stage": "failed",
                    "finished_at": datetime.now(UTC),
                    "failure_code": getattr(exc, "code", "EVOLUTION_INTERNAL_ERROR"),
                    "failure_message": str(exc)[:1000],
                },
            )
