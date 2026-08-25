"""Evolver health 对 dispatcher 状态的守门测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.responses import JSONResponse

from inalpha_evolver.main import health


@pytest.mark.asyncio
async def test_health_is_unhealthy_when_dispatcher_failed() -> None:
    manager = SimpleNamespace(healthy=False, unhealthy_reason="dispatcher failed")
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(evolution_manager=manager)))

    response = await health(request)  # type: ignore[arg-type]

    assert isinstance(response, JSONResponse)
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_health_is_ok_when_manager_is_healthy() -> None:
    manager = SimpleNamespace(healthy=True, unhealthy_reason=None)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(evolution_manager=manager)))

    response = await health(request)  # type: ignore[arg-type]

    assert response == {"status": "ok", "service": "inalpha-evolver"}
