"""0038 E1 schema migration tests against real PostgreSQL."""

from __future__ import annotations

import psycopg
import pytest
from migration_0038_support import (
    CANDIDATE_LEGACY,
    RUN_LEGACY,
    alembic,
    db_url,
    remove_incompatible_rows,
    seed_incompatible_rows,
    seed_legacy_rows,
)

pytestmark = pytest.mark.integration


def test_0038_upgrade_downgrade_upgrade_preserves_truth(
    migration_db_url: str,
) -> None:
    """Legacy NULL fitness upgrades; unsafe downgrade refuses without deletion."""
    alembic(migration_db_url, "upgrade", "0037")
    with psycopg.connect(db_url(migration_db_url), autocommit=True) as conn:
        seed_legacy_rows(conn)

    alembic(migration_db_url, "upgrade", "0038")
    with psycopg.connect(db_url(migration_db_url), autocommit=True) as conn:
        legacy_run = conn.execute(
            """SELECT status,active_stage,queued_at,started_at,finished_at,
            requested_as_of,queued_at_is_estimate FROM strategy_evo_runs
            WHERE run_id=%s""",
            (RUN_LEGACY,),
        ).fetchone()
        assert legacy_run is not None
        assert legacy_run[0:2] == ("completed", "legacy")
        assert legacy_run[2] == legacy_run[3]
        assert legacy_run[4] is not None and legacy_run[5] is None
        assert legacy_run[6] is True
        assert conn.execute(
            """SELECT stage,outcome,fitness,evaluation_snapshot
            FROM strategy_evo_candidates WHERE candidate_id=%s""",
            (CANDIDATE_LEGACY,),
        ).fetchone() == ("legacy", "legacy_unknown", None, {"legacy": True})
        definition = conn.execute(
            """SELECT pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conname='evo_candidate_success_check'"""
        ).fetchone()[0]
        required = (
            "source_code", "source_hash", "evaluation_snapshot",
            "fitness", "data_epoch", "report",
        )
        assert all(field in definition for field in required)
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "UPDATE strategy_evo_candidates SET outcome='succeeded' WHERE candidate_id=%s",
                (CANDIDATE_LEGACY,),
            )
        seed_incompatible_rows(conn)

    failed = alembic(migration_db_url, "downgrade", "0037", check=False)
    assert failed.returncode != 0
    assert "0038 downgrade refused" in failed.stderr
    with psycopg.connect(db_url(migration_db_url), autocommit=True) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0038",
        )
        assert conn.execute(
            "SELECT count(*) FROM strategy_evo_candidates"
        ).fetchone() == (2,)
        remove_incompatible_rows(conn)

    alembic(migration_db_url, "downgrade", "0037")
    with psycopg.connect(db_url(migration_db_url), autocommit=True) as conn:
        row = conn.execute(
            """SELECT fitness,r.started_at,r.finished_at
            FROM strategy_evo_candidates c JOIN strategy_evo_runs r USING(run_id)
            WHERE candidate_id=%s""",
            (CANDIDATE_LEGACY,),
        ).fetchone()
        assert row is not None and row[0] is None
        assert row[1:] == legacy_run[3:5]

    alembic(migration_db_url, "upgrade", "0038")
    with psycopg.connect(db_url(migration_db_url)) as conn:
        assert conn.execute(
            "SELECT stage,outcome FROM strategy_evo_candidates WHERE candidate_id=%s",
            (CANDIDATE_LEGACY,),
        ).fetchone() == ("legacy", "legacy_unknown")
