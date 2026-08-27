"""Persist restart-stable evolution approval operation identities."""

from __future__ import annotations

from alembic import op

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Add request scope, restore rolling compatibility, and create the operation ledger."""
    op.execute(
        """SET LOCAL lock_timeout = '10s';
ALTER TABLE evolution_credential_grant_uses
ADD COLUMN request_digest TEXT;
UPDATE evolution_credential_grant_uses SET request_digest=repeat('0',64);
ALTER TABLE evolution_credential_grant_uses
ALTER COLUMN request_digest SET DEFAULT repeat('0',64),
ALTER COLUMN request_digest SET NOT NULL,
ADD CONSTRAINT evolution_credential_grant_request_digest_check
CHECK (request_digest ~ '^[0-9a-f]{64}$');
ALTER TABLE strategy_evo_runs
ALTER COLUMN llm_snapshot_required SET DEFAULT FALSE,
ALTER COLUMN llm_credential_grant_required SET DEFAULT FALSE,
DROP CONSTRAINT evo_run_llm_snapshot_check;
ALTER TABLE strategy_evo_runs ADD CONSTRAINT evo_run_llm_snapshot_check
CHECK (
  (NOT llm_credential_grant_required OR llm_snapshot_required)
  AND (status <> 'queued' OR NOT llm_snapshot_required OR llm_credential_grant_required)
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
CREATE TABLE evolution_approval_operations (
  operation_id UUID PRIMARY KEY,
  auth_sub TEXT NOT NULL,
  session_id TEXT NOT NULL,
  tool_name TEXT NOT NULL CHECK (tool_name='evolver.run_evolution'),
  input_digest TEXT NOT NULL CHECK (input_digest ~ '^[0-9a-f]{64}$'),
  approved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL,
  UNIQUE(auth_sub,session_id,tool_name,input_digest),
  CHECK (expires_at>approved_at)
);
CREATE INDEX ix_evolution_approval_operations_expires_at
ON evolution_approval_operations(expires_at);"""
    )


def downgrade() -> None:
    """Restore the 0041 constraint/defaults and remove new ledgers/scopes."""
    op.execute(
        """SET LOCAL lock_timeout = '10s';
DROP TABLE evolution_approval_operations;
ALTER TABLE strategy_evo_runs
ALTER COLUMN llm_snapshot_required SET DEFAULT TRUE,
ALTER COLUMN llm_credential_grant_required SET DEFAULT TRUE,
DROP CONSTRAINT evo_run_llm_snapshot_check;
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
ALTER TABLE evolution_credential_grant_uses
DROP CONSTRAINT evolution_credential_grant_request_digest_check,
DROP COLUMN request_digest;"""
    )
