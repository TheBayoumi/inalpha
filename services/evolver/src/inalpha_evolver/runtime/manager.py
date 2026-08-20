"""数据库队列驱动的 E1 run manager。"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from inalpha_shared.db import get_conn

from ..config import EvolverSettings
from ..storage import run_queries
from .dispatcher import dispatch_runs
from .finalizer import execute_managed


class EvolutionRunManager:
    def __init__(self, *, mutator: Any, settings: EvolverSettings) -> None:
        self.mutator = mutator
        self.settings = settings
        self.tasks: dict[UUID, asyncio.Task[None]] = {}
        self.wake = asyncio.Event()
        self.dispatcher: asyncio.Task[None] | None = None
        self.semaphore = asyncio.Semaphore(settings.evolver_max_running_runs)
        self.closing = False
        self.unhealthy_reason: str | None = None

    @property
    def healthy(self) -> bool:
        """dispatcher 存活且没有尚未恢复的队列或终态写入错误。"""
        return bool(
            self.dispatcher and not self.dispatcher.done() and self.unhealthy_reason is None
        )

    async def start(self) -> None:
        async with get_conn() as conn:
            await run_queries.reconcile_interrupted(conn)
        self.dispatcher = asyncio.create_task(dispatch_runs(self), name="evo-dispatch")

    async def notify_async(self) -> None:
        self.wake.set()

    async def abort(self, run_id: UUID) -> None:
        task = self.tasks.get(run_id)
        if task is not None and task.cancelling() == 0:
            task.cancel()

    async def close(self) -> None:
        self.closing = True
        self.wake.set()
        if self.dispatcher:
            self.dispatcher.cancel()
        tasks = list(self.tasks.values())
        for task in tasks:
            if task.cancelling() == 0:
                task.cancel()
        pending = tasks + ([self.dispatcher] if self.dispatcher else [])
        await asyncio.gather(*pending, return_exceptions=True)
        close = getattr(getattr(self.mutator, "llm_client", None), "close", None)
        if close is not None:
            await close()

    async def _execute(self, run: dict[str, Any]) -> None:
        await execute_managed(
            run,
            mutator=self.mutator,
            settings=self.settings,
            should_stop=lambda: self.closing,
            on_error=lambda reason: setattr(self, "unhealthy_reason", reason),
            on_success=lambda: setattr(self, "unhealthy_reason", None),
        )

    def _done(self, run_id: UUID, task: asyncio.Task[None]) -> None:
        self.tasks.pop(run_id, None)
        self.semaphore.release()
        self.wake.set()
        if not task.cancelled():
            task.exception()


__all__ = ["EvolutionRunManager"]
