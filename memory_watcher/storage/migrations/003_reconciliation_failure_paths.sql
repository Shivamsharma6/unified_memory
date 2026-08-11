ALTER TABLE ingestion_jobs
    ADD COLUMN IF NOT EXISTS vault_path text;

CREATE INDEX IF NOT EXISTS ingestion_jobs_failed_vault_path_idx
    ON ingestion_jobs (vault_path)
    WHERE event_type = 'reconcile' AND status = 'failed';
