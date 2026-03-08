# Implementation Status — Post Feature 0002

**Date**: 2026-03-08
**Branch**: switch-to-mindstate
**Assessed against**: feature-0001, feature-0002, and the design documented in `docs/MindState-first-design-thoughts.md`

---

## 1. Executive summary

The implementation is further along than the openspec task list implies. Feature 0001 (rebase) is substantially complete at the code level — the package is already `mindstate/`, the executable and configuration use MindState naming, and the low-level REPL/TUI is intact. Feature 0002 (API and memory layer) is partially implemented, with the core service layer and HTTP API in place, but several specified behaviors are absent or stubbed.

The tri-store vision (RAG + Graph + document/NoSQL) is partially realized:

- **RAG** is fully implemented and on the critical path of every `remember()` call.
- **Graph** (Apache AGE) exists at the substrate level but is not wired into the memory service — it remains a manual Cypher interface only.
- **Document/NoSQL** is served by the relational `memory_items` table with JSONB metadata — pragmatic and functional, but not a dedicated layer.

The most significant gap relative to the stated design is the absence of graph projection from the `remember()` flow, the absence of a higher-level UI, and missing first-wave API endpoints (`/v1/memory/{id}`, `/v1/decisions/history`, etc.).

---

## 2. Feature 0001 — Rebase status

### What is done

| Item | Status |
|------|--------|
| Package renamed `cypherrepl` → `mindstate` | ✓ Done |
| Executable `mstate` registered in `pyproject.toml` | ✓ Done |
| `python -m mindstate` entry point | ✓ Done |
| CLI banner uses MindState identity | ✓ Done (`DEFAULT_SYSTEM_PROMPT` says "MindState agent") |
| REPL prompt changed to `mstate>` | Verify — `cli.py` still to confirm |
| `AGE_GRAPH` default → `"mindstate"` | ✓ Done (`config.py` line 138) |
| History file → `~/.mstate_history` | ✓ Done (`config.py` line 140) |
| `init-mindstate.sql` (renamed from `init-tristore.sql`) | ✓ Done |
| Dockerfile updated | ✓ Done (confirmed by SQL file presence) |
| `config.py` has `APISettings` and `MemorySettings` | ✓ Done — beyond Feature 0001 scope |

### What remains (Feature 0001 tasks not confirmed)

- TUI class rename `CypherReplTUI` → `MindStateTUI` — not confirmed from code read
- Full doc sweep (README updated; `REPL-MANUAL.md` not checked)
- `run.sh` still references `--name tristore` and `localhost/tristore-pg`

---

## 3. Feature 0002 — API and memory layer status

### 3.1 Canonical memory object

**Specified fields** (feature-0002, section 3.2):

| Field | In `memory_items` schema | Notes |
|-------|--------------------------|-------|
| identity (UUID) | ✓ `memory_id` | Auto-generated |
| kind | ✓ | Required |
| content | ✓ | Required |
| content_format | ✓ | Defaults to `text/plain` |
| source | ✓ | In `memory_sources` table |
| author | ✓ | In `memory_sources` table |
| timestamps | ✓ | `created_at` + `occurred_at` |
| metadata | ✓ | JSONB |
| provenance anchor | ✓ | `provenance_anchor TEXT` |

The canonical `MemoryItem` model is well-aligned with the feature spec. What is missing relative to the full design document (`docs/MindState-first-design-thoughts.md`) is `tenant_id`, `workspace_id`, `status` enum, `importance_score`, `confidence_score`, `version`, and `parent_item_id`. These were not required for Feature 0002 but will matter for Feature 3 and beyond.

### 3.2 Projection pipeline

| Projection | Status | Notes |
|------------|--------|-------|
| Raw canonical item | ✓ Implemented | `memory_items` + `memory_sources` |
| Chunk projection | ✓ Implemented | `memory_chunks`, word-boundary splitting |
| Embedding projection | ✓ Implemented | `memory_embeddings` via pgvector, OpenAI/Azure/local |
| Graph projection (AGE) | ✗ Not implemented | AGE is set up; `remember()` does not write to it |
| Relation/link projection | ⚠ Minimal | `memory_links` table — stores `provenance_anchor` links and explicit `memory:UUID` references found in content; no entity extraction |

The feature spec (section 3.3) required "a minimal graph projection or relation-link projection." The `memory_links` table satisfies the letter of this requirement conservatively. However, the spirit — that the graph layer captures structural information about entities and relations derived from memory content — is not yet met. No entity extraction, no relation inference, no AGE graph write from the service layer.

### 3.3 Retrieval

| Behavior | Status | Notes |
|----------|--------|-------|
| Semantic recall over embeddings | ✓ Implemented | `recall_by_embedding()` via pgvector cosine distance |
| Filter by kind | ✓ Implemented | `WHERE kind = ?` |
| Filter by source | ✓ Implemented | `WHERE source = ?` |
| Ranked result return | ✓ Implemented | Score = `1 / (1 + distance)` |
| Hybrid / graph-aware retrieval | ✗ Not implemented | Pure vector search only |
| Timeline / sequential retrieval | ✗ Not implemented | No endpoint to scan by `created_at` |
| Open-loop / decision-aware recall | ⚠ Partial | `get_recent_decisions()` used in `build_context()` only |

### 3.4 Context assembly

| Behavior | Status | Notes |
|----------|--------|-------|
| Overview synthesis | ⚠ Template string | Not LLM-generated; just counts items |
| Supporting raw items | ✓ Implemented | Top-N recalled items |
| Linked records | ✓ Implemented | `memory_links` + recent decisions |
| Provenance references | ✓ Implemented | source + provenance_anchor per item |
| Token budget / size limiting | ✗ Not implemented | `limit` param only, no token counting |

The `build_context()` implementation is structurally correct but the overview is a template string, not a synthesized summary. The design envisions an LLM-generated synthesis step here.

### 3.5 HTTP API

| Endpoint | Status | Notes |
|----------|--------|-------|
| `POST /v1/memory/remember` | ✓ Implemented | Full pipeline |
| `POST /v1/memory/recall` | ✓ Implemented | |
| `POST /v1/context/build` | ✓ Implemented | |
| `POST /v1/memory/lookup` | ⚠ 501 stub | Reserved |
| `POST /v1/memory/related` | ⚠ 501 stub | Reserved |
| `GET /v1/memory/{id}` | ✗ Not implemented | `inspect_memory()` exists in service but no route |
| `GET /v1/decisions/history` | ✗ Not implemented | `get_recent_decisions()` exists in db but no route |
| `GET /v1/topics/{id}/explain` | ✗ Not implemented | |
| `POST /v1/work-sessions/log` | ✗ Not implemented | |

The three foundational endpoints are implemented and match the feature spec. The recommended first-wave extensions are absent or stubbed.

### 3.6 Higher-level UI

| Item | Status |
|------|--------|
| Memory capture without Cypher | ✗ Not implemented |
| Semantic search without Cypher | ✗ Not implemented |
| Context bundle request | ✗ Not implemented |
| Memory item inspection | ✗ Not implemented |
| Extended TUI or web UI | ✗ Not implemented |

The UI requirement from feature-0002 (section 6) is entirely unimplemented. The existing CLI/TUI is the low-level Cypher shell. There is no higher-level interaction surface that exposes the memory service to a human user without HTTP knowledge.

### 3.7 Feature 0002 acceptance criteria — verdict

| Criterion | Status |
|-----------|--------|
| 1. API exposes remember, recall, build_context | ✓ |
| 2. Persists canonical items with raw and embedding projections | ✓ |
| 3. User-facing UI for capture and retrieval without Cypher | ✗ |
| 4. Existing low-level shell remains available | ✓ |
| 5. User can store, retrieve semantically, request context bundle | ✓ (via API only) |
| 6. Visibly built on brownfield base, not a rewrite | ✓ |
| 7. MindState vocabulary throughout | ✓ |

**Summary**: 5 of 7 acceptance criteria met. The blocking gap is criterion 3 — no higher-level UI exists.

---

## 4. Tri-store assessment

The design intent is a three-layer storage model: **RAG** (vector), **Graph** (AGE/Cypher), and **NoSQL/document**. Here is the honest current state:

### RAG layer

**Fully implemented and on the hot path.**

Every `remember()` call:
1. Chunks the content (word-boundary splitting, configurable size)
2. Embeds all chunks (OpenAI, Azure OpenAI, or local hash fallback)
3. Stores chunks in `memory_chunks`
4. Stores vectors in `memory_embeddings` (pgvector)

`recall()` performs cosine distance search (`<->` operator) over `memory_embeddings`, returning ranked `MemoryItem` results. This is correct and complete for the first version.

**Gaps**: No re-embedding pipeline, no embedding version tracking, no HNSW index configuration. The chunk splitter is word-count based — paragraph-aware or heading-aware chunking is not yet implemented.

### Graph layer (Apache AGE)

**Substrate exists; not wired into the memory service.**

The AGE extension is installed. `init-mindstate.sql` creates the `mindstate` graph. The CLI/TUI REPL exposes direct Cypher access, and `test-data-set.cypher` shows the intended domain model (Workspace, Person, Project, Task, Decision, Observation, Risk, Note, Idea with typed relations).

However:
- `remember()` does **not** write to the AGE graph.
- There is no entity extraction step.
- There is no relation inference step.
- The service layer has no Cypher write path.
- Graph traversal does not participate in `recall()` or `build_context()`.

The AGE graph is currently an independent substrate accessible only via the Cypher shell — not a projection derived from `remember()` calls. The design intends the graph to be a derived projection of canonical memory items.

**What would be needed**: an optional async step after `remember()` that (a) extracts entities and relations from content (LLM-assisted or rule-based), then (b) writes `MERGE` statements to the AGE graph. This is correctly identified as compute-heavy and optional per the design.

### Document/NoSQL layer

**Served by relational tables with JSONB — pragmatic and functional.**

`memory_items.metadata` (JSONB) provides flexible document storage. `memory_links` provides lightweight linking. This is not a dedicated NoSQL interface but is practically sufficient for the current scope.

**What is missing from the design**: dedicated `TopicDigest`, `EntityMention`, `RelationEdge`, `EmbeddingProjection`/`ChunkProjection` as first-class domain objects. These exist implicitly in the schema but are not surfaced as queryable objects via the API.

---

## 5. Sequential memory — specific assessment

The design document (`docs/MindState-first-design-thoughts.md`) and the user's stated requirement both call for memory that is stored as a **sequence**: every `remember()` appends a timestamped item and that ordering must be queryable.

| Requirement | Status | Notes |
|-------------|--------|-------|
| Append on `remember()` | ✓ | Every item gets `created_at = NOW()` |
| `occurred_at` for event-time ordering | ✓ | Optional field on `RememberInput` |
| Insertion order preserved | ✓ | UUID primary key + `created_at` index (implicit) |
| Sequential scan API (last N items) | ✗ | No endpoint exposes this |
| Timeline query (items since timestamp) | ✗ | No endpoint exposes this |
| Sequence-aware context assembly | ✗ | `build_context()` ranks by semantic similarity, not recency |

The data model already supports sequence retrieval — `SELECT * FROM memory_items ORDER BY created_at DESC LIMIT N` is trivially expressible. The gap is purely at the API and service layer: no route exposes sequential/temporal access. This is a small addition.

**RAG write on every `remember()`**: already implemented and correct.

**Graph write on `remember()` (optional)**: not implemented. This is the right call for the MVP — it requires entity extraction compute and an async pipeline that does not yet exist. When added, it should be a background job, not a synchronous step in the HTTP request.

---

## 6. Gap summary and priority

### Critical gaps (blocking full Feature 0002)

1. **No higher-level UI** — the most significant missing piece per the acceptance criteria. The API is complete but only accessible via HTTP. No TUI mode or web UI exposes memory capture/retrieval to a human without curl/Postman.

### Important gaps (near-term work)

2. **No sequential/temporal API** — `GET /v1/memory/recent?limit=N&since=<timestamp>` or equivalent. The data supports it; the route does not exist.
3. **`GET /v1/memory/{id}` route missing** — `inspect_memory()` is implemented in the service but has no HTTP endpoint.
4. **`GET /v1/decisions/history` route missing** — `get_recent_decisions()` is implemented in the DB layer but has no HTTP endpoint.
5. **Context overview is not synthesized** — `build_context()` returns a template string. An LLM synthesis step would make it genuinely useful.

### Medium-term gaps (Feature 0003 territory)

6. **No graph projection from `remember()`** — AGE is present but disconnected from the memory service. Adding an async entity extraction + graph write pipeline is the right approach.
7. **No MCP server** — Feature 0003. The service layer is now ready to be the backend for an MCP adapter.
8. **No workspace/tenant scoping** — `memory_items` has no `workspace_id`. Multi-context isolation requires schema changes.
9. **No `status` lifecycle on memory items** — items cannot be archived, superseded, or soft-deleted via the current schema.

### Low priority / deferred

10. No embedding version tracking or re-embedding pipeline.
11. No importance/confidence scoring.
12. No digest/summary objects.
13. No HNSW index tuning.

---

## 7. What to build next

In priority order:

1. **Sequential recall endpoint** — small, enables the core sequence-as-memory use case. `GET /v1/memory/recent` ordered by `created_at`.
2. **`GET /v1/memory/{id}` route** — the service method exists, add the route.
3. **`GET /v1/decisions/history` route** — same pattern.
4. **Higher-level TUI mode** — a new TUI screen that surfaces `remember`, `recall`, and `build_context` without Cypher. This closes the Feature 0002 UI criterion.
5. **LLM-generated context overview** — replace the template string in `build_context()` with a short LLM synthesis call.
6. **Optional async graph projection** — background entity extraction + AGE `MERGE` after `remember()`. Design as an optional pipeline step, not a blocking synchronous call.
7. **MCP adapter** — Feature 0003. Wire `MindStateService` into an MCP tool surface exposing `remember`, `recall`, `build_context`, `recent`.
