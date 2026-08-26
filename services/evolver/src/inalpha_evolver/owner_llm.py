"""按 run 冻结快照解析 owner 的既有加密 LLM 凭据。"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import httpx
import jwt
from inalpha_shared_llm import LLMClient  # type: ignore[import-untyped]
from inalpha_shared_llm.config import LLMSettings  # type: ignore[import-untyped]

from .config import EvolverSettings
from .mutator import Mutator

_BASE_URLS = {
    "deepseek": "https://api.deepseek.com/v1",
    "openai": "https://api.openai.com/v1",
    "kimi": "https://api.moonshot.cn/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
}


async def build_owner_mutator(
    run: dict[str, Any],
    settings: EvolverSettings,
) -> Mutator:
    """只把明文 key 留在当前进程内；run/日志均仅保存 config reference。"""
    snapshot = run.get("llm_snapshot")
    if not isinstance(snapshot, dict):
        raise RuntimeError("run is missing frozen LLM snapshot")
    config_id = str(snapshot["config_id"])
    issued_at = int(time.time())
    token = jwt.encode(
        {
            "sub": run["requested_by_sub"],
            "token_use": "evolver_credential",
            "config_id": config_id,
            "iat": issued_at,
            "exp": issued_at + min(settings.service_token_ttl_s, 600),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    url = (
        f"{settings.dashboard_service_url.rstrip('/')}/api/internal/llm-config/"
        f"{quote(config_id, safe='')}"
    )
    async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
        response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    if response.status_code != 200:
        raise RuntimeError(f"owner LLM credential unavailable: HTTP {response.status_code}")
    credential = response.json()
    if (
        credential.get("config_id") != config_id
        or credential.get("provider") != snapshot["provider"]
    ):
        raise RuntimeError("owner LLM credential no longer matches frozen snapshot")
    api_key = credential.get("api_key")
    if not isinstance(api_key, str) or not api_key:
        raise RuntimeError("owner LLM credential response omitted api_key")
    pricing = snapshot["pricing"]
    llm_settings = LLMSettings(
        LLM_API_KEY=api_key,
        DEEPSEEK_API_KEY="",
        LLM_BASE_URL=snapshot.get("base_url") or _BASE_URLS[snapshot["provider"]],
        LLM_MODEL=snapshot["model"],
        LLM_TIMEOUT_S=settings.evolver_llm_timeout_s,
        LLM_MAX_TOKENS=int(pricing["max_output_tokens"]),
    )
    return Mutator(
        llm_client=LLMClient(settings=llm_settings),
        input_usd_per_million=float(pricing["input_usd_per_million"]),
        output_usd_per_million=float(pricing["output_usd_per_million"]),
        max_output_tokens=int(pricing["max_output_tokens"]),
    )


__all__ = ["build_owner_mutator"]
