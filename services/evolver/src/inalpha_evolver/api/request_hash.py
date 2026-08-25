"""run 创建请求的规范化与幂等摘要。"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .schemas import StartRunRequest


def normalized_request(request: StartRunRequest) -> tuple[dict[str, Any], str]:
    payload = request.model_dump(mode="json")
    config = payload["config"]
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return config, digest


__all__ = ["normalized_request"]
