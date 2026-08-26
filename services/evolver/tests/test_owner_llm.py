"""Owner-scoped LLM credential 与 per-run 生命周期测试。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar

import jwt
import pytest

from inalpha_evolver.owner_llm import build_owner_mutator
from inalpha_evolver.runtime.executor import _run_mutator

from .llm_snapshot_fixtures import llm_snapshot


class _Response:
    status_code = 200

    @staticmethod
    def json() -> dict[str, str]:
        return {
            "config_id": "config-1",
            "provider": "deepseek",
            "api_key": "owner-test-key",
        }


class _CredentialClient:
    kwargs: ClassVar[dict[str, object]] = {}
    requested_url: ClassVar[str] = ""
    requested_headers: ClassVar[dict[str, str]] = {}

    def __init__(self, **kwargs: object) -> None:
        type(self).kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def get(self, url: str, **kwargs: object) -> _Response:
        type(self).requested_url = url
        type(self).requested_headers = kwargs["headers"]  # type: ignore[assignment]
        return _Response()


@pytest.mark.asyncio
async def test_owner_mutator_uses_frozen_snapshot_and_credential_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("inalpha_evolver.owner_llm.httpx.AsyncClient", _CredentialClient)
    run = {
        "requested_by_sub": "user:alice",
        "llm_snapshot": llm_snapshot(),
    }
    settings = SimpleNamespace(
        dashboard_service_url="http://dashboard:3001",
        service_token_ttl_s=3600,
        jwt_secret="test-secret-at-least-32-bytes-long",
        jwt_algorithm="HS256",
        evolver_llm_timeout_s=45,
    )

    mutator = await build_owner_mutator(run, settings)  # type: ignore[arg-type]

    assert _CredentialClient.kwargs["trust_env"] is False
    assert _CredentialClient.requested_url.endswith("/api/internal/llm-config/config-1")
    credential_token = _CredentialClient.requested_headers["Authorization"].removeprefix("Bearer ")
    credential_scope = jwt.decode(
        credential_token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
    assert credential_scope["sub"] == "user:alice"
    assert credential_scope["token_use"] == "evolver_credential"
    assert credential_scope["config_id"] == "config-1"
    assert mutator.llm_client.settings.effective_api_key == "owner-test-key"
    assert mutator.llm_client.settings.llm_model == "deepseek-v4-pro"
    assert mutator.max_output_tokens == 8_192
    assert "api_key" not in run["llm_snapshot"]


class _ClosableMutator:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_production_mutator_is_closed_but_injected_test_mutator_is_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _ClosableMutator()

    async def build(*_args: object) -> _ClosableMutator:
        return owner

    monkeypatch.setattr("inalpha_evolver.runtime.executor.build_owner_mutator", build)
    async with _run_mutator({}, None, SimpleNamespace()):  # type: ignore[arg-type]
        pass
    assert owner.closed is True

    injected = _ClosableMutator()
    async with _run_mutator({}, injected, SimpleNamespace()):  # type: ignore[arg-type]
        pass
    assert injected.closed is False
