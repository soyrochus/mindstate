-- Enable Apache AGE
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';

-- Set search path so AGE functions are available
SET search_path = ag_catalog, "$user", public;

-- Create the AGE graph (idempotent)
DO $$
BEGIN
    PERFORM create_graph('mindstate');
EXCEPTION WHEN others THEN
    NULL; -- graph already exists
END;
$$;

-- Reset search path so all subsequent DDL lands in public
SET search_path = "$user", public;

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Core memory tables
CREATE TABLE IF NOT EXISTS memory_items (
    memory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    content_format TEXT NOT NULL DEFAULT 'text/plain',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    provenance_anchor TEXT NULL,
    occurred_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    contextualized_at TIMESTAMPTZ NULL,
    contextualization_skipped BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS memory_sources (
    memory_id UUID PRIMARY KEY REFERENCES memory_items(memory_id) ON DELETE CASCADE,
    source TEXT NULL,
    author TEXT NULL
);

CREATE TABLE IF NOT EXISTS memory_chunks (
    chunk_id BIGSERIAL PRIMARY KEY,
    memory_id UUID NOT NULL REFERENCES memory_items(memory_id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Embedding dimensions default to 1536 (OpenAI text-embedding-ada-002 / text-embedding-3-small).
-- If MS_EMBEDDING_DIMENSIONS is changed, drop and recreate this table to match.
CREATE TABLE IF NOT EXISTS memory_embeddings (
    embedding_id BIGSERIAL PRIMARY KEY,
    memory_id UUID NOT NULL REFERENCES memory_items(memory_id) ON DELETE CASCADE,
    chunk_id BIGINT NOT NULL REFERENCES memory_chunks(chunk_id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS memory_links (
    link_id BIGSERIAL PRIMARY KEY,
    memory_id UUID NOT NULL REFERENCES memory_items(memory_id) ON DELETE CASCADE,
    linked_memory_id UUID NULL REFERENCES memory_items(memory_id) ON DELETE SET NULL,
    relation_type TEXT NOT NULL,
    evidence TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS memory_contextualization_jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_ids UUID[] NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    queued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    error TEXT NULL,
    result JSONB NULL
);
