"""risk_locks 补 account_id —— 风控锁按用户隔离(多租户上线必修)

Revision ID: 0040
Revises: 0038
Create Date: 2026-08-21

背景:多用户上线后验证发现「风控日志跨账户泄露」——``risk_locks`` 表没有 account_id 列,
``/risk/locks`` / ``/risk/locks/history`` 只按 ``get_current_user`` 认证、不按账户过滤;
HTTP 路径的 ``RiskGuard.check`` 写锁也不带 account_id,导致 A 用户的 global/market/symbol
锁会拦到 B 用户的下单(跨账户误伤),且 B 用户能在风控面板看到 A 的锁。

``account_id TEXT``(可空,向后兼容老行;老行无归属,隔离后对任何账户不可见)。
索引 ``(account_id, locked_at DESC)`` 覆盖「查本人最近 N 条锁」的热路径。

注:``down_revision`` 指向 0038(本提交时的链头)。0039(evolution ``llm_snapshot``)
为同分支并行 WIP、尚未合入;两者各自以 0038 为父,后并 main 者按项目约定修链
(``down_revision`` 指向先合入的那一个),勿留双头。
"""
from __future__ import annotations

from alembic import op

revision: str = "0040"
down_revision: str | None = "0038"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE risk_locks
            ADD COLUMN IF NOT EXISTS account_id TEXT
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS risk_locks_account_locked_idx "
        "ON risk_locks (account_id, locked_at DESC) "
        "WHERE account_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS risk_locks_account_locked_idx")
    op.execute(
        "ALTER TABLE risk_locks DROP COLUMN IF EXISTS account_id"
    )
