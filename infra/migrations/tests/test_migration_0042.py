"""0042 durable evolution approval operation ledger integration tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from migration_0038_support import alembic, db_url

pytestmark = pytest.mark.integration


def test_0042_persists_one_operation_per_owner_thread_request(
    migration_db_url: str,
) -> None:
    alembic(migration_db_url, "upgrade", "0041")
    old_grant = (
        "11111111-1111-4111-8111-111111111111",
        "user:alice",
        "config-1",
        "operation-old",
        "a" * 64,
    )
    with psycopg.connect(db_url(migration_db_url), autocommit=True) as conn:
        conn.execute(
            """INSERT INTO evolution_credential_grant_uses
            (jti,owner_sub,config_id,operation_id,config_digest)
            VALUES (%s,%s,%s,%s,%s)""",
            old_grant,
        )

    alembic(migration_db_url, "upgrade", "0042")
    identity = ("user:alice", "thread-1", "evolver.run_evolution", "a" * 64)
    first = "50000000-0000-4000-8000-000000000001"
    second = "50000000-0000-4000-8000-000000000002"
    expires = datetime.now(UTC) + timedelta(hours=24)
    with psycopg.connect(db_url(migration_db_url), autocommit=True) as conn:
        assert conn.execute(
            """SELECT request_digest FROM evolution_credential_grant_uses
            WHERE jti=%s""",
            (old_grant[0],),
        ).fetchone() == ("0" * 64,)
        conn.execute(
            """INSERT INTO evolution_credential_grant_uses
            (jti,owner_sub,config_id,operation_id,config_digest)
            VALUES ('11111111-1111-4111-8111-111111111112',
                    'user:alice','config-1','operation-rolling',%s)""",
            ("a" * 64,),
        )
        assert conn.execute(
            """SELECT request_digest FROM evolution_credential_grant_uses
            WHERE jti='11111111-1111-4111-8111-111111111112'"""
        ).fetchone() == ("0" * 64,)
        conn.execute(
            """INSERT INTO strategy_evo_runs
            (run_id,owner_account_id,requested_by_sub,seed_strategy_id,budget,config,
             status,idempotency_key,request_hash,queued_at)
            VALUES ('50000000-0000-4000-8000-000000000010',
                    '00000000-0000-0000-0000-000000000099','user:alice','seed',1,'{}',
                    'queued','old-image-compatible','old-hash',NOW())"""
        )
        assert conn.execute(
            """SELECT llm_snapshot_required,llm_credential_grant_required
            FROM strategy_evo_runs
            WHERE run_id='50000000-0000-4000-8000-000000000010'"""
        ).fetchone() == (False, False)
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                """INSERT INTO strategy_evo_runs
                (run_id,owner_account_id,requested_by_sub,seed_strategy_id,budget,config,
                 status,idempotency_key,request_hash,queued_at,
                 llm_snapshot_required,llm_credential_grant_required)
                VALUES ('50000000-0000-4000-8000-000000000011',
                        '00000000-0000-0000-0000-000000000099','user:alice','seed',1,'{}',
                        'queued','new-image-invalid','new-hash',NOW(),TRUE,TRUE)"""
            )
        conn.execute(
            """INSERT INTO evolution_approval_operations
            (operation_id,auth_sub,session_id,tool_name,input_digest,expires_at)
            VALUES (%s,%s,%s,%s,%s,%s)""",
            (first, *identity, expires),
        )
        conn.execute(
            """INSERT INTO evolution_approval_operations
            (operation_id,auth_sub,session_id,tool_name,input_digest,expires_at)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (auth_sub,session_id,tool_name,input_digest) DO UPDATE SET
            operation_id=EXCLUDED.operation_id,approved_at=NOW(),expires_at=EXCLUDED.expires_at""",
            (second, *identity, expires),
        )
        assert conn.execute(
            """SELECT operation_id::text FROM evolution_approval_operations
            WHERE auth_sub=%s AND session_id=%s AND tool_name=%s AND input_digest=%s
              AND expires_at>NOW()""",
            identity,
        ).fetchone() == (second,)

    alembic(migration_db_url, "downgrade", "0041")
    with psycopg.connect(db_url(migration_db_url), autocommit=True) as conn:
        assert conn.execute(
            "SELECT to_regclass('evolution_approval_operations')"
        ).fetchone() == (None,)
        assert conn.execute(
            """SELECT 1 FROM information_schema.columns
            WHERE table_name='evolution_credential_grant_uses'
              AND column_name='request_digest'"""
        ).fetchone() is None
