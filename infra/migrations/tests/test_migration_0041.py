"""0041 owner LLM snapshot migration tests against real PostgreSQL."""

from __future__ import annotations

import json

import psycopg
import pytest
from migration_0038_support import alembic, db_url

pytestmark = pytest.mark.integration

_LEGACY_RUN = "30000000-0000-0000-0000-000000000001"
_NEW_RUN = "30000000-0000-0000-0000-000000000002"
_VALID_RUN = "30000000-0000-0000-0000-000000000003"
_OWNER = "00000000-0000-0000-0000-000000000099"
_DIGEST = "a4635b0c80f69b6054bdc2330b78cb98d9c81c849d476e7d01f1b8d626015c2c"
_SNAPSHOT = {
    "config_id": "config-1",
    "provider": "deepseek",
    "model": "deepseek-v4-pro",
    "base_url": "https://api.deepseek.com",
    "pricing": {"version": "provider-estimate-2026-08"},
    "config_digest": _DIGEST,
}


def _insert_run(
    conn: psycopg.Connection[tuple[object, ...]],
    run_id: str,
    key: str,
    *,
    snapshot: dict[str, object] | None = None,
) -> None:
    columns = ""
    values = ""
    params: list[object] = [run_id, _OWNER, "user:test", key, f"hash-{key}"]
    if snapshot is not None:
        columns = ",llm_snapshot,llm_config_digest"
        values = ",%s,%s"
        params.extend([json.dumps(snapshot), snapshot["config_digest"]])
    conn.execute(
        f"""INSERT INTO strategy_evo_runs
        (run_id,owner_account_id,requested_by_sub,seed_strategy_id,budget,config,
        status,idempotency_key,request_hash,queued_at{columns})
        VALUES (%s,%s,%s,'seed',1,'{{}}','queued',%s,%s,NOW(){values})""",
        params,
    )


def test_0041_preserves_old_rows_and_enforces_new_snapshots(
    migration_db_url: str,
) -> None:
    alembic(migration_db_url, "upgrade", "0040")
    with psycopg.connect(db_url(migration_db_url), autocommit=True) as conn:
        _insert_run(conn, _LEGACY_RUN, "legacy-before-0041")

    alembic(migration_db_url, "upgrade", "0041")
    with psycopg.connect(db_url(migration_db_url), autocommit=True) as conn:
        assert conn.execute(
            """SELECT llm_snapshot,llm_config_digest,llm_snapshot_required
            FROM strategy_evo_runs WHERE run_id=%s""",
            (_LEGACY_RUN,),
        ).fetchone() == (None, None, False)
        conn.execute(
            "UPDATE strategy_evo_runs SET updated_at=NOW() WHERE run_id=%s",
            (_LEGACY_RUN,),
        )
        validated = conn.execute(
            "SELECT convalidated FROM pg_constraint WHERE conname='evo_run_llm_snapshot_check'"
        ).fetchone()
        assert validated == (False,)
        with pytest.raises(psycopg.errors.CheckViolation):
            _insert_run(conn, _NEW_RUN, "new-without-snapshot")
        _insert_run(conn, _VALID_RUN, "new-with-snapshot", snapshot=_SNAPSHOT)
        assert conn.execute(
            "SELECT llm_snapshot_required FROM strategy_evo_runs WHERE run_id=%s",
            (_VALID_RUN,),
        ).fetchone() == (True,)

    alembic(migration_db_url, "downgrade", "0040")
