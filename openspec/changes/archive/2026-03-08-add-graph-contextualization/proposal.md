## Why

MindState has a working RAG layer (Feature 2) but an idle graph layer: Apache AGE is installed and the `mindstate` graph exists, but `remember()` never writes to it. Retrieval is purely semantic — no entity anchoring, no structural traversal, no hybrid recall. This feature feeds the graph through a deliberate, cost-controlled enrichment operation that runs after the Tier 1 write and never blocks it.

## What Changes

- New `GraphContextualizer` pipeline: LLM-assisted entity recognition → entity resolution against AGE → relation inference → AGE `MERGE` writes → `memory_links` sync
- New `contextualize(n)` / `contextualize(ids=[...])` operation exposed on REPL, HTTP API, and MCP tool
- `remember(..., contextualize=True)` convenience shorthand that enqueues contextualization after the Tier 1 write
- Kind-aware automatic contextualization: items whose `kind` is in `AUTO_CONTEXTUALIZE_KINDS` are contextualized without explicit opt-in
- New job queue table `memory_contextualization_jobs` for async execution, status polling, and retry
- Two new columns on `memory_items`: `contextualized_at` (NULL = eligible for retry) and `contextualization_skipped`
- Five new `MS_CONTEXTUALIZE_*` configuration variables plus `MS_AUTO_CONTEXTUALIZE_KINDS`
- New `\contextualize` command in the CLI REPL

## Capabilities

### New Capabilities

- `graph-contextualization`: The `GraphContextualizer` pipeline — entity recognition (LLM, structured output), entity resolution (normalize → embedding similarity → LLM disambiguation), relation inference (controlled relation set), AGE MERGE writes, `memory_links` sync, and `memory_items.contextualized_at` update. Includes kind-aware auto-trigger policy and the `contextualize=True` flag on `remember()`.
- `contextualization-jobs`: Async job queue backed by `memory_contextualization_jobs` table. Covers job creation, status lifecycle (`queued → running → done | failed`), status polling via HTTP, and retry semantics (failed items remain eligible via NULL `contextualized_at`).

### Modified Capabilities

- `cli-repl`: New `\contextualize [n]` and `\contextualize --id <UUID>` REPL commands.
- `configuration`: Six new environment variables — `MS_AUTO_CONTEXTUALIZE_KINDS`, `MS_CONTEXTUALIZE_CONFIDENCE_THRESHOLD`, `MS_CONTEXTUALIZE_MERGE_THRESHOLD`, `MS_CONTEXTUALIZE_MAX_ENTITIES_PER_ITEM`, `MS_CONTEXTUALIZE_ENABLED`.
- `db-substrate`: Schema migration — two new columns on `memory_items`, one new table `memory_contextualization_jobs`.

## Impact

- **New module**: `mindstate/contextualization.py` (or `mindstate/graph/contextualizer.py`) — `GraphContextualizer` class and job dispatch logic
- **Modified**: `mindstate/memory.py` — `remember()` gains `contextualize: bool` param and kind-policy check; no behavior change to existing callers
- **Modified**: `mindstate/api.py` — two new endpoints: `POST /v1/memory/contextualize`, `GET /v1/memory/contextualize/{job_id}`; `POST /v1/memory` gains optional `contextualize` field
- **Modified**: `mindstate/__main__.py` — `\contextualize` REPL command
- **Modified**: `mindstate/config.py` — six new settings with defaults
- **Database**: migration adds two columns and one table; no existing columns altered
- **Dependencies**: no new packages — uses existing `langchain`, `psycopg2`, `langchain-openai`
- **Tier 1 guarantee**: `remember()` return path is unchanged; contextualization failure cannot affect stored items or RAG availability
