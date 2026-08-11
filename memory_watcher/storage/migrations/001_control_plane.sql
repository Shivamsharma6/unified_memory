CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS documents (
    memory_id uuid PRIMARY KEY,
    path text NOT NULL UNIQUE,
    memory_type text NOT NULL,
    status text NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived', 'deleted')),
    current_revision_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_revisions (
    revision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id uuid NOT NULL REFERENCES documents(memory_id) ON DELETE CASCADE,
    content_hash char(64) NOT NULL,
    title text NOT NULL,
    raw_markdown text NOT NULL,
    frontmatter jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_agent text,
    project text,
    occurred_at timestamptz,
    state text NOT NULL DEFAULT 'staged'
        CHECK (state IN ('staged', 'active', 'superseded', 'failed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    superseded_at timestamptz,
    UNIQUE (memory_id, content_hash)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'documents_current_revision_fk'
    ) THEN
        ALTER TABLE documents
            ADD CONSTRAINT documents_current_revision_fk
            FOREIGN KEY (current_revision_id)
            REFERENCES document_revisions(revision_id)
            DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS document_revisions_memory_state_idx
    ON document_revisions (memory_id, state, created_at DESC);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    revision_id uuid NOT NULL REFERENCES document_revisions(revision_id) ON DELETE CASCADE,
    memory_id uuid NOT NULL REFERENCES documents(memory_id) ON DELETE CASCADE,
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    heading_path text[] NOT NULL DEFAULT ARRAY[]::text[],
    content text NOT NULL,
    embedding_text text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english'::regconfig, coalesce(embedding_text, ''))
    ) STORED,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (revision_id, ordinal)
);

CREATE INDEX IF NOT EXISTS chunks_search_vector_gin_idx
    ON chunks USING gin (search_vector);
CREATE INDEX IF NOT EXISTS chunks_memory_revision_idx
    ON chunks (memory_id, revision_id);

CREATE TABLE IF NOT EXISTS entities (
    entity_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name text NOT NULL,
    normalized_key text NOT NULL UNIQUE,
    entity_type text NOT NULL DEFAULT 'concept',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS entity_aliases (
    entity_id uuid NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    alias text NOT NULL,
    normalized_key text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_id, normalized_key)
);

CREATE TABLE IF NOT EXISTS mentions (
    mention_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    revision_id uuid NOT NULL REFERENCES document_revisions(revision_id) ON DELETE CASCADE,
    memory_id uuid NOT NULL REFERENCES documents(memory_id) ON DELETE CASCADE,
    chunk_id uuid REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    entity_id uuid NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    surface_text text NOT NULL,
    context text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS mentions_entity_revision_idx
    ON mentions (entity_id, revision_id);
CREATE INDEX IF NOT EXISTS mentions_memory_revision_idx
    ON mentions (memory_id, revision_id);

CREATE TABLE IF NOT EXISTS claims (
    claim_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_entity_id uuid NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    predicate text NOT NULL,
    object_entity_id uuid REFERENCES entities(entity_id) ON DELETE CASCADE,
    object_value jsonb,
    evidence_memory_id uuid NOT NULL REFERENCES documents(memory_id) ON DELETE CASCADE,
    evidence_revision_id uuid NOT NULL REFERENCES document_revisions(revision_id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'explicit'
        CHECK (status IN ('explicit', 'candidate', 'retracted')),
    confidence double precision NOT NULL DEFAULT 1.0
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (object_entity_id IS NOT NULL OR object_value IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS claims_subject_predicate_idx
    ON claims (subject_entity_id, predicate, status);
CREATE INDEX IF NOT EXISTS claims_object_idx
    ON claims (object_entity_id) WHERE object_entity_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS claims_evidence_revision_idx
    ON claims (evidence_revision_id);

CREATE TABLE IF NOT EXISTS profiles (
    profile_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_type text NOT NULL CHECK (profile_type IN ('agent', 'user', 'project')),
    canonical_key text NOT NULL,
    display_name text NOT NULL,
    entity_id uuid REFERENCES entities(entity_id) ON DELETE SET NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (profile_type, canonical_key)
);

CREATE TABLE IF NOT EXISTS profile_facts (
    fact_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    fact_key text NOT NULL,
    fact_value jsonb NOT NULL,
    evidence_memory_id uuid NOT NULL REFERENCES documents(memory_id) ON DELETE CASCADE,
    evidence_revision_id uuid NOT NULL REFERENCES document_revisions(revision_id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'superseded', 'retracted')),
    valid_from timestamptz NOT NULL DEFAULT now(),
    valid_to timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS profile_facts_profile_key_idx
    ON profile_facts (profile_id, fact_key, status);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    job_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id uuid REFERENCES documents(memory_id) ON DELETE CASCADE,
    revision_id uuid REFERENCES document_revisions(revision_id) ON DELETE CASCADE,
    event_type text NOT NULL,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'retrying')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    error text,
    available_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ingestion_jobs_status_available_idx
    ON ingestion_jobs (status, available_at);

CREATE TABLE IF NOT EXISTS vector_outbox (
    outbox_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    command text NOT NULL CHECK (command IN ('upsert_revision', 'delete_revision', 'delete_memory')),
    memory_id uuid NOT NULL REFERENCES documents(memory_id) ON DELETE CASCADE,
    revision_id uuid REFERENCES document_revisions(revision_id) ON DELETE CASCADE,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'succeeded', 'failed')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    available_at timestamptz NOT NULL DEFAULT now(),
    locked_at timestamptz,
    locked_by text,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    UNIQUE (command, memory_id, revision_id)
);

CREATE INDEX IF NOT EXISTS vector_outbox_delivery_idx
    ON vector_outbox (status, available_at, outbox_id);

CREATE TABLE IF NOT EXISTS memory_audit_events (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    memory_id uuid REFERENCES documents(memory_id) ON DELETE SET NULL,
    revision_id uuid REFERENCES document_revisions(revision_id) ON DELETE SET NULL,
    event_type text NOT NULL,
    actor text,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS memory_audit_events_memory_time_idx
    ON memory_audit_events (memory_id, occurred_at DESC);
