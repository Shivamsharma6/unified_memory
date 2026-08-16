ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS mtime_ns bigint,
    ADD COLUMN IF NOT EXISTS file_size bigint;

CREATE INDEX IF NOT EXISTS documents_path_stat_idx
    ON documents (path, mtime_ns, file_size);
