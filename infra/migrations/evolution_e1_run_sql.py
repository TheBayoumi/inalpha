RUN_UP = """ALTER TABLE strategy_evo_runs DROP CONSTRAINT IF EXISTS strategy_evo_runs_status_check;
ALTER TABLE strategy_evo_runs
ADD COLUMN owner_account_id UUID,ADD COLUMN requested_by_sub TEXT,
ADD COLUMN idempotency_key TEXT,ADD COLUMN request_hash TEXT,
ADD COLUMN queued_at TIMESTAMPTZ,ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
ADD COLUMN venue TEXT,ADD COLUMN symbol TEXT,ADD COLUMN request_timeframe TEXT,
ADD COLUMN data_timeframe TEXT,ADD COLUMN engine_timeframe TEXT,
ADD COLUMN requested_as_of TIMESTAMPTZ,ADD COLUMN seed_source_snapshot TEXT,
ADD COLUMN seed_source_hash TEXT,ADD COLUMN seed_report_snapshot JSONB,
ADD COLUMN baseline_snapshot JSONB,ADD COLUMN dataset_manifest JSONB,
ADD COLUMN active_stage TEXT,ADD COLUMN failure_code TEXT,ADD COLUMN failure_message TEXT;
UPDATE strategy_evo_runs SET owner_account_id='00000000-0000-0000-0000-000000000001',
requested_by_sub='legacy',idempotency_key='legacy:'||run_id,
request_hash=md5(config::text),queued_at=started_at,venue=COALESCE(config->>'venue','legacy'),
symbol=COALESCE(config->>'symbol',config->'universe'->>0,'legacy'),
request_timeframe=COALESCE(config->>'timeframe','1h'),
data_timeframe=COALESCE(config->>'timeframe','1h'),
engine_timeframe=COALESCE(config->>'timeframe','1h'),requested_as_of=finished_at;
ALTER TABLE strategy_evo_runs ALTER COLUMN owner_account_id SET NOT NULL,
ALTER COLUMN requested_by_sub SET NOT NULL,ALTER COLUMN idempotency_key SET NOT NULL,
ALTER COLUMN request_hash SET NOT NULL,ALTER COLUMN queued_at SET NOT NULL,
ALTER COLUMN status SET DEFAULT 'queued',ADD CONSTRAINT strategy_evo_runs_status_check
CHECK(status IN('queued','running','cancelling','completed','failed','aborted')),
ADD CONSTRAINT evo_run_owner_idempotency_key UNIQUE(owner_account_id,idempotency_key);
CREATE INDEX idx_er_owner_cursor ON strategy_evo_runs(owner_account_id,queued_at DESC,run_id DESC);
CREATE INDEX idx_er_active ON strategy_evo_runs(status,queued_at);"""

RUN_DOWN = """DROP INDEX IF EXISTS idx_er_active;DROP INDEX IF EXISTS idx_er_owner_cursor;
UPDATE strategy_evo_runs SET status='aborted' WHERE status IN('queued','cancelling');
ALTER TABLE strategy_evo_runs DROP CONSTRAINT evo_run_owner_idempotency_key,
DROP CONSTRAINT strategy_evo_runs_status_check,
DROP COLUMN owner_account_id,DROP COLUMN requested_by_sub,DROP COLUMN idempotency_key,
DROP COLUMN request_hash,DROP COLUMN queued_at,DROP COLUMN updated_at,DROP COLUMN venue,
DROP COLUMN symbol,DROP COLUMN request_timeframe,DROP COLUMN data_timeframe,
DROP COLUMN engine_timeframe,DROP COLUMN requested_as_of,DROP COLUMN seed_source_snapshot,
DROP COLUMN seed_source_hash,DROP COLUMN seed_report_snapshot,DROP COLUMN baseline_snapshot,
DROP COLUMN dataset_manifest,DROP COLUMN active_stage,DROP COLUMN failure_code,
DROP COLUMN failure_message,ALTER COLUMN status SET DEFAULT 'running',
ADD CONSTRAINT strategy_evo_runs_status_check CHECK(status IN('running','completed','failed','aborted'));"""
