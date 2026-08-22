-- Performance indexes for fast revision lookup, search filtering, and outbox polling.

CREATE INDEX IF NOT EXISTS idx_doc_revisions_state_mem
    ON document_revisions(state, memory_id);

CREATE INDEX IF NOT EXISTS idx_doc_revisions_superseded
    ON document_revisions(superseded_at)
    WHERE superseded_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_vector_outbox_status_avail
    ON vector_outbox(status, available_at);

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status_event
    ON ingestion_jobs(status, event_type, created_at);

CREATE INDEX IF NOT EXISTS idx_documents_status_type
    ON documents(status, memory_type);

CREATE INDEX IF NOT EXISTS idx_chunks_revision_mem
    ON chunks(revision_id, memory_id);

CREATE INDEX IF NOT EXISTS idx_claims_evidence_rev
    ON claims(evidence_revision_id, status);

CREATE INDEX IF NOT EXISTS idx_mentions_rev_entity
    ON mentions(revision_id, entity_id);
