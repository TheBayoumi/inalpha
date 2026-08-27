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
    digest: str | None = None,
    grant: str | None = None,
) -> None:
    columns = ""
    values = ""
    params: list[object] = [run_id, _OWNER, "user:test", key, f"hash-{key}"]
    if snapshot is not None:
        columns = ",llm_snapshot,llm_config_digest,llm_credential_grant"
        values = ",%s,%s,%s"
        params.extend(
            [
                json.dumps(snapshot),
                digest or snapshot.get("config_digest"),
                grant if grant is not None else "g" * 100,
            ]
        )
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
            """SELECT llm_snapshot,llm_config_digest,llm_snapshot_required,
            llm_credential_grant_required
            FROM strategy_evo_runs WHERE run_id=%s""",
            (_LEGACY_RUN,),
        ).fetchone() == (None, None, False, False)
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
        with pytest.raises(psycopg.errors.CheckViolation):
            _insert_run(
                conn,
                "30000000-0000-0000-0000-000000000009",
                "new-without-grant",
                snapshot=_SNAPSHOT,
                grant="",
            )
        _insert_run(conn, _VALID_RUN, "new-with-snapshot", snapshot=_SNAPSHOT)
        assert conn.execute(
            """SELECT llm_snapshot_required,llm_credential_grant_required
            FROM strategy_evo_runs WHERE run_id=%s""",
            (_VALID_RUN,),
        ).fetchone() == (True, True)
        conn.execute(
            """UPDATE strategy_evo_runs
            SET llm_credential_grant=NULL,llm_credential_grant_required=FALSE
            WHERE run_id=%s""",
            (_VALID_RUN,),
        )
        malformed_snapshots = [
            (
                {
                    key: value
                    for key, value in _SNAPSHOT.items()
                    if key != "config_digest"
                },
                _DIGEST,
            ),
            (
                {key: value for key, value in _SNAPSHOT.items() if key != "pricing"},
                _DIGEST,
            ),
            ({**_SNAPSHOT, "config_digest": "b" * 64}, _DIGEST),
            ({**_SNAPSHOT, "model": ""}, _DIGEST),
        ]
        for index, (snapshot, digest) in enumerate(malformed_snapshots, start=4):
            run_id = f"30000000-0000-0000-0000-{index:012d}"
            with pytest.raises(psycopg.errors.CheckViolation):
                _insert_run(
                    conn,
                    run_id,
                    f"invalid-snapshot-{index}",
                    snapshot=snapshot,
                    digest=digest,
                )

        grant_values = (
            "11111111-1111-4111-8111-111111111111",
            "user:test",
            "config-1",
            "operation-1",
            _DIGEST,
        )
        conn.execute(
            """INSERT INTO evolution_credential_grant_uses
            (jti,owner_sub,config_id,operation_id,config_digest) VALUES (%s,%s,%s,%s,%s)""",
            grant_values,
        )
        with pytest.raises(psycopg.errors.UniqueViolation):
            conn.execute(
                """INSERT INTO evolution_credential_grant_uses
                (jti,owner_sub,config_id,operation_id,config_digest)
                VALUES (%s,%s,%s,%s,%s)""",
                grant_values,
            )

    alembic(migration_db_url, "downgrade", "0040")
    with psycopg.connect(db_url(migration_db_url), autocommit=True) as conn:
        columns = conn.execute(
            """SELECT column_name FROM information_schema.columns
            WHERE table_name='strategy_evo_runs'
              AND column_name IN
              ('llm_snapshot','llm_config_digest','llm_credential_grant',
               'llm_credential_grant_required','llm_snapshot_required')"""
        ).fetchall()
        constraint = conn.execute(
            "SELECT 1 FROM pg_constraint WHERE conname='evo_run_llm_snapshot_check'"
        ).fetchone()
        assert columns == []
        assert constraint is None
        assert conn.execute(
            "SELECT to_regclass('evolution_credential_grant_uses')"
        ).fetchone() == (None,)
