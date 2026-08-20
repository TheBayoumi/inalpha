RUN_DOWN = (
    "DROP INDEX IF EXISTS idx_er_active; DROP INDEX IF EXISTS idx_er_owner_cursor;",
    """ALTER TABLE strategy_evo_runs
    DROP CONSTRAINT evo_run_owner_idempotency_key,
    DROP CONSTRAINT strategy_evo_runs_status_check,
    DROP COLUMN owner_account_id, DROP COLUMN requested_by_sub,
    DROP COLUMN idempotency_key, DROP COLUMN request_hash, DROP COLUMN queued_at,
    DROP COLUMN queued_at_is_estimate, DROP COLUMN updated_at, DROP COLUMN venue,
    DROP COLUMN symbol, DROP COLUMN request_timeframe, DROP COLUMN data_timeframe,
    DROP COLUMN engine_timeframe, DROP COLUMN requested_as_of,
    DROP COLUMN seed_source_snapshot, DROP COLUMN seed_source_hash,
    DROP COLUMN seed_report_snapshot, DROP COLUMN baseline_snapshot,
    DROP COLUMN dataset_manifest, DROP COLUMN active_stage, DROP COLUMN failure_code,
    DROP COLUMN failure_message, ALTER COLUMN started_at SET NOT NULL,
    ALTER COLUMN status SET DEFAULT 'running';
    ALTER TABLE strategy_evo_runs ADD CONSTRAINT strategy_evo_runs_status_check
    CHECK (status IN ('running','completed','failed','aborted'));""",
)
