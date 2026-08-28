"""0044 migration-head merge integration test."""

from __future__ import annotations

from migration_0038_support import alembic


def test_0044_restores_a_single_upgrade_head(migration_db_url: str) -> None:
    """Upgrade both 0043 branches through one deterministic head."""
    alembic(migration_db_url, "upgrade", "head")

    current = alembic(migration_db_url, "current")
    assert "0044 (head)" in current.stdout
    assert "0043_waitlist (head)" not in current.stdout
