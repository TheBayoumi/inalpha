"""Freeze non-secret owner LLM metadata on every new evolution run."""

from __future__ import annotations

from alembic import op

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Abort unapproved legacy work, then enforce snapshots for every new queued run."""
    op.execute("SET LOCAL lock_timeout = '10s'")
    op.execute(
        """ALTER TABLE strategy_evo_runs
ADD COLUMN llm_snapshot JSONB,
ADD COLUMN llm_config_digest TEXT,
ADD COLUMN llm_credential_grant TEXT,
ADD COLUMN llm_credential_grant_required BOOLEAN NOT NULL DEFAULT FALSE,
ADD COLUMN llm_snapshot_required BOOLEAN NOT NULL DEFAULT FALSE;
UPDATE strategy_evo_candidates AS candidate SET stage='completed',outcome='cancelled',
error_code='EVOLUTION_UPGRADE_ABORTED',
error_message='run queued before owner LLM snapshot migration',updated_at=NOW()
FROM strategy_evo_runs AS run
WHERE candidate.run_id=run.run_id AND candidate.outcome='pending'
  AND run.status IN ('queued','running','cancelling');
UPDATE strategy_evo_runs SET status='aborted',active_stage='aborted',
finished_at=NOW(),updated_at=NOW(),failure_code='EVOLUTION_UPGRADE_ABORTED',
failure_message='run queued before owner LLM snapshot migration'
WHERE status IN ('queued','running','cancelling');
ALTER TABLE strategy_evo_runs
ALTER COLUMN llm_snapshot_required SET DEFAULT TRUE,
ALTER COLUMN llm_credential_grant_required SET DEFAULT TRUE;
ALTER TABLE strategy_evo_runs ADD CONSTRAINT evo_run_llm_snapshot_check
CHECK (
  (status <> 'queued' OR (llm_snapshot_required AND llm_credential_grant_required))
  AND (
    NOT llm_snapshot_required
    OR (
      llm_snapshot IS NOT NULL
      AND llm_config_digest IS NOT NULL
      AND (
        NOT llm_credential_grant_required
        OR length(COALESCE(llm_credential_grant,''))>=100
      )
      AND llm_config_digest ~ '^[0-9a-f]{64}$'
      AND COALESCE(llm_snapshot->>'config_digest'=llm_config_digest,FALSE)
      AND length(COALESCE(llm_snapshot->>'config_id',''))>0
      AND length(COALESCE(llm_snapshot->>'provider',''))>0
      AND length(COALESCE(llm_snapshot->>'model',''))>0
      AND COALESCE(jsonb_typeof(llm_snapshot->'pricing')='object',FALSE)
    )
  )
) NOT VALID;
CREATE TABLE evolution_credential_grant_uses (
  jti UUID PRIMARY KEY,
  owner_sub TEXT NOT NULL,
  config_id TEXT NOT NULL,
  operation_id TEXT NOT NULL,
  config_digest TEXT NOT NULL CHECK (config_digest ~ '^[0-9a-f]{64}$'),
  consumed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_redeemed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  redemption_count SMALLINT NOT NULL DEFAULT 1 CHECK (redemption_count BETWEEN 1 AND 2)
);
CREATE INDEX ix_evolution_credential_grant_uses_consumed_at
ON evolution_credential_grant_uses(consumed_at);"""
    )


def downgrade() -> None:
    """Remove metadata columns; intentionally do not resurrect upgrade-aborted work."""
    op.execute("SET LOCAL lock_timeout = '10s'")
    op.execute(
        """DROP TABLE evolution_credential_grant_uses;
ALTER TABLE strategy_evo_runs
DROP CONSTRAINT evo_run_llm_snapshot_check,
DROP COLUMN llm_snapshot_required,
DROP COLUMN llm_credential_grant_required,
DROP COLUMN llm_credential_grant,
DROP COLUMN llm_config_digest,
DROP COLUMN llm_snapshot;"""
    )
