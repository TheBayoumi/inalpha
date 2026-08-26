"""Mastra 显式审批断言验证。"""

from __future__ import annotations

import jwt
from fastapi import HTTPException

from ..config import EvolverSettings

_MAX_APPROVAL_TTL_SECONDS = 300


def verify_evolution_approval(
    token: str,
    *,
    owner_sub: str,
    operation_id: str,
    llm_config_digest: str,
    settings: EvolverSettings,
) -> None:
    """验证短效审批 JWT，并绑定 owner、幂等操作和 LLM 快照。"""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalid evolution approval") from exc
    expected = {
        "token_use": "evolution_approval",
        "sub": owner_sub,
        "operation_id": operation_id,
        "llm_config_digest": llm_config_digest,
    }
    issued_at = payload.get("iat")
    expires_at = payload.get("exp")
    invalid_ttl = (
        not isinstance(issued_at, int)
        or not isinstance(expires_at, int)
        or expires_at - issued_at > _MAX_APPROVAL_TTL_SECONDS
        or expires_at <= issued_at
    )
    if invalid_ttl or any(payload.get(key) != value for key, value in expected.items()):
        raise HTTPException(status_code=403, detail="evolution approval scope mismatch")


__all__ = ["verify_evolution_approval"]
