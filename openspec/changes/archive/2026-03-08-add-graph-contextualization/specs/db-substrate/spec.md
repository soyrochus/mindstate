## ADDED Requirements

### Requirement: `memory_items` has `contextualized_at` and `contextualization_skipped` columns
The `memory_items` table SHALL have two new columns added via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`:
- `contextualized_at TIMESTAMPTZ NULL` — NULL means the item has not been graph-contextualized and is eligible for `contextualize(n)`
- `contextualization_skipped BOOLEAN NOT NULL DEFAULT FALSE` — TRUE means the item is permanently excluded from automatic selection

These columns SHALL be added by `ensure_memory_schema` on startup. Existing rows receive `contextualized_at = NULL` and `contextualization_skipped = FALSE` by default.

#### Scenario: New columns present after schema ensure
- **WHEN** `ensure_memory_schema` runs on a database that had the previous schema
- **THEN** `memory_items` has both `contextualized_at` and `contextualization_skipped` columns with correct types and defaults

#### Scenario: Existing rows receive correct defaults
- **WHEN** `memory_items` contains rows created before this migration
- **THEN** those rows have `contextualized_at = NULL` and `contextualization_skipped = FALSE`

#### Scenario: `contextualized_at` updated on successful contextualization
- **WHEN** `GraphContextualizer` completes processing for a memory item
- **THEN** `memory_items.contextualized_at` is set to the completion timestamp for that item

### Requirement: `memory_contextualization_jobs` table tracks async job state
The `memory_contextualization_jobs` table SHALL be created with `CREATE TABLE IF NOT EXISTS` by `ensure_memory_schema`. Schema:

```sql
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
```

Valid `status` values are `queued`, `running`, `done`, `failed`.

#### Scenario: Table created on startup
- **WHEN** `ensure_memory_schema` runs for the first time
- **THEN** `memory_contextualization_jobs` exists with all required columns

#### Scenario: Job row inserted on contextualize call
- **WHEN** `contextualize(n=1)` is called with an eligible item
- **THEN** a row is inserted into `memory_contextualization_jobs` with `status = 'queued'` and `memory_ids` containing the selected UUID(s)

#### Scenario: Additive migration does not affect existing tables
- **WHEN** `ensure_memory_schema` runs on a database with existing `memory_items` data
- **THEN** no existing rows are modified or deleted; only new columns and the new table are added
