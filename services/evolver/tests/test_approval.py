"""短效演化审批断言测试。"""

from __future__ import annotations

import time
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException

from inalpha_evolver.api.approval import verify_evolution_approval

_SECRET = "approval-unit-test-secret-at-least-32-bytes"
_DIGEST = "a" * 64


def _token(ttl_seconds: int) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": "user:alice",
            "token_use": "evolution_approval",
            "operation_id": "approval-operation-1",
            "llm_config_digest": _DIGEST,
            "iat": now,
            "exp": now + ttl_seconds,
        },
        _SECRET,
        algorithm="HS256",
    )


def _verify(token: str) -> None:
    verify_evolution_approval(
        token,
        owner_sub="user:alice",
        operation_id="approval-operation-1",
        llm_config_digest=_DIGEST,
        settings=SimpleNamespace(jwt_secret=_SECRET, jwt_algorithm="HS256"),  # type: ignore[arg-type]
    )


def test_approval_accepts_only_short_lived_matching_scope() -> None:
    _verify(_token(300))

    with pytest.raises(HTTPException) as error:
        _verify(_token(301))
    assert error.value.status_code == 403


def test_approval_rejects_another_owner() -> None:
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "user:bob",
            "token_use": "evolution_approval",
            "operation_id": "approval-operation-1",
            "llm_config_digest": _DIGEST,
            "iat": now,
            "exp": now + 300,
        },
        _SECRET,
        algorithm="HS256",
    )

    with pytest.raises(HTTPException) as error:
        _verify(token)
    assert error.value.status_code == 403
