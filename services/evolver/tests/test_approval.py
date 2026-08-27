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


def _token(
    ttl_seconds: int,
    *,
    overrides: dict[str, object] | None = None,
    secret: str = _SECRET,
) -> str:
    now = int(time.time())
    payload: dict[str, object] = {
        "sub": "user:alice",
        "token_use": "evolution_approval",
        "operation_id": "approval-operation-1",
        "llm_config_digest": _DIGEST,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    payload.update(overrides or {})
    return jwt.encode(
        payload,
        secret,
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


@pytest.mark.parametrize(
    "overrides",
    [
        {"token_use": "session"},
        {"operation_id": "another-operation"},
        {"llm_config_digest": "b" * 64},
        {"iat": None},
        {"exp": None},
    ],
)
def test_approval_rejects_invalid_claims(overrides: dict[str, object]) -> None:
    with pytest.raises(HTTPException) as error:
        _verify(_token(300, overrides=overrides))
    assert error.value.status_code in {401, 403}


def test_approval_rejects_expired_bad_signature_and_non_positive_ttl() -> None:
    tokens = [
        _token(-1),
        _token(300, secret="different-secret-at-least-32-bytes"),
        _token(300, overrides={"iat": int(time.time()) + 300}),
    ]
    for token in tokens:
        with pytest.raises(HTTPException) as error:
            _verify(token)
        assert error.value.status_code in {401, 403}
