CANDIDATE_UP = """ALTER TABLE strategy_evo_candidates ALTER COLUMN source_code DROP NOT NULL,
ALTER COLUMN source_hash DROP NOT NULL,ALTER COLUMN report DROP NOT NULL,
ALTER COLUMN data_epoch DROP NOT NULL,ADD COLUMN slot INT,
ADD COLUMN stage TEXT NOT NULL DEFAULT 'queued',ADD COLUMN outcome TEXT NOT NULL DEFAULT 'pending',
ADD COLUMN audit_snapshot JSONB,ADD COLUMN contract_snapshot JSONB,
ADD COLUMN evaluation_snapshot JSONB,ADD COLUMN error_code TEXT,ADD COLUMN error_message TEXT,
ADD COLUMN input_tokens INT,ADD COLUMN output_tokens INT,
ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
WITH ranked AS(SELECT candidate_id,row_number()OVER(PARTITION BY run_id ORDER BY created_at,candidate_id)-1 n
FROM strategy_evo_candidates)UPDATE strategy_evo_candidates c SET slot=ranked.n,outcome='succeeded',
evaluation_snapshot=report FROM ranked WHERE c.candidate_id=ranked.candidate_id;
ALTER TABLE strategy_evo_candidates ALTER COLUMN slot SET NOT NULL,
ADD CONSTRAINT evo_candidate_run_slot_key UNIQUE(run_id,slot),
ADD CONSTRAINT evo_candidate_outcome_check CHECK(outcome IN
('pending','mutation_failed','no_change','diff_failed','ast_rejected','contract_rejected',
'duplicate','evaluation_failed','succeeded','cancelled')),
ADD CONSTRAINT evo_candidate_success_check CHECK(outcome<>'succeeded'OR
(source_code IS NOT NULL AND source_hash IS NOT NULL AND evaluation_snapshot IS NOT NULL AND fitness IS NOT NULL));"""

CANDIDATE_DOWN = """DELETE FROM strategy_evo_candidates WHERE source_code IS NULL OR
source_hash IS NULL OR report IS NULL OR data_epoch IS NULL;
ALTER TABLE strategy_evo_candidates DROP CONSTRAINT evo_candidate_success_check,
DROP CONSTRAINT evo_candidate_outcome_check,DROP CONSTRAINT evo_candidate_run_slot_key,
DROP COLUMN slot,DROP COLUMN stage,DROP COLUMN outcome,DROP COLUMN audit_snapshot,
DROP COLUMN contract_snapshot,DROP COLUMN evaluation_snapshot,DROP COLUMN error_code,
DROP COLUMN error_message,DROP COLUMN input_tokens,DROP COLUMN output_tokens,
DROP COLUMN updated_at,ALTER COLUMN source_code SET NOT NULL,
ALTER COLUMN source_hash SET NOT NULL,ALTER COLUMN report SET NOT NULL,
ALTER COLUMN data_epoch SET NOT NULL;"""
