"""可取消、可超时的单次回测子进程执行器。"""
from __future__ import annotations

import asyncio
import multiprocessing
from multiprocessing.connection import Connection
from typing import Any

from .engine.pool import configure_worker_limits
from .evaluation_worker import run_engine_worker


def _child_entry(
    connection: Connection,
    kwargs: dict[str, Any],
    cpu_limit_s: int,
    mem_bytes: int,
) -> None:
    configure_worker_limits(cpu_limit_s, mem_bytes)
    try:
        connection.send(("ok", run_engine_worker(**kwargs)))
    except BaseException as exc:
        try:
            connection.send(("error", exc))
        except BaseException:
            connection.send(("error_text", f"{type(exc).__name__}: {exc}"))
    finally:
        connection.close()


class KillableEngineRunner:
    """每次评估启动一个 spawn 子进程，取消或超时时强制终止。"""

    def __init__(self, *, timeout_s: float, mem_gb: float) -> None:
        self._timeout_s = timeout_s
        self._cpu_limit_s = max(1, int(timeout_s))
        self._mem_bytes = int(mem_gb * 1024**3)
        self._context = multiprocessing.get_context("spawn")

    async def __call__(self, **kwargs: Any) -> Any:
        receive, send = self._context.Pipe(duplex=False)
        process = self._context.Process(
            target=_child_entry,
            args=(send, kwargs, self._cpu_limit_s, self._mem_bytes),
        )
        process.start()
        send.close()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._timeout_s
        try:
            while not receive.poll():
                if not process.is_alive():
                    raise RuntimeError(
                        f"backtest worker exited without result: {process.exitcode}"
                    )
                if loop.time() >= deadline:
                    raise TimeoutError(
                        f"backtest worker exceeded {self._timeout_s:.1f}s"
                    )
                await asyncio.sleep(0.01)
            kind, payload = receive.recv()
            if kind == "ok":
                return payload
            if kind == "error":
                raise payload
            raise RuntimeError(payload)
        finally:
            receive.close()
            if process.is_alive():
                process.terminate()
            process.join(timeout=1.0)
            if process.is_alive():
                process.kill()
                process.join(timeout=1.0)
            process.close()


__all__ = ["KillableEngineRunner"]
