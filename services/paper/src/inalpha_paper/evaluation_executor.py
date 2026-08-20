"""可取消、可超时的单次回测子进程执行器。"""

from __future__ import annotations

import asyncio
import multiprocessing
from multiprocessing.connection import Connection
from typing import Any

from .engine.pool import configure_worker_limits
from .evaluation_worker import run_engine_worker


class WorkerExecutionError(RuntimeError):
    """子进程中的受控失败，不携带不可序列化的异常对象。"""

    def __init__(self, message: str, *, code: str, error_type: str) -> None:
        super().__init__(message)
        self.code = code
        self.error_type = error_type


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
        connection.send(
            (
                "error",
                {
                    "code": getattr(exc, "code", "EVALUATION_WORKER_FAILED"),
                    "error_type": type(exc).__name__,
                    "message": str(exc)[:1000],
                },
            )
        )
    finally:
        connection.close()


def _cleanup_process(process: multiprocessing.Process) -> None:
    """在线程中完成可能阻塞的 terminate/join/kill/close。"""
    try:
        if process.is_alive():
            process.terminate()
        process.join(timeout=1.0)
        if process.is_alive():
            process.kill()
            process.join(timeout=1.0)
    except (AssertionError, ValueError):
        pass
    finally:
        try:
            process.close()
        except ValueError:
            pass


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
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._timeout_s
        started = False
        try:
            await asyncio.wait_for(
                asyncio.to_thread(process.start), timeout=max(0.001, deadline - loop.time())
            )
            started = True
            send.close()
            while not receive.poll():
                if not process.is_alive():
                    raise WorkerExecutionError(
                        f"backtest worker exited without result: {process.exitcode}",
                        code="EVALUATION_WORKER_EXITED",
                        error_type="ProcessExit",
                    )
                if loop.time() >= deadline:
                    raise TimeoutError(f"backtest worker exceeded {self._timeout_s:.1f}s")
                await asyncio.sleep(0.01)
            kind, payload = await asyncio.wait_for(
                asyncio.to_thread(receive.recv),
                timeout=max(0.001, deadline - loop.time()),
            )
            if kind == "ok":
                return payload
            if kind == "error":
                raise WorkerExecutionError(
                    payload["message"],
                    code=payload["code"],
                    error_type=payload["error_type"],
                )
            raise WorkerExecutionError(
                "backtest worker returned an unknown envelope",
                code="EVALUATION_WORKER_PROTOCOL_ERROR",
                error_type="ProtocolError",
            )
        finally:
            receive.close()
            if not started:
                send.close()
            await asyncio.shield(asyncio.to_thread(_cleanup_process, process))


__all__ = ["KillableEngineRunner", "WorkerExecutionError"]
