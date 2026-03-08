## Purpose
Define Docker/database substrate naming and behavior guarantees for MindState.

## Requirements

### Requirement: Docker init script is named `init-mindstate.sql`
The PostgreSQL initialization SQL file SHALL be named `init-mindstate.sql`. The filename `init-tristore.sql` SHALL NOT exist in the repository.

#### Scenario: Init file name in repository
- **WHEN** the repository root is listed
- **THEN** `init-mindstate.sql` is present and `init-tristore.sql` is absent

#### Scenario: Dockerfile references correct init script
- **WHEN** the Dockerfile is inspected
- **THEN** the `COPY` instruction references `init-mindstate.sql`, not `init-tristore.sql`

### Requirement: Database substrate behavior is unchanged
The underlying PostgreSQL/AGE/pgvector stack SHALL remain the substrate for MindState after this feature set. These changes MAY add canonical memory, projection, and contextualization storage structures on top of that substrate, but they MUST NOT remove or break existing direct PostgreSQL, AGE, pgvector, or low-level query execution behavior.

#### Scenario: AGE extension loads correctly
- **WHEN** the application connects to the database
- **THEN** the AGE extension is loaded and Cypher queries execute successfully

#### Scenario: pgvector remains available
- **WHEN** the database container is initialized using `init-mindstate.sql`
- **THEN** both the `age` and `vector` extensions are available

#### Scenario: Existing substrate access remains available
- **WHEN** the application connects to the database after the feature set is implemented
- **THEN** direct PostgreSQL, AGE, and pgvector access still functions for existing low-level workflows

#### Scenario: Additive storage does not replace the substrate
- **WHEN** canonical memory tables, projection structures, or contextualization job tables are introduced
- **THEN** they are added on top of the current PostgreSQL/AGE/pgvector substrate rather than replacing it with a different backend

### Requirement: `run.sh` references MindState artifact names
Any shell scripts that reference Docker image names, container names, or init SQL filenames SHALL be updated to use MindState-oriented names.

#### Scenario: run.sh uses updated names
- **WHEN** `run.sh` is inspected
- **THEN** all references to TriStore artifact names are replaced with MindState equivalents

### Requirement: The substrate persists canonical memory and derived projections
The database substrate SHALL support persistence for canonical memory items and their derived chunk, embedding, and minimal relation-link projections.

#### Scenario: Canonical memory storage is backed by the substrate
- **WHEN** a memory item is remembered
- **THEN** the substrate stores the canonical record and its associated projection records in database-managed structures

#### Scenario: Derived projections remain queryable through the substrate
- **WHEN** embeddings or relation links are created for a memory item
- **THEN** they remain queryable through the existing PostgreSQL, pgvector, and graph-capable substrate layers

### Requirement: The substrate supports higher-level retrieval without removing direct inspection
The substrate SHALL support application-level semantic recall and context assembly while preserving direct low-level inspection paths.

#### Scenario: High-level retrieval and low-level inspection coexist
- **WHEN** the application adds semantic recall and context assembly behavior
- **THEN** those behaviors use the substrate while direct low-level inspection remains available to users and operators

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
