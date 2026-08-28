"""0043_waitlist user access migration tests against real PostgreSQL."""

from __future__ import annotations

import psycopg
import pytest
from migration_0038_support import alembic, db_url

pytestmark = pytest.mark.integration


def test_0043_waitlist_preserves_existing_access_and_guards_downgrade(
    migration_db_url: str,
) -> None:
    alembic(migration_db_url, "upgrade", "0042")
    with psycopg.connect(db_url(migration_db_url), autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO users (subject, email, password_hash, roles)
            VALUES
              ('console:dev', 'admin@inalpha.dev', 'hash', '{}'),
              ('user:existing', 'existing@example.com', 'hash', ARRAY['trader'])
            """
        )

    alembic(migration_db_url, "upgrade", "0043_waitlist")
    with psycopg.connect(db_url(migration_db_url), autocommit=True) as conn:
        assert conn.execute(
            "SELECT access_status, roles FROM users WHERE subject='console:dev'"
        ).fetchone() == ("active", [])
        assert conn.execute(
            "SELECT access_status, roles FROM users WHERE subject='user:existing'"
        ).fetchone() == ("active", ["trader"])
        conn.execute(
            """
            INSERT INTO users (
                subject, email, password_hash, access_status, display_name,
                application_note, activation_token_hash, activation_expires_at
            ) VALUES (
                'user:pending', 'pending@example.com', 'hash', 'pending',
                'Pending', 'note', 'token-hash', now() + interval '48 hours'
            )
            """
        )
        assert conn.execute(
            "SELECT display_name, application_note, activation_token_hash "
            "FROM users WHERE subject='user:pending'"
        ).fetchone() == ("Pending", "note", "token-hash")
        assert conn.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name='user_access_events'"
        ).fetchone() == (1,)
        event_id = conn.execute(
            """
            INSERT INTO user_access_events (
                target_subject, actor_subject, action, previous_status, next_status
            ) VALUES (
                'user:existing', 'console:dev', 'approved', 'pending', 'invited'
            ) RETURNING id
            """
        ).fetchone()[0]
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            conn.execute(
                "UPDATE user_access_events SET action='rejected' WHERE id=%s",
                (event_id,),
            )
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            conn.execute("DELETE FROM user_access_events WHERE id=%s", (event_id,))
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            conn.execute("TRUNCATE user_access_events")
        conn.execute("DELETE FROM users WHERE subject='user:existing'")
        assert conn.execute(
            "SELECT target_subject FROM user_access_events WHERE id=%s", (event_id,)
        ).fetchone() == ("user:existing",)
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                """
                INSERT INTO users (subject, email, password_hash, access_status)
                VALUES ('user:invalid', 'invalid@example.com', 'hash', 'unknown')
                """
            )

    blocked = alembic(migration_db_url, "downgrade", "0042", check=False)
    assert blocked.returncode != 0
    assert "cannot downgrade 0043_waitlist while non-active users exist" in blocked.stderr

    with psycopg.connect(db_url(migration_db_url), autocommit=True) as conn:
        conn.execute("UPDATE users SET access_status = 'active'")
    alembic(migration_db_url, "downgrade", "0042")
    with psycopg.connect(db_url(migration_db_url), autocommit=True) as conn:
        assert conn.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='users' AND column_name='access_status'"
        ).fetchone() is None
        assert conn.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name='user_access_events'"
        ).fetchone() is None
