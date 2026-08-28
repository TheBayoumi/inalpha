"""users access waitlist —— 注册申请、管理员审核与试用准入

Revision ID: 0043_waitlist
Revises: 0042
Create Date: 2026-08-27

现有账号全部回填为 ``active``，避免上线迁移影响已有用户。新注册账号由应用显式
写入 ``pending``。管理员批准后生成一次性激活链接，申请人设置密码后才变为
``active``。管理员角色必须通过 create_user CLI 显式授予，迁移不按邮箱自动提权。
"""
from __future__ import annotations

from alembic import op

revision: str = "0043_waitlist"
down_revision: str | None = "0042"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS access_status TEXT NOT NULL "
        "DEFAULT 'active'"
    )
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name TEXT")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS application_note TEXT")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS reviewed_by TEXT")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS activation_token_hash TEXT")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS activation_expires_at TIMESTAMPTZ")
    op.execute(
        "ALTER TABLE users DROP CONSTRAINT IF EXISTS users_access_status_check"
    )
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT users_access_status_check "
        "CHECK (access_status IN ('pending', 'invited', 'active', 'rejected'))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS users_access_status_created_idx "
        "ON users (access_status, created_at DESC)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS users_activation_token_hash_idx "
        "ON users (activation_token_hash) WHERE activation_token_hash IS NOT NULL"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_access_events (
            id BIGSERIAL PRIMARY KEY,
            target_subject TEXT NOT NULL,
            actor_subject TEXT,
            action TEXT NOT NULL CHECK (
                action IN ('approved', 'activation_rotated', 'rejected', 'activated')
            ),
            previous_status TEXT NOT NULL,
            next_status TEXT NOT NULL,
            token_fingerprint TEXT,
            trace_id TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_user_access_event_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'user_access_events is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER user_access_events_immutable
        BEFORE UPDATE OR DELETE ON user_access_events
        FOR EACH ROW EXECUTE FUNCTION reject_user_access_event_mutation()
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS user_access_events_target_created_idx "
        "ON user_access_events (target_subject, created_at DESC)"
    )


def downgrade() -> None:
    # 检查与删列必须在同一排他锁内，避免并发注册在检查后插入 pending 账号。
    op.execute("LOCK TABLE users IN ACCESS EXCLUSIVE MODE")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM users WHERE access_status <> 'active') THEN
                RAISE EXCEPTION
                    'cannot downgrade 0043_waitlist while non-active users exist; '
                    'approve or remove pending/rejected accounts first';
            END IF;
        END $$
        """
    )
    op.execute("DROP INDEX IF EXISTS users_access_status_created_idx")
    op.execute("DROP INDEX IF EXISTS users_activation_token_hash_idx")
    op.execute("DROP TABLE IF EXISTS user_access_events")
    op.execute("DROP FUNCTION IF EXISTS reject_user_access_event_mutation()")
    op.execute(
        "ALTER TABLE users DROP CONSTRAINT IF EXISTS users_access_status_check"
    )
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS reviewed_by")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS reviewed_at")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS application_note")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS display_name")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS activation_expires_at")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS activation_token_hash")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS access_status")
