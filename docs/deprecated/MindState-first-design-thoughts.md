Below is a concrete technical design for the memory system we discussed: a MindState-backed Open Brain with one canonical corpus, derived vector and graph projections, and agent-facing interfaces.

I will assume four design constraints.

First, the system must be practical to build now, not merely architecturally elegant. Second, Postgres is the default substrate, but the design must avoid binding the core model to Postgres internals. Third, memory must be inspectable and rebuildable. Fourth, the system must serve agents, not just human search.

## 1. System objective

The system is a persistent AI-accessible memory substrate that captures raw knowledge, supports semantic retrieval, supports structural traversal, and exposes those capabilities through a stable API and MCP tools.

Its purpose is not only to “store notes.” It should support:

* long-lived context across sessions and tools
* agent retrieval for task execution
* decision history and timelines
* topic-level synthesis
* provenance and auditability
* future extension to richer graph or vector backends

The system should treat memory as a first-class information system, not as a chat plugin.

## 2. Core design principle

The most important technical invariant is this:

**One canonical memory object, multiple derived projections.**

That means every captured unit enters once as a canonical `MemoryItem`. From that item, the system derives:

* raw persisted representation
* chunked representations for retrieval
* vector embeddings
* graph entities and relations
* synthetic summaries
* indexes and caches

No secondary layer is authoritative. The source of truth remains the canonical raw item and its provenance.

This is what prevents drift.

## 3. Logical architecture

The system has six layers.

### 3.1 Capture layer

Responsible for ingesting content from agents, humans, files, transcripts, meetings, messages, and system events.

### 3.2 Canonical memory layer

Stores raw memory items, source metadata, versioning, provenance, and identity.

### 3.3 Projection layer

Produces chunk projections, embedding projections, graph projections, and summary projections.

### 3.4 Retrieval layer

Implements semantic recall, graph traversal, timeline reconstruction, hybrid retrieval, and context assembly.

### 3.5 Agent interface layer

Exposes memory behaviors through application APIs and MCP tools.

### 3.6 Operational layer

Handles jobs, rebuild pipelines, observability, access control, deduplication, and retention.

## 4. Main architectural components

A minimal production-capable system should have these components.

### 4.1 Memory API service

The main application service. It receives capture and query requests and orchestrates other components.

### 4.2 Projection workers

Asynchronous workers that generate embeddings, entities, relations, summaries, and derived indexes.

### 4.3 Postgres MindState

Default storage substrate:

* relational canonical store
* pgvector index
* relational graph projection tables
* metadata and provenance tables

### 4.4 Embedding provider adapter

Abstraction over embedding generation. Initially one provider, later swappable.

### 4.5 Extraction and synthesis pipeline

LLM-driven or hybrid deterministic pipeline for:

* chunking
* entity extraction
* relation extraction
* topic tagging
* summarization

### 4.6 MCP adapter

Exposes memory capabilities to agent frameworks and external tools.

### 4.7 Scheduler / queue

Runs background jobs for projection, reindexing, decay, summarization, and periodic synthesis.

## 5. Canonical domain model

The system should have a small but expressive domain model.

### 5.1 MemoryItem

This is the primary object. Every piece of captured knowledge is a `MemoryItem`.

Suggested fields:

* `id` UUID
* `tenant_id`
* `workspace_id`
* `source_id`
* `external_ref` nullable
* `kind` enum
* `title` nullable
* `content` text or JSONB
* `content_format` enum
* `language`
* `author_type` enum (`human`, `agent`, `system`, `imported`)
* `author_id`
* `captured_at`
* `created_at`
* `updated_at`
* `effective_at` nullable, for event timing
* `status` enum (`active`, `superseded`, `deleted`, `archived`)
* `importance_score` nullable
* `confidence_score` nullable
* `canonical_hash`
* `version`
* `parent_item_id` nullable
* `metadata` JSONB
* `provenance_id`

Kinds should remain controlled. Start with:

* note
* message
* meeting_excerpt
* decision
* task
* document
* document_chunk_source
* summary
* observation
* event
* agent_action
* claim

Do not over-expand this taxonomy early.

### 5.2 Source

Represents the origin of the memory item.

Fields:

* `id`
* `tenant_id`
* `kind` (`chat`, `email`, `meeting`, `file`, `api`, `manual`, `agent_run`, `import`)
* `name`
* `uri` nullable
* `system_name`
* `external_ref`
* `metadata`

### 5.3 ProvenanceRecord

Tracks how an item came into existence.

Fields:

* `id`
* `generation_mode` (`captured`, `imported`, `derived`, `summarized`, `extracted`)
* `source_item_ids` array or link table
* `model_name` nullable
* `model_version` nullable
* `prompt_ref` nullable
* `pipeline_version`
* `operator_id` nullable
* `created_at`
* `metadata`

This table matters. Without provenance, the system will eventually become untrustworthy.

### 5.4 ChunkProjection

A retrieval-oriented projection derived from a memory item.

Fields:

* `id`
* `memory_item_id`
* `chunk_index`
* `content`
* `token_count`
* `char_start`
* `char_end`
* `chunk_hash`
* `projection_version`
* `metadata`

### 5.5 EmbeddingProjection

Fields:

* `id`
* `chunk_id`
* `embedding_model`
* `embedding_dim`
* `embedding` vector
* `projection_version`
* `created_at`

### 5.6 Entity

Represents stable referenced things.

Fields:

* `id`
* `tenant_id`
* `entity_type`
* `canonical_name`
* `normalized_name`
* `description` nullable
* `confidence_score`
* `metadata`
* `created_at`
* `updated_at`

Entity types should start simple:

* person
* organization
* project
* topic
* document
* technology
* place
* concept
* artifact

### 5.7 EntityMention

Links memory content to entities.

Fields:

* `id`
* `memory_item_id`
* `chunk_id` nullable
* `entity_id`
* `surface_form`
* `char_start`
* `char_end`
* `confidence_score`
* `extraction_version`

### 5.8 RelationEdge

Represents typed graph relations.

Fields:

* `id`
* `tenant_id`
* `subject_type`
* `subject_id`
* `predicate`
* `object_type`
* `object_id`
* `source_memory_item_id`
* `confidence_score`
* `valid_from` nullable
* `valid_to` nullable
* `extraction_version`
* `metadata`

Predicates should be tightly controlled at first:

* mentions
* about
* belongs_to
* related_to
* depends_on
* follows_from
* decides
* assigned_to
* contradicts
* summarizes
* derived_from
* references

### 5.9 TopicDigest

A synthetic summary at topic or scope level.

Fields:

* `id`
* `tenant_id`
* `scope_type`
* `scope_id`
* `time_window_start`
* `time_window_end`
* `digest_text`
* `digest_kind` (`rolling`, `weekly`, `project`, `person`, `topic`)
* `source_item_count`
* `provenance_id`
* `created_at`

### 5.10 MemoryLink

For explicit high-value links between memory items.

Fields:

* `id`
* `from_item_id`
* `to_item_id`
* `link_type`
* `weight`
* `source` (`manual`, `extracted`, `semantic`, `graph_inferred`)
* `metadata`

This table helps bridge raw memory and graph logic without forcing everything into entities.

## 6. Postgres implementation model

The default implementation uses Postgres plus pgvector.

### 6.1 Why Postgres works here

Postgres gives:

* ACID transactions for capture and projection bookkeeping
* flexible JSONB for metadata
* strong relational integrity for provenance and links
* pgvector for approximate semantic retrieval
* materialized views and SQL for analytics
* operational simplicity

This does not mean Postgres is the optimal graph engine in all cases. It means it is the best default substrate for a coherent first system.

### 6.2 Suggested schema separation

Use schema namespaces to keep the design clean.

* `core` for canonical objects
* `proj` for projections
* `graph` for entities and relations
* `retrieval` for query artifacts and caches
* `ops` for jobs and observability
* `auth` for identities and permissions

This helps maintain conceptual clarity.

## 7. API design philosophy

The system should expose **capabilities**, not storage mechanics.

Bad API shape:

* `insert_embedding`
* `get_neighbors`
* `upsert_entity`

Good API shape:

* `remember`
* `recall`
* `build_context`
* `explain_topic`
* `decision_history`
* `find_open_loops`

The API should remain stable even if the graph backend, embedding provider, or chunking logic changes.

## 8. Core application interfaces

Below is the conceptual interface set. Language-agnostic first, then example API shapes.

### 8.1 MemoryCaptureService

Responsibilities:

* validate incoming memory
* create canonical item
* deduplicate if appropriate
* enqueue projection jobs

Methods:

* `remember(input: RememberRequest) -> RememberResponse`
* `remember_batch(inputs: list[RememberRequest]) -> BatchResponse`

### 8.2 MemoryRecallService

Responsibilities:

* semantic recall
* hybrid recall
* filter by scope and provenance
* return ranked results

Methods:

* `recall(query: RecallQuery) -> RecallResult`
* `recall_by_item(item_id, options) -> RecallResult`

### 8.3 ContextAssemblyService

Responsibilities:

* assemble task-specific context
* mix raw items, summaries, entities, timelines
* size to token budget

Methods:

* `build_context(task: ContextRequest) -> ContextBundle`

### 8.4 TopicInsightService

Responsibilities:

* topic summaries
* topic evolution
* contradiction surfacing
* open questions

Methods:

* `explain_topic(topic_ref, options) -> TopicInsight`
* `topic_timeline(topic_ref, options) -> TimelineResult`

### 8.5 DecisionHistoryService

Methods:

* `decision_history(subject_ref, options) -> DecisionHistory`
* `decision_context(decision_id) -> ContextBundle`

### 8.6 GraphNavigationService

Methods:

* `related_entities(ref, options) -> RelatedEntitySet`
* `traverse(ref, path_spec, depth) -> GraphTraversalResult`

### 8.7 MemoryMaintenanceService

Methods:

* `reproject(item_ids, projection_types)`
* `reembed(item_ids, embedding_model)`
* `reextract(item_ids, extractor_version)`
* `merge_entities(entity_ids)`
* `rebuild_topic_digest(scope_ref)`

## 9. External HTTP API proposal

A pragmatic first API might look like this.

### 9.1 Capture

`POST /v1/memory/remember`

Request:

```json
{
  "workspace_id": "ws_123",
  "kind": "note",
  "title": "Thought on agent memory",
  "content": "Memory should be one canonical object with derived vector and graph projections.",
  "content_format": "text/plain",
  "source": {
    "kind": "manual",
    "name": "user_capture"
  },
  "author": {
    "type": "human",
    "id": "user_1"
  },
  "metadata": {
    "tags": ["memory", "architecture"],
    "project": "OpenBrain"
  },
  "capture_options": {
    "run_embedding": true,
    "run_extraction": true,
    "priority": "normal"
  }
}
```

Response:

```json
{
  "memory_item_id": "mem_001",
  "status": "accepted",
  "projection_jobs": [
    "embed",
    "extract_entities",
    "extract_relations"
  ]
}
```

### 9.2 Recall

`POST /v1/memory/recall`

Request:

```json
{
  "workspace_id": "ws_123",
  "query": "What architectural principles define MindState memory?",
  "filters": {
    "kinds": ["note", "summary", "decision"],
    "time_range": {
      "from": "2026-01-01T00:00:00Z"
    },
    "projects": ["OpenBrain"]
  },
  "strategy": {
    "mode": "hybrid",
    "top_k_semantic": 12,
    "top_k_graph": 8,
    "include_summaries": true,
    "rerank": true
  }
}
```

Response:

```json
{
  "results": [
    {
      "memory_item_id": "mem_001",
      "score": 0.91,
      "reason": "semantic_match",
      "snippet": "Memory should be one canonical object...",
      "provenance": {
        "source_kind": "manual"
      }
    }
  ],
  "related_entities": [
    {
      "entity_id": "ent_12",
      "name": "MindState",
      "type": "concept"
    }
  ]
}
```

### 9.3 Context assembly

`POST /v1/context/build`

Request:

```json
{
  "workspace_id": "ws_123",
  "task": "Prepare technical design for Postgres-based Open Brain memory system",
  "constraints": {
    "max_tokens": 6000,
    "include_decision_history": true,
    "include_recent_only": false
  },
  "focus": {
    "projects": ["OpenBrain"],
    "topics": ["MindState", "memory architecture"]
  }
}
```

Response:

```json
{
  "bundle_id": "ctx_123",
  "summary": "This context bundle includes core architectural notes...",
  "items": [
    {
      "type": "summary",
      "ref_id": "dig_01",
      "content": "MindState treats raw, vector, and graph..."
    },
    {
      "type": "memory_item",
      "ref_id": "mem_001"
    }
  ],
  "token_estimate": 4820
}
```

### 9.4 Topic explanation

`GET /v1/topics/{topic_id}/explain`

### 9.5 Decision history

`GET /v1/decisions/history?subject=OpenBrain`

### 9.6 Maintenance

`POST /v1/admin/reproject`
`POST /v1/admin/reembed`
`POST /v1/admin/entity/merge`

## 10. MCP tool proposal

MCP should expose a smaller, cognitively coherent surface.

Recommended tools:

* `remember`
* `recall`
* `build_context`
* `topic_digest`
* `decision_history`
* `find_related`
* `timeline`
* `open_loops`

Example MCP contracts:

### 10.1 remember

Input:

```json
{
  "text": "A graph layer should not be optional in architecture, only in retrieval path.",
  "kind": "observation",
  "workspace": "OpenBrain"
}
```

### 10.2 recall

Input:

```json
{
  "query": "Why is one canonical memory object important?",
  "workspace": "OpenBrain",
  "limit": 10
}
```

### 10.3 build_context

Input:

```json
{
  "task": "Draft architecture overview for agent memory platform",
  "workspace": "OpenBrain",
  "max_tokens": 4000
}
```

## 11. Ingestion flow

A robust ingestion pipeline is central.

### 11.1 Step 1: accept and normalize

Input can arrive as raw text, structured JSON, file import, transcript segment, or system event.

Normalize into an internal `RememberRequest`.

### 11.2 Step 2: deduplication and canonicalization

Compute:

* normalized text
* content hash
* optional fuzzy duplicate score

Duplicates should not always be blocked. The system may record repeated observations but should detect likely identical imports.

### 11.3 Step 3: persist canonical memory item

Write:

* `MemoryItem`
* `Source`
* `ProvenanceRecord`

This is the only mandatory synchronous write.

### 11.4 Step 4: enqueue projection jobs

Jobs may include:

* chunking
* embedding
* entity extraction
* relation extraction
* digest update
* topic classifier
* link inference

### 11.5 Step 5: project asynchronously

Workers generate projections and store them with explicit projection versions.

### 11.6 Step 6: post-projection linking

Once entities and relations are available, update:

* item-entity links
* related item links
* digests
* graph summaries

## 12. Chunking design

Chunking should not be naïve fixed-size splitting only.

Use a chunking strategy abstraction.

Initial strategies:

* paragraph-preserving chunking
* heading-aware chunking
* transcript utterance chunking
* code/document section chunking

Chunk size targets:

* 300 to 800 tokens for general prose
* smaller chunks for dense factual material
* preserve overlap where needed

Each chunk must keep offsets back to the raw source. That is essential for explainability and reconstruction.

## 13. Embedding strategy

Embeddings should be attached to chunks, not only full items.

Design considerations:

* store embedding model version
* support parallel re-embedding
* support multiple embedding spaces if needed later
* allow tenant- or workspace-specific embedding config

Recommended first implementation:

* one active embedding per chunk
* old embeddings retained optionally for migration window
* HNSW or IVFFlat indexing through pgvector depending on scale

## 14. Graph projection strategy

This is where many systems become bloated. Start lighter than your ambitions.

The graph layer should not initially aim to be a universal knowledge graph. It should support useful memory behavior.

### 14.1 What to extract first

Extract:

* entities
* typed mentions
* high-confidence relations
* explicit tasks and decisions
* temporal references
* contradiction candidates

### 14.2 What not to overbuild initially

Avoid:

* full ontology engineering
* deep inference engines
* unrestricted relation taxonomies
* brittle entity resolution rules

### 14.3 Entity resolution

You need lightweight resolution logic:

* normalized name matching
* workspace-scoped alias tables
* optional LLM-assisted merge suggestions
* manual override support

False merges are worse than missed merges. Be conservative.

## 15. Retrieval strategies

The retrieval layer should support multiple strategies.

### 15.1 Pure semantic

For broad recall by meaning.

### 15.2 Graph-aware recall

Start from an entity or item, then traverse related nodes and gather supporting items.

### 15.3 Hybrid recall

Recommended default. Steps:

1. semantic retrieval candidate set
2. graph expansion from top entities/items
3. summary retrieval for topic scopes
4. reranking using task relevance and recency

### 15.4 Timeline retrieval

For project, topic, or decision history:

* gather time-bound items
* include summaries and decisions
* group chronologically

### 15.5 Open loop retrieval

Useful for agents. Surface:

* unresolved tasks
* contradictions
* pending dependencies
* stale summaries
* low-confidence edges needing review

## 16. Context builder design

This is one of the most important components because agents do not need “all memory.” They need **task-shaped context**.

### 16.1 Inputs

* task description
* workspace/project/topic scope
* token budget
* recency preference
* need for timeline vs need for concepts
* user/agent role

### 16.2 Outputs

A `ContextBundle` containing:

* short synthetic overview
* supporting raw excerpts
* relevant entities
* current decisions
* open questions
* provenance references

### 16.3 Assembly logic

A strong default assembly pipeline:

1. identify focus topics/entities from task
2. fetch latest digests
3. retrieve semantic candidates
4. expand graph neighbors for core entities
5. include recent decisions and unresolved items
6. compress to token budget
7. attach provenance map

This is the point where memory becomes useful rather than merely searchable.

## 17. Summarization and digesting

You need summaries early. Without them, the system grows but does not become more usable.

### 17.1 Digest scopes

Start with:

* topic digest
* project digest
* person/entity digest
* weekly digest
* decision digest

### 17.2 Digest rebuild triggers

* threshold number of new items
* time-based schedule
* explicit admin request
* topic importance threshold crossed

### 17.3 Summary storage rule

Summaries are never the canonical source. They are stored as derived memory items with provenance pointing to their source set.

## 18. Versioning and rebuildability

This system must tolerate changing models and extraction logic.

### 18.1 Version every projection

Store versions for:

* chunker
* embedding model
* extractor
* summarizer
* relation taxonomy

### 18.2 Rebuild pipelines

Support:

* re-chunk
* re-embed
* re-extract entities
* re-extract relations
* rebuild digests

These should be incremental and scoped.

### 18.3 Backfill strategy

When a model changes, do not block reads. Mark projections with active version status and let the retriever prefer newest versions.

## 19. Operational job system

Use a job queue with explicit job types and retry policies.

Suggested job types:

* `chunk_memory_item`
* `embed_chunk_batch`
* `extract_entities`
* `extract_relations`
* `infer_links`
* `rebuild_digest`
* `merge_entities_review`
* `reproject_item`

Each job should include:

* tenant/workspace scope
* source item refs
* projection version
* idempotency key

## 20. Security and multi-tenancy

This is easy to neglect and expensive to retrofit.

### 20.1 Tenant boundaries

Every core table must be tenant-aware.

### 20.2 Workspace boundaries

Useful for separating projects, teams, or personal vs enterprise contexts.

### 20.3 Access control

At minimum:

* read scopes
* write scopes
* admin maintenance scopes
* derived summary visibility rules

### 20.4 Sensitive memory classes

Certain items may require sensitivity flags:

* private
* confidential
* restricted
* agent-readable false

Agents should not see everything by default.

## 21. Observability

The system needs observability at the memory quality level, not only CPU and DB metrics.

Track:

* ingestion rate
* projection lag
* embedding error rate
* entity extraction confidence distribution
* duplicate rate
* recall hit quality
* context bundle token composition
* stale digest ratio
* unresolved low-confidence merge suggestions

You will need these signals to prevent silent decay.

## 22. Recommended repository structure

A pragmatic code layout could be:

```text
memory-system/
  apps/
    api/
    worker/
    mcp/
  packages/
    domain/
    application/
    adapters/
      postgres/
      embeddings/
      extractors/
      mcp/
    contracts/
    observability/
  migrations/
  docs/
    architecture/
    schemas/
    api/
```

Inside the domain/application split:

* `domain`: entities, value objects, invariants
* `application`: use cases and service interfaces
* `adapters`: Postgres, vector, extraction, MCP implementations

## 23. Example application-layer interfaces

Pseudocode only, but close to real design.

```python
class MemoryRepository(Protocol):
    def create_item(self, item: MemoryItem) -> MemoryItem: ...
    def get_item(self, item_id: str) -> MemoryItem | None: ...
    def list_items(self, query: MemoryItemQuery) -> list[MemoryItem]: ...

class ProjectionRepository(Protocol):
    def store_chunks(self, chunks: list[ChunkProjection]) -> None: ...
    def store_embeddings(self, embeddings: list[EmbeddingProjection]) -> None: ...
    def store_entities(self, entities: list[Entity]) -> None: ...
    def store_relations(self, relations: list[RelationEdge]) -> None: ...

class RecallPort(Protocol):
    def semantic_search(self, query: SemanticQuery) -> list[RankedChunk]: ...
    def graph_expand(self, seeds: list[GraphSeed], depth: int) -> GraphTraversalResult: ...
    def hybrid_search(self, query: HybridRecallQuery) -> RecallResult: ...

class ContextBuilderPort(Protocol):
    def build_context(self, request: ContextRequest) -> ContextBundle: ...

class DigestPort(Protocol):
    def get_digest(self, scope: DigestScope) -> TopicDigest | None: ...
    def rebuild_digest(self, scope: DigestScope) -> TopicDigest: ...
```

These interfaces express memory behavior, not database mechanics.

## 24. Example Postgres adapter notes

The default adapter package might include:

* `PostgresMemoryRepository`
* `PostgresProjectionRepository`
* `PgVectorRecallAdapter`
* `PostgresGraphProjectionAdapter`
* `PostgresDigestRepository`

Where graph traversal is modest, SQL recursive queries and indexed joins may be enough. If later you replace graph traversal with Neo4j, the application contracts do not change.

## 25. Migration path to hybrid backends

You asked specifically about decoupling from Postgres. The correct design allows phased backend specialization.

### Phase 1

Everything in Postgres:

* raw store
* pgvector
* graph tables
* summaries

### Phase 2

If graph complexity grows:

* keep canonical raw store in Postgres
* replicate graph projection into Neo4j
* graph adapter reads from Neo4j
* provenance still anchored in Postgres IDs

### Phase 3

If vector scale grows:

* replicate embeddings to Qdrant/Weaviate
* vector adapter shifts there
* canonical chunk IDs remain stable

The core system still speaks in memory behaviors, not backend operations.

## 26. Minimal viable build plan

A good first version should not try to solve all of memory.

### MVP scope

Implement:

* canonical `MemoryItem`
* source and provenance
* chunking
* embeddings with pgvector
* simple entity extraction
* lightweight relation edges
* semantic recall
* context builder
* one digest type
* MCP adapter with 4 to 6 tools

Do not start with:

* full ontology
* advanced graph analytics
* autonomous memory pruning
* cross-tenant federated memory
* speculative inference layers

## 27. Recommended first relation set

For initial utility, these are enough:

* `about`
* `mentions`
* `belongs_to`
* `decides`
* `depends_on`
* `follows_from`
* `contradicts`
* `summarizes`
* `derived_from`

This set is expressive enough to support useful agent behavior without drowning in schema semantics.

## 28. Failure modes to design against

There are several predictable failure modes.

### 28.1 Memory sludge

Too many low-value captures, no synthesis, noisy retrieval.

Mitigation:

* importance scoring
* digests
* duplicate detection
* scoped recall

### 28.2 Projection drift

Embeddings, graph edges, and summaries no longer reflect raw data after pipeline changes.

Mitigation:

* versioned projections
* rebuild tooling
* provenance references

### 28.3 Entity collapse

Different concepts merged incorrectly.

Mitigation:

* conservative entity resolution
* merge review workflow
* alias management

### 28.4 Context overload

Context builder returns too much or too little.

Mitigation:

* task-shaped retrieval
* token budgeting
* summary-first assembly
* bundle diagnostics

### 28.5 Agent misuse

Agents treat retrieval results as truth.

Mitigation:

* provenance exposure
* confidence scores
* distinction between source items and derived summaries

## 29. Concrete answer to your architectural question

Yes, define interfaces first, but define them around memory semantics. Then implement a default `PostgresMindStateAdapter` as the initial backend.

The practical shape is:

* canonical store in Postgres
* vector retrieval with pgvector
* relational graph projection tables
* async projection workers
* behavior-oriented API and MCP surface
* optional later adapters for Neo4j or dedicated vector engines

That is the cleanest way to get something real built without sacrificing long-term extensibility.

## 30. Final recommended architecture statement

If I had to phrase the design in one precise sentence, it would be this:

**The system is a behavior-oriented, multi-representation memory platform in which Postgres serves as the canonical substrate for raw memory, semantic projection, and structural projection, while agent-facing interfaces expose cognitive operations rather than storage operations.**

