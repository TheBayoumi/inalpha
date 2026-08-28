"""Data event snapshot client with short-lived owner-bound service JWT."""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

import httpx
import jwt

from .config import EvolverSettings


async def fetch_event_snapshot(
    snapshot_id: UUID,
    *,
    owner_account_id: UUID,
    settings: EvolverSettings,
) -> dict[str, Any]:
    """Resolve and freeze Data-owned snapshot metadata without direct table access."""
    token = jwt.encode(
        {
            "sub": str(owner_account_id),
            "token_use": "service",
            "service_audience": "data",
            "exp": int(time.time()) + min(settings.service_token_ttl_s, 300),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    url = f"{settings.data_service_url.rstrip('/')}/events/snapshots/{snapshot_id}"
    async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
        response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    if response.status_code != 200:
        raise RuntimeError(f"event snapshot unavailable: HTTP {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("snapshot_id") != str(snapshot_id):
        raise RuntimeError("event snapshot response identity mismatch")
    return payload


__all__ = ["fetch_event_snapshot"]
