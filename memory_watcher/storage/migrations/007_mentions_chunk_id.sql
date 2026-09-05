-- Index mentions.chunk_id to ensure fast cascades and avoid table scans during chunk deletion.

CREATE INDEX IF NOT EXISTS idx_mentions_chunk_id
    ON mentions(chunk_id);
