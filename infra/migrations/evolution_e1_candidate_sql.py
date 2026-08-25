CANDIDATE_UP = (
    """ALTER TABLE strategy_evo_candidates
    ALTER COLUMN source_code DROP NOT NULL,
    ALTER COLUMN source_hash DROP NOT NULL,
    ALTER COLUMN report DROP NOT NULL,
    ALTER COLUMN data_epoch DROP NOT NULL,
    ADD COLUMN slot INT, ADD COLUMN stage TEXT, ADD COLUMN outcome TEXT,
    ADD COLUMN audit_snapshot JSONB, ADD COLUMN contract_snapshot JSONB,
    ADD COLUMN evaluation_snapshot JSONB, ADD COLUMN error_code TEXT,
    ADD COLUMN error_message TEXT, ADD COLUMN input_tokens INT,
    ADD COLUMN output_tokens INT, ADD COLUMN updated_at TIMESTAMPTZ;""",
    """WITH ranked AS (
      SELECT candidate_id,
        row_number() OVER (PARTITION BY run_id ORDER BY created_at, candidate_id) - 1 AS n
      FROM strategy_evo_candidates
    )
    UPDATE strategy_evo_candidates AS candidate SET slot = ranked.n,
      stage = 'legacy', outcome = 'legacy_unknown',
      evaluation_snapshot = candidate.report, updated_at = candidate.created_at
    FROM ranked WHERE candidate.candidate_id = ranked.candidate_id;""",
    """ALTER TABLE strategy_evo_candidates
    ADD CONSTRAINT evo_candidate_required_fields_check
    CHECK (slot IS NOT NULL AND stage IS NOT NULL AND outcome IS NOT NULL
      AND updated_at IS NOT NULL) NOT VALID;
    ALTER TABLE strategy_evo_candidates
    VALIDATE CONSTRAINT evo_candidate_required_fields_check;
    ALTER TABLE strategy_evo_candidates
    ALTER COLUMN slot SET NOT NULL,
    ALTER COLUMN stage SET DEFAULT 'queued', ALTER COLUMN stage SET NOT NULL,
    ALTER COLUMN outcome SET DEFAULT 'pending', ALTER COLUMN outcome SET NOT NULL,
    ALTER COLUMN updated_at SET DEFAULT NOW(), ALTER COLUMN updated_at SET NOT NULL;
    ALTER TABLE strategy_evo_candidates
    DROP CONSTRAINT evo_candidate_required_fields_check;
    ALTER TABLE strategy_evo_candidates ADD CONSTRAINT evo_candidate_run_slot_key
    UNIQUE (run_id, slot);""",
    """ALTER TABLE strategy_evo_candidates ADD CONSTRAINT evo_candidate_stage_check
    CHECK (stage IN ('legacy','queued','mutation','evaluation','completed')) NOT VALID;
    ALTER TABLE strategy_evo_candidates ADD CONSTRAINT evo_candidate_outcome_check
    CHECK (outcome IN ('legacy_unknown','pending','mutation_failed','no_change',
      'diff_failed','ast_rejected','contract_rejected','duplicate',
      'evaluation_failed','succeeded','cancelled')) NOT VALID;
    ALTER TABLE strategy_evo_candidates ADD CONSTRAINT evo_candidate_success_check
    CHECK (outcome <> 'succeeded' OR (stage = 'completed'
      AND source_code IS NOT NULL AND source_hash IS NOT NULL
      AND evaluation_snapshot IS NOT NULL AND fitness IS NOT NULL
      AND data_epoch IS NOT NULL AND report IS NOT NULL)) NOT VALID;
    ALTER TABLE strategy_evo_candidates VALIDATE CONSTRAINT evo_candidate_stage_check;
    ALTER TABLE strategy_evo_candidates VALIDATE CONSTRAINT evo_candidate_outcome_check;
    ALTER TABLE strategy_evo_candidates VALIDATE CONSTRAINT evo_candidate_success_check;""",
)

CANDIDATE_DOWN = (
    """ALTER TABLE strategy_evo_candidates
    DROP CONSTRAINT evo_candidate_success_check,
    DROP CONSTRAINT evo_candidate_outcome_check,
    DROP CONSTRAINT evo_candidate_stage_check,
    DROP CONSTRAINT evo_candidate_run_slot_key;""",
    """ALTER TABLE strategy_evo_candidates
    DROP COLUMN slot, DROP COLUMN stage, DROP COLUMN outcome,
    DROP COLUMN audit_snapshot, DROP COLUMN contract_snapshot,
    DROP COLUMN evaluation_snapshot, DROP COLUMN error_code,
    DROP COLUMN error_message, DROP COLUMN input_tokens,
    DROP COLUMN output_tokens, DROP COLUMN updated_at,
    ALTER COLUMN source_code SET NOT NULL,
    ALTER COLUMN source_hash SET NOT NULL,
    ALTER COLUMN report SET NOT NULL,
    ALTER COLUMN data_epoch SET NOT NULL;""",
)
