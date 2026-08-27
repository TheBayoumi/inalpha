"""共享的冻结 LLM 快照与审批断言测试夹具。"""

from __future__ import annotations

import copy
import time

import jwt

VALID_LLM_SNAPSHOT = {
    "config_id": "config-1",
    "provider": "deepseek",
    "model": "deepseek-v4-pro",
    "base_url": "https://api.deepseek.com",
    "pricing": {
        "version": "provider-estimate-2026-08",
        "currency": "USD",
        "input_usd_per_million": 0.56,
        "output_usd_per_million": 1.68,
        "assumed_input_tokens": 24_000,
        "max_output_tokens": 8_192,
        "estimated_max_usd_per_candidate": 0.02720256,
    },
    "config_digest": "a4635b0c80f69b6054bdc2330b78cb98d9c81c849d476e7d01f1b8d626015c2c",
}


def llm_snapshot() -> dict:
    """返回可安全修改的有效快照副本。"""
    return copy.deepcopy(VALID_LLM_SNAPSHOT)


def approval_token(
    *,
    subject: str,
    operation_id: str,
    secret: str,
    digest: str = VALID_LLM_SNAPSHOT["config_digest"],
) -> str:
    """签发与 orchestration 相同 scope 的短效审批断言。"""
    now = int(time.time())
    return jwt.encode(
        {
            "sub": subject,
            "token_use": "evolution_approval",
            "operation_id": operation_id,
            "llm_config_digest": digest,
            "iat": now,
            "exp": now + 300,
        },
        secret,
        algorithm="HS256",
    )
