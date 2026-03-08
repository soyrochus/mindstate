## 1. Schema Migration

- [ ] 1.1 Add `contextualized_at TIMESTAMPTZ NULL` and `contextualization_skipped BOOLEAN NOT NULL DEFAULT FALSE` columns to `memory_items` via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` in `ensure_memory_schema`
- [ ] 1.2 Add `CREATE TABLE IF NOT EXISTS memory_contextualization_jobs` with columns `job_id`, `memory_ids`, `status`, `queued_at`, `started_at`, `completed_at`, `error`, `result` in `ensure_memory_schema`
- [ ] 1.3 Verify migration is additive: existing rows get correct defaults, no data loss on re-run

## 2. Configuration

- [ ] 2.1 Add `ContextualizationSettings` dataclass to `config.py` with fields: `enabled`, `auto_kinds`, `confidence_threshold`, `merge_threshold`, `max_entities_per_item`
- [ ] 2.2 Populate `ContextualizationSettings` in `get_settings()` from env vars `MS_CONTEXTUALIZE_ENABLED`, `MS_AUTO_CONTEXTUALIZE_KINDS`, `MS_CONTEXTUALIZE_CONFIDENCE_THRESHOLD`, `MS_CONTEXTUALIZE_MERGE_THRESHOLD`, `MS_CONTEXTUALIZE_MAX_ENTITIES_PER_ITEM` with documented defaults
- [ ] 2.3 Add `contextualization: ContextualizationSettings` field to `Settings` dataclass

## 3. Data Models

- [ ] 3.1 Add `ContextualizeInput` model to `memory_models.py` with fields: `n: Optional[int]`, `ids: Optional[List[str]]` (exactly one must be set)
- [ ] 3.2 Add `ContextualizeJobResponse` model with fields: `job_id`, `queued_count`, `status`
- [ ] 3.3 Add `ContextualizeJobStatus` model with fields: `job_id`, `status`, `queued_count`, `started_at`, `completed_at`, `error`, `result`
- [ ] 3.4 Add `contextualized_at` and `contextualization_skipped` fields to `MemoryItem` dataclass

## 4. Database Layer (`memory_db.py`)

- [ ] 4.1 Add `get_eligible_for_contextualization(cur, n) -> List[str]` — selects up to n `memory_ids` where `contextualized_at IS NULL AND contextualization_skipped = FALSE ORDER BY created_at DESC LIMIT n`
- [ ] 4.2 Add `create_contextualization_job(cur, conn, memory_ids) -> str` — inserts a row into `memory_contextualization_jobs` with `status='queued'`, returns `job_id`
- [ ] 4.3 Add `get_contextualization_job(cur, job_id) -> Optional[dict]` — fetches a job row by UUID
- [ ] 4.4 Add `update_job_status(cur, conn, job_id, status, ...)` — updates `status`, `started_at`, `completed_at`, `error`, `result` as appropriate
- [ ] 4.5 Add `set_contextualized_at(cur, conn, memory_id)` — sets `contextualized_at = NOW()` for one item
- [ ] 4.6 Add `set_contextualization_skipped(cur, conn, memory_id)` — sets `contextualization_skipped = TRUE`

## 5. GraphContextualizer (`mindstate/contextualizer.py`)

- [ ] 5.1 Create `mindstate/contextualizer.py` with `GraphContextualizer` class; constructor accepts `settings: Settings` and opens its own psycopg2 connection
- [ ] 5.2 Implement Stage 1: `_recognize_entities(content) -> List[EntityCandidate]` — LLM structured output call using `langchain_openai` with controlled entity type list; apply confidence threshold and entity cap
- [ ] 5.3 Implement Stage 2 step 1: `_resolve_exact(surface_form, entity_type) -> Optional[str]` — normalize (lowercase, strip punctuation, collapse whitespace) and query AGE for matching node by type
- [ ] 5.4 Implement Stage 2 step 2: `_resolve_by_embedding(surface_form, entity_type) -> Optional[str]` — embed surface form, compare against stored entity canonical name embeddings in `memory_embeddings`, return node id if similarity ≥ `merge_threshold`
- [ ] 5.5 Implement Stage 2 step 3: `_resolve_by_llm(surface_form, entity_type, candidates) -> Optional[str]` — ask LLM to disambiguate surface form against a short candidate list; only called when confidence > threshold and steps 1–2 inconclusive
- [ ] 5.6 Implement `_resolve_entity(candidate) -> ResolvedEntity` — orchestrates steps 1–3 in order, creates new node if all inconclusive; uses namespaced ID `{entity_type}.{normalized_name}`
- [ ] 5.7 Implement Stage 3: `_infer_relations(memory_id, content, resolved_entities) -> List[InferredRelation]` — LLM structured output call returning typed relations from the controlled set only
- [ ] 5.8 Implement Stage 4: `_write_to_age(memory_id, memory_item, resolved_entities, relations)` — emit AGE MERGE statements and `memory_links` inserts in one transaction; call `set_contextualized_at` on success
- [ ] 5.9 Implement `run(memory_id: str)` — orchestrates stages 1–4; on any exception logs error and leaves `contextualized_at` NULL; sets `contextualization_skipped` for deterministic failures (content < 10 words)
- [ ] 5.10 Add entity canonical name embedding storage: after creating a new AGE node, store its canonical name embedding in `memory_embeddings` with `model_name = 'entity_canonical'`

## 6. Job Dispatcher (`mindstate/contextualizer.py`)

- [ ] 6.1 Add `ContextualizationDispatcher` class with a thread pool cap of 4 concurrent jobs
- [ ] 6.2 Implement `dispatch(memory_ids: List[str]) -> ContextualizeJobResponse` — creates job row, spawns daemon thread, returns job reference immediately
- [ ] 6.3 Implement the thread worker: sets job to `running`, calls `GraphContextualizer.run()` per item, sets job to `done` or `failed`, closes DB connection
- [ ] 6.4 Implement `contextualize_n(cur, conn, settings, n: int) -> ContextualizeJobResponse` — selects eligible IDs, returns empty response if none, otherwise dispatches
- [ ] 6.5 Implement `contextualize_ids(cur, conn, settings, ids: List[str]) -> ContextualizeJobResponse` — validates IDs exist, dispatches

## 7. MindStateService Integration

- [ ] 7.1 Add `contextualize: bool = False` parameter to `MindStateService.remember()`
- [ ] 7.2 After `commit()` in `remember()`, check if `contextualize=True` or `payload.kind in settings.contextualization.auto_kinds` and `settings.contextualization.enabled`; if so, call `dispatcher.dispatch([memory_id])`
- [ ] 7.3 Add `contextualize_n(n: int) -> ContextualizeJobResponse` method to `MindStateService`
- [ ] 7.4 Add `contextualize_ids(ids: List[str]) -> ContextualizeJobResponse` method to `MindStateService`
- [ ] 7.5 Add `get_contextualization_job(job_id: str) -> Optional[dict]` method to `MindStateService`
- [ ] 7.6 Update `inspect_memory()` return value to include `contextualized_at` and `contextualization_skipped` fields

## 8. HTTP API

- [ ] 8.1 Add `ContextualizeRequest` Pydantic model to `api.py` with optional `n: int` and `ids: List[str]`; add validator requiring exactly one of `n` or `ids`
- [ ] 8.2 Add `POST /v1/memory/contextualize` endpoint — delegates to `svc.contextualize_n()` or `svc.contextualize_ids()` based on request body; returns `ContextualizeJobResponse`
- [ ] 8.3 Add `GET /v1/memory/contextualize/{job_id}` endpoint — delegates to `svc.get_contextualization_job()`; returns 404 if not found
- [ ] 8.4 Add optional `contextualize: bool = False` field to `RememberRequest`; pass it through to `svc.remember()`

## 9. CLI REPL

- [ ] 9.1 Add `\contextualize` command handler to `__main__.py`; parse `[n]` and `--id <UUID>` variants
- [ ] 9.2 Call `svc.contextualize_n(n)` or `svc.contextualize_ids([uuid])` based on parsed args; print job_id and queued_count
- [ ] 9.3 Add `\contextualize` to the `\h` help listing with a usage description

## 10. Tests

- [ ] 10.1 Unit test `ContextualizationSettings`: defaults, env override for each variable
- [ ] 10.2 Unit test `ensure_memory_schema` migration: new columns present, existing data unaffected
- [ ] 10.3 Unit test `get_eligible_for_contextualization`: respects `contextualized_at` and `contextualization_skipped` filters; correct ordering
- [ ] 10.4 Unit test `GraphContextualizer` entity recognition: mocked LLM, confidence filtering, entity cap
- [ ] 10.5 Unit test entity resolution: exact match, embedding match, new-node fallback (each step mocked)
- [ ] 10.6 Unit test `remember()` auto-kind policy: `decision` enqueues job, `note` does not; `contextualize=True` overrides
- [ ] 10.7 Unit test `MS_CONTEXTUALIZE_ENABLED=false` suppresses all job creation
- [ ] 10.8 Integration test `POST /v1/memory/contextualize` n-mode and ids-mode via TestClient
- [ ] 10.9 Integration test `GET /v1/memory/contextualize/{job_id}` returns correct status; 404 for unknown
- [ ] 10.10 Regression test: `remember()` / `recall()` / `build_context()` behavior unchanged when contextualization is not triggered
