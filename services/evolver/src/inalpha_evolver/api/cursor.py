"""run keyset cursor 的编码与校验。"""
from __future__ import annotations

import base64
import json
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException


def encode_cursor(queued_at: datetime, run_id: UUID) -> str:
    """编码不透明的 `(queued_at, run_id)` 游标。"""
    payload = json.dumps(
        [queued_at.isoformat(), str(run_id)],
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(value: str | None) -> tuple[datetime, UUID] | None:
    """解码游标；格式错误统一返回 400。"""
    if value is None:
        return None
    try:
        padding = "=" * (-len(value) % 4)
        queued_at, run_id = json.loads(
            base64.urlsafe_b64decode(value + padding).decode()
        )
        parsed_at = datetime.fromisoformat(queued_at.replace("Z", "+00:00"))
        if parsed_at.tzinfo is None:
            raise ValueError("cursor timestamp must include timezone")
        return parsed_at, UUID(run_id)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid cursor") from exc


__all__ = ["decode_cursor", "encode_cursor"]
