"""E1 数据库队列 dispatcher。"""

from __future__ import annotations

import asyncio
from typing import Any

from inalpha_shared.db import get_conn

from ..storage import run_queries


async def dispatch_runs(manager: Any) -> None:
    """持续 claim queued run；暂时性 DB 异常不会杀死 dispatcher。"""
    delay = 0.1
    while not manager.closing:
        acquired = handed_off = False
        try:
            await manager.semaphore.acquire()
            acquired = True
            async with get_conn() as conn:
                queue_timeout_s = getattr(manager.settings, "evolver_queue_timeout_s", None)
                run = (
                    await run_queries.claim_next(conn, queue_timeout_s=queue_timeout_s)
                    if queue_timeout_s is not None
                    else await run_queries.claim_next(conn)
                )
            manager.unhealthy_reason = None
            delay = 0.1
            if run is None:
                manager.semaphore.release()
                acquired = False
                await _wait_for_work(manager.wake)
                continue
            task = asyncio.create_task(manager._execute(run), name=f"evo-{run['run_id']}")
            manager.tasks[run["run_id"]] = task
            task.add_done_callback(lambda done, rid=run["run_id"]: manager._done(rid, done))
            handed_off = True
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            manager.unhealthy_reason = f"dispatcher failed: {type(exc).__name__}: {exc}"
            await asyncio.sleep(delay)
            delay = min(delay * 2, 5.0)
        finally:
            if acquired and not handed_off:
                manager.semaphore.release()


async def _wait_for_work(wake: asyncio.Event) -> None:
    wake.clear()
    try:
        await asyncio.wait_for(wake.wait(), timeout=1.0)
    except TimeoutError:
        pass


__all__ = ["dispatch_runs"]
