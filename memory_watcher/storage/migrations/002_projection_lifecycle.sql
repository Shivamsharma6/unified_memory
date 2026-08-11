ALTER TABLE claims
    DROP CONSTRAINT IF EXISTS claims_status_check;

ALTER TABLE claims
    ADD CONSTRAINT claims_status_check
    CHECK (status IN ('explicit', 'verified', 'candidate', 'retracted'));

ALTER TABLE profile_facts
    DROP CONSTRAINT IF EXISTS profile_facts_status_check;

ALTER TABLE profile_facts
    ADD CONSTRAINT profile_facts_status_check
    CHECK (status IN ('staged', 'active', 'superseded', 'retracted'));
