"""Shared operations for the 0038 PostgreSQL migration test."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
RUN_LEGACY = "10000000-0000-0000-0000-000000000001"
RUN_QUEUED = "10000000-0000-0000-0000-000000000002"
CANDIDATE_LEGACY = "20000000-0000-0000-0000-000000000001"
CANDIDATE_FAILED = "20000000-0000-0000-0000-000000000002"


def db_url(url: str) -> str:
    """Convert an SQLAlchemy psycopg URL to a libpq URL."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def alembic(
    url: str, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run the real Alembic CLI against only the supplied test database."""
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": url},
        check=check,
        capture_output=True,
        text=True,
    )


def seed_legacy_rows(conn: psycopg.Connection[tuple[object, ...]]) -> None:
    """Insert rows valid at 0037, including a candidate with NULL fitness."""
    conn.execute(
        """INSERT INTO strategy_evo_runs
        (run_id,seed_strategy_id,budget,config,status,started_at,finished_at)
        VALUES (%s,'legacy-seed',1,'{"venue":"legacy-market","timeframe":"1d"}',
        'completed','2025-01-02T03:04:05Z','2025-01-03T04:05:06Z')""",
        (RUN_LEGACY,),
    )
    conn.execute(
        """INSERT INTO strategy_evo_candidates
        (candidate_id,run_id,generation,source_code,source_hash,fitness,report,
        data_epoch,status,created_at) VALUES
        (%s,%s,1,'legacy source','legacy-hash',NULL,'{"legacy":true}',
        1735776000000,'rejected','2025-01-02T05:00:00Z')""",
        (CANDIDATE_LEGACY, RUN_LEGACY),
    )


def seed_incompatible_rows(conn: psycopg.Connection[tuple[object, ...]]) -> None:
    """Insert a queued run and failed candidate that 0037 cannot represent."""
    conn.execute(
        """INSERT INTO strategy_evo_runs
        (run_id,owner_account_id,requested_by_sub,seed_strategy_id,budget,config,
        status,idempotency_key,request_hash,queued_at,started_at)
        VALUES (%s,'00000000-0000-0000-0000-000000000002','test','seed',1,
        '{}','queued','queued-test','hash','2026-01-01T00:00:00Z',NULL)""",
        (RUN_QUEUED,),
    )
    conn.execute(
        """INSERT INTO strategy_evo_candidates
        (candidate_id,run_id,slot,generation,stage,outcome,status)
        VALUES (%s,%s,0,1,'completed','mutation_failed','evaluated')""",
        (CANDIDATE_FAILED, RUN_QUEUED),
    )


def remove_incompatible_rows(conn: psycopg.Connection[tuple[object, ...]]) -> None:
    """Remove only test fixtures so the representable downgrade path can run."""
    conn.execute(
        "DELETE FROM strategy_evo_candidates WHERE candidate_id=%s",
        (CANDIDATE_FAILED,),
    )
    conn.execute("DELETE FROM strategy_evo_runs WHERE run_id=%s", (RUN_QUEUED,))
