-- Migration 003: Bitemporal Claims and Invalidation Tracking

ALTER TABLE claims
    ADD COLUMN IF NOT EXISTS valid_from timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS valid_to timestamptz,
    ADD COLUMN IF NOT EXISTS invalidated_by_claim_id uuid REFERENCES claims(claim_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS claims_validity_idx
    ON claims (subject_entity_id, predicate, valid_from, valid_to);

ALTER TABLE claims
    DROP CONSTRAINT IF EXISTS claims_status_check;

ALTER TABLE claims
    ADD CONSTRAINT claims_status_check
    CHECK (status IN ('explicit', 'verified', 'candidate', 'superseded', 'retracted'));
