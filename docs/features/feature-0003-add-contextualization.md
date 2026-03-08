# Feature 3 — Add graph contextualization to the memory layer

## Intent

The canonical memory pipeline (`remember`) is intentionally dumb: it stores a raw item, chunks it, and embeds it. That is correct. The RAG layer is always available immediately after a write, at minimal cost, with no LLM call on the write path.

Graph contextualization is a qualitatively different operation. It requires LLM reasoning to extract entities, resolve them against existing graph nodes, and infer typed relations. It is powerful but costly, fallible, and not uniformly valuable across all memory items. Applying it unconditionally to every write would generate noise, incur unnecessary cost, and couple a fast write path to a slow reasoning step.

This feature introduces graph contextualization as a **deliberate, cost-controlled, second-tier enrichment operation** that can be triggered explicitly by the user or agent, or automatically based on the kind of memory being stored.

---

## Problem statement

After Feature 2, MindState has a working RAG layer but an unused graph layer. Apache AGE is installed and the `mindstate` graph exists, but the `remember()` pipeline does not write to it. The graph remains an independent substrate accessible only via the Cypher shell.

This means:

* Retrieval is purely semantic — no structural traversal, no entity-aware expansion
* The graph accumulates nothing from the memory service path
* `build_context()` cannot do hybrid recall because there are no graph edges derived from memory items
* Decisions, architectural notes, and resolved blockers — the highest-value memory kinds — are not anchored in a navigable structure

The graph needs to be fed, but the feed must be controlled.

---

## Design principle: two-tier write model

Every memory item passes through two potential tiers:

**Tier 1 — Always, synchronous, cheap**

`remember()` stores the canonical item, chunks it, and embeds it. Always runs. Always completes before the call returns. No LLM involved. RAG is immediately available.

**Tier 2 — Optional, asynchronous, costly**

Contextualization extracts entities from the content, resolves them against the AGE graph, infers typed relations, writes MERGE statements to AGE, and records links in `memory_links`. Runs in the background. Failure never rolls back the Tier 1 write. The item remains fully searchable via RAG regardless of whether Tier 2 runs.

The two tiers are independent. Tier 2 enriches Tier 1 items after the fact. They share the same `memory_id` as the anchor.

---

## Functional scope

### 1. `contextualize [n]` command

An explicit operation that takes the `n` most recent `memory_items` that have not yet been graph-contextualized, and runs Tier 2 processing on them in the background.

**Default**: `n = 1` — contextualize the item most recently stored.

**Signature** (conceptual):
```
contextualize(n: int = 1) -> ContextualizeJob
contextualize(ids: List[UUID]) -> ContextualizeJob
```

Two targeting modes:
- **`n` mode**: selects the `n` most recent non-contextualized items ordered by `created_at DESC`. This is the primary human and simple-agent interface.
- **`ids` mode**: targets specific memory items by UUID. This is the precise-agent interface — an agent that tracks what it has written can specify exactly which items to contextualize.

Returns a job reference immediately. The actual graph writes happen asynchronously.

### 2. `remember(..., contextualize=True)` — the contextualized variant

A convenience composition of `remember()` followed immediately by `contextualize(ids=[new_memory_id])`. No new logic; purely a caller-side shorthand that avoids a second explicit call.

The underlying behavior is identical to calling them separately. The contextualization job is enqueued after the Tier 1 write commits. The `remember()` call still returns immediately with the `memory_id`; the caller does not wait for contextualization to complete.

### 3. Kind-aware automatic contextualization

Certain memory kinds are inherently high-value and structurally anchored by nature. For these, contextualization should be the default behavior without requiring the caller to pass `contextualize=True` or to issue a separate command.

The default policy:

```python
AUTO_CONTEXTUALIZE_KINDS = {
    "decision",
    "architecture_note",
    "resolved_blocker",
    "task",
    "observation",
    "claim",
}
```

When `remember()` is called with a kind in `AUTO_CONTEXTUALIZE_KINDS`, the system automatically enqueues a contextualization job for that item, as if the caller had passed `contextualize=True`.

For all other kinds — `note`, `message`, `summary`, `event`, `agent_action`, and any custom kinds — contextualization does not run unless explicitly requested.

**Rationale for the split**: High-value kinds by definition carry structured intent. A `decision` has a subject, a maker, and a scope. An `architecture_note` references technologies, components, and concepts. A `resolved_blocker` references a task and an outcome. These are precisely the items that make the graph useful. By contrast, a `note` or `message` may be transient, low-signal, or a near-duplicate — spending LLM tokens on them by default would dilute the graph.

**The kind policy must be configurable.** The default set above is conservative. Users and agents should be able to extend it via configuration (e.g., `MS_AUTO_CONTEXTUALIZE_KINDS` environment variable or a config file entry) without code changes.

### 4. Contextualization status on memory items

The schema requires one new field:

```sql
ALTER TABLE memory_items
    ADD COLUMN contextualized_at TIMESTAMPTZ NULL,
    ADD COLUMN contextualization_skipped BOOLEAN NOT NULL DEFAULT FALSE;
```

- `contextualized_at NULL` — not yet contextualized (eligible for `contextualize [n]`)
- `contextualized_at <timestamp>` — contextualization complete
- `contextualization_skipped = TRUE` — explicitly skipped (e.g., content too short, kind excluded, or manually marked)

This status is queryable. `GET /v1/memory/{id}` should include it. The REPL `\inspect <id>` command should show it. It also drives the input queue for `contextualize [n]`: the selection is always `WHERE contextualized_at IS NULL AND contextualization_skipped = FALSE ORDER BY created_at DESC LIMIT n`.

---

## The contextualization pipeline: `GraphContextualizer`

The `GraphContextualizer` is the internal service that executes Tier 2 processing for a single memory item. It has three stages:

### Stage 1 — Entity recognition

Extract named entities from the memory item's content. This is LLM-assisted with a structured output schema.

Each recognized entity has:
- `surface_form` — the exact text as it appears
- `entity_type` — one of the controlled types: `person`, `organization`, `project`, `topic`, `technology`, `concept`, `artifact`, `place`, `decision_ref`, `task_ref`
- `confidence` — float 0–1

The LLM prompt should be tight and typed. It must not be asked to infer everything — only the entity types in the controlled set. Unrecognized things should be omitted rather than forced into a category.

### Stage 2 — Entity resolution

For each recognized entity, determine whether a matching node already exists in the AGE graph.

Resolution strategy (in order of preference):
1. **Exact normalized name match** — normalize both the surface form and existing node names (lowercase, strip punctuation, collapse whitespace) and look for an exact match within the correct entity type.
2. **Embedding similarity match** — embed the surface form and compare against embeddings of existing entity canonical names. A high-confidence threshold (e.g., >0.92) is required to auto-merge.
3. **LLM disambiguation** — if normalization and embedding are inconclusive and the entity is high-confidence, ask the LLM whether `surface_form` refers to an existing entity given a short list of candidates.

**Conservative merge policy**: if resolution is ambiguous, create a new node rather than merging. False merges corrupt the graph in ways that are hard to detect and expensive to repair. A duplicate node can be merged later; a wrongly merged node carries cascading errors.

### Stage 3 — Relation inference

Given the resolved entities and the original content, infer the typed relations between the memory item and its entities, and between entities with each other where clearly stated.

The controlled relation set for this feature:

| Relation | Meaning |
|----------|---------|
| `about` | The memory item is primarily about this entity |
| `mentions` | The memory item references this entity in passing |
| `decided_by` | A decision was made by this person/agent |
| `for_project` | This item belongs to or concerns this project |
| `depends_on` | One thing depends on another |
| `follows_from` | This item is a logical consequence of another |
| `contradicts` | This item conflicts with another entity or item |
| `references_memory` | Explicit `memory:UUID` reference (already partially implemented) |
| `assigned_to` | A task is assigned to a person/agent |
| `resolved_by` | A blocker was resolved by a decision or action |

Relations outside this set should not be inferred in the first implementation. A narrow, high-confidence set is more valuable than a broad, noisy one.

### Stage 4 — AGE write

For each resolved entity and inferred relation, emit AGE `MERGE` statements into the `mindstate` graph. `MERGE` is safe: it is idempotent on existing nodes and creates only what is new.

```cypher
MERGE (e:Person {id: 'person.ada', canonical_name: 'Ada Lovelace'})

MERGE (m:MemoryNode {id: '<memory_id>'})
SET m.kind = 'decision', m.created_at = '<timestamp>'

MERGE (m)-[:DECIDED_BY]->(e)
```

After AGE writes complete, write corresponding rows to `memory_links` so that the relational layer also reflects the graph structure. This keeps the two layers consistent.

Finally, set `memory_items.contextualized_at = NOW()`.

---

## Failure handling

Contextualization failure must never affect the Tier 1 write. The item is already stored and searchable. If contextualization fails:

- Log the error with the `memory_id` and stage of failure
- Leave `contextualized_at NULL` — the item remains eligible for a retry via `contextualize [n]`
- Do not mark the item as skipped unless the failure is deterministic (e.g., content too short to extract entities)

This means `contextualize [n]` is also a **retry mechanism** — running it again will pick up items that failed previously.

---

## Interface surfaces

### REPL command

```
\contextualize [n]       Contextualize the n most recent non-contextualized items (default 1)
\contextualize --id UUID Contextualize a specific item by memory_id
```

### HTTP API

```
POST /v1/memory/contextualize
{
  "n": 1
}

POST /v1/memory/contextualize
{
  "ids": ["<uuid>", "<uuid>"]
}
```

Response:
```json
{
  "job_id": "<uuid>",
  "queued_count": 1,
  "status": "queued"
}
```

`GET /v1/memory/contextualize/{job_id}` returns job status and results when complete.

### MCP tool

```
contextualize(n: int = 1)
contextualize(ids: List[str])
```

Agents can call `contextualize` immediately after a `remember` call for a high-value item, or at the end of a work session to anchor the session's key outputs.

### `remember` with `contextualize` flag

All three interfaces — REPL, HTTP, MCP — should accept a `contextualize: bool` field on the `remember` call. When `True`, or when the item's kind is in `AUTO_CONTEXTUALIZE_KINDS`, the system enqueues a contextualization job immediately after the Tier 1 write.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MS_AUTO_CONTEXTUALIZE_KINDS` | `decision,architecture_note,resolved_blocker,task,observation,claim` | Comma-separated list of kinds that trigger automatic contextualization |
| `MS_CONTEXTUALIZE_CONFIDENCE_THRESHOLD` | `0.85` | Minimum entity confidence to include in graph write |
| `MS_CONTEXTUALIZE_MERGE_THRESHOLD` | `0.92` | Minimum embedding similarity to auto-resolve an entity to an existing node |
| `MS_CONTEXTUALIZE_MAX_ENTITIES_PER_ITEM` | `12` | Cap on entities extracted per item to bound LLM token use |
| `MS_CONTEXTUALIZE_ENABLED` | `true` | Master switch — can disable graph writes entirely without removing the feature |

---

## Data model changes

### `memory_items`

```sql
ALTER TABLE memory_items
    ADD COLUMN contextualized_at TIMESTAMPTZ NULL,
    ADD COLUMN contextualization_skipped BOOLEAN NOT NULL DEFAULT FALSE;
```

### `memory_contextualization_jobs` (new table)

```sql
CREATE TABLE memory_contextualization_jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_ids UUID[] NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',   -- queued | running | done | failed
    queued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    error TEXT NULL,
    result JSONB NULL
);
```

This table drives the job queue, supports status polling, and provides an audit trail of all contextualization activity.

---

## Non-goals

This feature does not include:

* Automatic contextualization of all existing historical items (can be done manually via `contextualize [n]` in batches)
* Full ontology management or entity taxonomy expansion beyond the defined set
* Real-time graph query integration into `recall()` — that is hybrid retrieval, a separate concern that becomes possible after this feature lands
* Conflict resolution UI for ambiguous entity merges — the conservative policy (create new, merge later) handles this for now
* Digest or summary generation from graph state

---

## Acceptance criteria

1. `contextualize [n=1]` is available in the REPL, HTTP API, and MCP tool surface.
2. Calling `contextualize` with `n` selects the n most recent non-contextualized items and enqueues a background job.
3. Calling `contextualize` with `ids` targets specific items by UUID.
4. `remember(..., contextualize=True)` enqueues contextualization immediately after the Tier 1 write commits.
5. Items whose `kind` is in `AUTO_CONTEXTUALIZE_KINDS` are automatically contextualized without explicit opt-in.
6. `AUTO_CONTEXTUALIZE_KINDS` is configurable via environment variable without code changes.
7. `memory_items.contextualized_at` is set when contextualization completes; items with `NULL` are eligible for `contextualize [n]`.
8. Contextualization failure leaves the Tier 1 item intact and the item eligible for retry.
9. The AGE graph receives `MERGE` statements for recognized entities and inferred relations.
10. `memory_links` is updated to reflect the graph edges written, keeping relational and graph layers consistent.
11. The `GraphContextualizer` uses the conservative merge policy: ambiguous resolution creates a new node rather than merging.
12. No regression in the `remember()` / `recall()` / `build_context()` behavior from Feature 2.

---

## Relationship to other features

**Depends on**: Feature 2 (canonical `MemoryItem`, `memory_items` schema, `MindStateService`)

**Enables**:
- Feature 4 (MCP): the `contextualize` tool becomes a first-class MCP operation; `log_work_session` naturally calls it for `decision` and `resolved_blocker` kinds
- Hybrid retrieval (future): once AGE contains edges derived from memory items, `recall()` can be augmented with a graph expansion pass — start from semantic candidates, walk entity edges, pull related items. This is the retrieval behavior described in `docs/MindState-first-design-thoughts.md` section 15.3 and cannot be built until this feature exists.
