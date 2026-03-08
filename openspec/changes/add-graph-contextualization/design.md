## Context

MindState has a working Tier 1 memory pipeline: `remember()` stores an item, chunks it, embeds it, and makes it immediately available for RAG via `recall()`. The graph substrate (Apache AGE, `mindstate` graph) is installed and initialized but receives no writes from the memory path.

The AGE connection model is psycopg2 with a raw SQL wrapper for Cypher:
```sql
SELECT * FROM cypher('mindstate', $$ MATCH ... $$) AS (col agtype);
```
This is already used in the REPL and TUI. The contextualization pipeline reuses the same connection pattern.

`MindStateService` is constructed per-request in the API (via `Depends`) and per-session in the REPL. It holds a live psycopg2 `conn`/`cur` pair. The `ensure_memory_schema` function runs additive `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` — this is the established migration pattern, no migration framework is in use.

## Goals / Non-Goals

**Goals:**
- Feed the AGE graph from the memory write path without blocking it
- Provide explicit `contextualize(n)` / `contextualize(ids)` targeting across REPL, HTTP, and MCP surfaces
- Implement `AUTO_CONTEXTUALIZE_KINDS` policy as a configurable default
- Track job state and contextualization status on items; support retry via NULL `contextualized_at`
- Keep Tier 1 failure-safe: contextualization failure must never roll back a committed `remember()` write

**Non-Goals:**
- Hybrid retrieval (`recall()` augmented with graph traversal) — enabled by this feature but not implemented here
- AGE entity merge UI or conflict resolution tooling
- Full async framework (asyncio, Celery, etc.) — Python threading is sufficient for this use case
- Schema versioning or a migration framework — the existing additive pattern is continued

## Decisions

### Decision 1: New module `mindstate/contextualizer.py`

`GraphContextualizer` lives in its own module rather than being added to `memory_service.py`. Rationale: the contextualization pipeline has distinct dependencies (LLM structured output, AGE MERGE writes, job state management) that would bloat `MindStateService`. `MindStateService.remember()` gains only a thin `contextualize: bool` parameter; it delegates immediately to a `ContextualizationDispatcher`.

Alternatives considered:
- Inline in `memory_service.py`: rejected — conflates two tiers that are deliberately independent
- Separate package (`mindstate/graph/`): overkill for one module at this stage

### Decision 2: In-process threading for async execution

Contextualization jobs run in a `threading.Thread` (daemon). No external queue, no asyncio, no worker process.

Rationale: the job volume is low (one item at a time in typical agent usage), the DB is local/containerized, and the codebase has no async infrastructure. Adding Celery or asyncio would require a queue broker and a fundamental architectural shift for marginal benefit.

The `memory_contextualization_jobs` table acts as the durable job log. If the process dies mid-job, the job row stays `running`; on next startup (or retry), a `contextualize(n)` call will pick up items with `contextualized_at IS NULL`. This is acceptable — jobs are retryable by design.

Alternatives considered:
- FastAPI `BackgroundTasks`: only available in the HTTP surface; REPL and MCP would need a different mechanism
- `asyncio`: requires converting the entire psycopg2 layer to asyncpg or aiopg — too large a change

### Decision 3: New psycopg2 connection per contextualization job

Each job opens its own short-lived DB connection rather than sharing the caller's `conn`/`cur`. Rationale: the caller's connection commits and closes before the background thread starts; sharing it across threads is not safe with psycopg2. The connection is opened at thread start and closed at thread end.

### Decision 4: LLM structured output via LangChain + Pydantic

Entity recognition and relation inference use `langchain_openai.ChatOpenAI` (or Azure equivalent, driven by `LLM_PROVIDER`) with `.with_structured_output(PydanticModel)`. This reuses the existing LLM configuration in `Settings.llm` and requires no new dependencies.

The entity recognition prompt is tight and types-constrained: the LLM receives the content and the controlled entity type list; it returns a list of `{surface_form, entity_type, confidence}` objects. Anything outside the controlled set is omitted by prompt instruction.

### Decision 5: Conservative entity resolution order

Resolution runs in three steps, stopping at the first confident match:
1. **Normalized exact match**: lowercase, strip punctuation, collapse whitespace — query existing `ag_catalog` nodes
2. **Embedding similarity**: embed the surface form, compare against stored entity canonical name embeddings using `memory_embeddings` cosine similarity (threshold `MS_CONTEXTUALIZE_MERGE_THRESHOLD`, default 0.92)
3. **LLM disambiguation**: only if steps 1–2 are inconclusive AND entity confidence > threshold — ask the LLM with a candidate list

If all three are inconclusive, a new node is created. This conservative policy prevents false merges, which are harder to detect and repair than duplicate nodes.

Entity name embeddings are stored in `memory_embeddings` with `model_name = 'entity_canonical'` to distinguish them from chunk embeddings.

### Decision 6: AGE writes via raw SQL Cypher wrapper

```python
cur.execute(
    "SELECT * FROM cypher(%s, $$ MERGE (e:Person {id: %s, canonical_name: %s}) $$) AS (v agtype)",
    (graph_name, entity_id, canonical_name)
)
```

This reuses the existing AGE query pattern. No dedicated AGE client library is added. All MERGE statements for a single item are executed in one transaction; if any fails, the transaction rolls back, `contextualized_at` stays NULL, and the item is eligible for retry.

### Decision 7: Schema migration via existing additive pattern

New columns are added with `ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS ...` in `ensure_memory_schema`. The new `memory_contextualization_jobs` table uses `CREATE TABLE IF NOT EXISTS`. This is consistent with how all existing tables are managed and requires no migration tooling.

## Risks / Trade-offs

**[Risk] Thread-per-job leaks connections if items accumulate faster than threads complete** → Mitigation: `MS_CONTEXTUALIZE_MAX_ENTITIES_PER_ITEM` bounds per-item LLM calls; typical agent usage is serial. Add a simple thread pool cap (max 4 concurrent jobs) in the dispatcher.

**[Risk] LLM disambiguation in Step 3 adds latency and cost per entity** → Mitigation: Step 3 only fires when Steps 1–2 are inconclusive AND entity confidence is high. Low-confidence entities skip to "create new" directly.

**[Risk] `contextualized_at NULL` used as both "not yet run" and "failed" could cause unbounded retries on deterministically-failing items** → Mitigation: `contextualization_skipped = TRUE` flag for items where failure is deterministic (e.g., content too short). The `contextualize(n)` selector always excludes `skipped = TRUE` items.

**[Risk] AGE node ID collisions across entity types** → Mitigation: node IDs are namespaced by type: `{entity_type}.{normalized_name}` (e.g., `person.ada_lovelace`). Within-type collisions are resolved by the merge policy; cross-type conflicts cannot occur.

**[Risk] `remember()` callers that pass `contextualize=True` on a non-auto kind get silent success even if contextualization is disabled** → Mitigation: `MS_CONTEXTUALIZE_ENABLED=false` suppresses job creation; `remember()` still returns `memory_id` normally. The job is simply not enqueued.

## Migration Plan

1. `ensure_memory_schema` additions run on first startup after deploy:
   - `ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS contextualized_at TIMESTAMPTZ NULL`
   - `ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS contextualization_skipped BOOLEAN NOT NULL DEFAULT FALSE`
   - `CREATE TABLE IF NOT EXISTS memory_contextualization_jobs (...)`
2. Existing `memory_items` rows get `contextualized_at = NULL` and `contextualization_skipped = FALSE` by default — they are immediately eligible for `contextualize(n)` if desired
3. No rollback needed: columns are additive and nullable/defaulted; the old code path ignores them

## Open Questions

- **Entity canonical name embedding storage**: storing entity embeddings in `memory_embeddings` with a special `model_name` marker is expedient but mixes concerns. A dedicated `entity_embeddings` table would be cleaner. Deferred to a follow-up unless the mixed-table approach causes query complexity.
- **MCP tool signature**: the MCP surface is listed in the feature spec but MCP tooling is Feature 4. The `contextualize` method on `MindStateService` will be ready; MCP wiring is deferred.
- **Job result schema in `result JSONB`**: the column exists for future use; this feature will write a summary `{entities: N, relations: N, nodes_created: N, nodes_merged: N}` but the schema is not contracted yet.
