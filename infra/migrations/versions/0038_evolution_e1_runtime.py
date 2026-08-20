"""Safely adapt legacy evolution rows to the E1 runtime schema."""

from __future__ import annotations

from alembic import op

from evolution_e1_candidate_sql import CANDIDATE_DOWN, CANDIDATE_UP
from evolution_e1_run_down_sql import RUN_DOWN
from evolution_e1_run_sql import RUN_UP

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

_DOWNGRADE_GUARD = """
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM strategy_evo_candidates
    WHERE source_code IS NULL OR source_hash IS NULL
       OR report IS NULL OR data_epoch IS NULL
  ) THEN
    RAISE EXCEPTION USING MESSAGE =
      '0038 downgrade refused: candidates incompatible with the 0037 NOT NULL schema';
  END IF;
  IF EXISTS (
    SELECT 1 FROM strategy_evo_runs
    WHERE status IN ('queued', 'cancelling') OR started_at IS NULL
  ) THEN
    RAISE EXCEPTION USING MESSAGE =
      '0038 downgrade refused: runs incompatible with the 0037 status/started_at schema';
  END IF;
END $$;
"""


def _execute_all(statements: tuple[str, ...]) -> None:
    """Execute one migration phase at a time for inspectable failure boundaries."""
    for statement in statements:
        op.execute(statement)


def upgrade() -> None:
    """Backfill legacy truth first, then validate and install E1 constraints."""
    op.execute("SET LOCAL lock_timeout = '10s'")
    _execute_all(RUN_UP)
    _execute_all(CANDIDATE_UP)


def downgrade() -> None:
    """Refuse incompatible rollback instead of deleting or falsifying business rows."""
    op.execute("SET LOCAL lock_timeout = '10s'")
    op.execute(_DOWNGRADE_GUARD)
    _execute_all(CANDIDATE_DOWN)
    _execute_all(RUN_DOWN)
