"""Evolver FastAPI 应用入口。

使用方式：:

    uvicorn inalpha_evolver.main:app --port 8005 --reload
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from inalpha_shared.db import close_pool, init_pool
from inalpha_shared.middleware import install_error_handler, install_request_logging

from .api.routes import router
from .config import get_evolver_settings
from .mutator import Mutator
from .runtime import EvolutionRunManager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """初始化 DB 队列与 manager；E1 强制单 API worker。"""
    settings = get_evolver_settings()
    workers = int(os.environ.get("WEB_CONCURRENCY", os.environ.get("WORKERS", "1")))
    if workers != 1:
        raise RuntimeError("evolver requires exactly one API worker in E1")
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for evolver")
    await init_pool(
        settings.database_url,
        min_size=2,
        max_size=settings.evolver_pool_size,
    )
    manager = EvolutionRunManager(mutator=Mutator(), settings=settings)
    app.state.evolution_manager = manager
    await manager.start()
    try:
        yield
    finally:
        await manager.close()
        await close_pool()


app = FastAPI(
    title="Inalpha Evolver API",
    description="策略演化引擎 —— LLM-as-mutation-operator 闭环",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)
install_request_logging(app)
install_error_handler(app)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "inalpha-evolver"}