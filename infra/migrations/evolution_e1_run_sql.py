RUN_UP = (
    """ALTER TABLE strategy_evo_runs
    DROP CONSTRAINT IF EXISTS strategy_evo_runs_status_check;
    ALTER TABLE strategy_evo_runs
    ADD COLUMN owner_account_id UUID, ADD COLUMN requested_by_sub TEXT,
    ADD COLUMN idempotency_key TEXT, ADD COLUMN request_hash TEXT,
    ADD COLUMN queued_at TIMESTAMPTZ, ADD COLUMN queued_at_is_estimate BOOLEAN,
    ADD COLUMN updated_at TIMESTAMPTZ, ADD COLUMN venue TEXT, ADD COLUMN symbol TEXT,
    ADD COLUMN request_timeframe TEXT, ADD COLUMN data_timeframe TEXT,
    ADD COLUMN engine_timeframe TEXT, ADD COLUMN requested_as_of TIMESTAMPTZ,
    ADD COLUMN seed_source_snapshot TEXT, ADD COLUMN seed_source_hash TEXT,
    ADD COLUMN seed_report_snapshot JSONB, ADD COLUMN baseline_snapshot JSONB,
    ADD COLUMN dataset_manifest JSONB, ADD COLUMN active_stage TEXT,
    ADD COLUMN failure_code TEXT, ADD COLUMN failure_message TEXT;
    ALTER TABLE strategy_evo_runs ALTER COLUMN started_at DROP NOT NULL;""",
    """UPDATE strategy_evo_runs SET
    owner_account_id = '00000000-0000-0000-0000-000000000001',
    requested_by_sub = 'legacy', idempotency_key = 'legacy:' || run_id,
    request_hash = md5(config::text), queued_at = started_at,
    queued_at_is_estimate = TRUE, updated_at = COALESCE(finished_at, started_at),
    venue = NULLIF(config->>'venue', ''),
    symbol = COALESCE(NULLIF(config->>'symbol', ''), NULLIF(config->'universe'->>0, '')),
    request_timeframe = NULLIF(config->>'timeframe', ''),
    data_timeframe = NULLIF(config->>'timeframe', ''),
    engine_timeframe = NULLIF(config->>'timeframe', ''), active_stage = 'legacy';""",
    """ALTER TABLE strategy_evo_runs ADD CONSTRAINT evo_run_required_fields_check
    CHECK (owner_account_id IS NOT NULL AND requested_by_sub IS NOT NULL
      AND idempotency_key IS NOT NULL AND request_hash IS NOT NULL
      AND queued_at IS NOT NULL AND queued_at_is_estimate IS NOT NULL
      AND updated_at IS NOT NULL) NOT VALID;
    ALTER TABLE strategy_evo_runs VALIDATE CONSTRAINT evo_run_required_fields_check;
    ALTER TABLE strategy_evo_runs
    ALTER COLUMN owner_account_id SET NOT NULL,
    ALTER COLUMN requested_by_sub SET NOT NULL,
    ALTER COLUMN idempotency_key SET NOT NULL,
    ALTER COLUMN request_hash SET NOT NULL,
    ALTER COLUMN queued_at SET NOT NULL,
    ALTER COLUMN queued_at_is_estimate SET DEFAULT FALSE,
    ALTER COLUMN queued_at_is_estimate SET NOT NULL,
    ALTER COLUMN updated_at SET DEFAULT NOW(),
    ALTER COLUMN updated_at SET NOT NULL,
    ALTER COLUMN status SET DEFAULT 'queued';
    ALTER TABLE strategy_evo_runs DROP CONSTRAINT evo_run_required_fields_check;
    ALTER TABLE strategy_evo_runs ADD CONSTRAINT strategy_evo_runs_status_check
    CHECK (status IN ('queued','running','cancelling','completed','failed','aborted'));
    ALTER TABLE strategy_evo_runs ADD CONSTRAINT evo_run_owner_idempotency_key
    UNIQUE (owner_account_id, idempotency_key);""",
    """CREATE INDEX idx_er_owner_cursor
    ON strategy_evo_runs (owner_account_id, queued_at DESC, run_id DESC);
    CREATE INDEX idx_er_active ON strategy_evo_runs (status, queued_at);""",
)
