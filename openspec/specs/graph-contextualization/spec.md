## Purpose
Define graph contextualization behavior for enriching memory items with conservative entity and relation projections.

## Requirements

### Requirement: GraphContextualizer executes a four-stage pipeline per memory item
The `GraphContextualizer` SHALL process a single memory item through four sequential stages: entity recognition, entity resolution, relation inference, and AGE write. Failure in any stage SHALL leave `memory_items.contextualized_at` as NULL (item remains retry-eligible) unless the failure is deterministic, in which case `contextualization_skipped` is set to TRUE.

#### Scenario: Successful pipeline run
- **WHEN** `GraphContextualizer.run(memory_id)` is called with a valid memory item
- **THEN** entities are extracted, resolved against AGE, relations inferred, AGE MERGE statements executed, `memory_links` rows written, and `memory_items.contextualized_at` set to the current timestamp

#### Scenario: Pipeline failure leaves item retry-eligible
- **WHEN** an LLM call or AGE write raises an exception during contextualization
- **THEN** `contextualized_at` remains NULL, `contextualization_skipped` remains FALSE, and the error is logged with the `memory_id` and failing stage name

#### Scenario: Deterministic failure skips item
- **WHEN** the memory item content is too short to extract entities (e.g., fewer than 10 words)
- **THEN** `contextualization_skipped` is set to TRUE and the item is not selected for future `contextualize(n)` calls

### Requirement: Stage 1 — Entity recognition uses LLM structured output with controlled types
The entity recognition stage SHALL call the LLM with the memory item content and return a list of entities. Each entity SHALL have `surface_form` (exact text), `entity_type` (one of: `person`, `organization`, `project`, `topic`, `technology`, `concept`, `artifact`, `place`, `decision_ref`, `task_ref`), and `confidence` (float 0–1). Entities with types outside the controlled set SHALL NOT be returned.

#### Scenario: Entities extracted from decision content
- **WHEN** a memory item of kind `decision` contains "Ada approved using PostgreSQL for the backend"
- **THEN** the recognizer returns at least `{surface_form: "Ada", entity_type: "person", confidence: >0.8}` and `{surface_form: "PostgreSQL", entity_type: "technology", confidence: >0.8}`

#### Scenario: Entity count is capped
- **WHEN** the LLM would return more than `MS_CONTEXTUALIZE_MAX_ENTITIES_PER_ITEM` entities
- **THEN** only the top N by confidence are retained; the rest are discarded

#### Scenario: Low-confidence entities are filtered
- **WHEN** the LLM returns an entity with `confidence` below `MS_CONTEXTUALIZE_CONFIDENCE_THRESHOLD`
- **THEN** that entity is excluded from subsequent resolution and relation inference stages

### Requirement: Stage 2 — Entity resolution uses a three-step conservative merge policy
The resolution stage SHALL attempt to match each recognized entity to an existing AGE node using three steps in order: (1) normalized exact name match, (2) embedding cosine similarity above `MS_CONTEXTUALIZE_MERGE_THRESHOLD`, (3) LLM disambiguation against a candidate list. If all three steps are inconclusive, a new node SHALL be created. A false merge SHALL NOT be preferred over a duplicate node.

#### Scenario: Exact match resolves entity
- **WHEN** the surface form normalizes to a name that matches an existing AGE node of the same entity type
- **THEN** the existing node ID is used; no new node is created

#### Scenario: Embedding match resolves entity
- **WHEN** no exact match exists but an existing node's canonical name embedding has cosine similarity ≥ `MS_CONTEXTUALIZE_MERGE_THRESHOLD` with the surface form embedding
- **THEN** the existing node is used; no new node is created

#### Scenario: Ambiguous entity creates new node
- **WHEN** normalized match and embedding match are both inconclusive (no match above threshold)
- **THEN** a new AGE node is created with a namespaced ID (`{entity_type}.{normalized_name}`) rather than merging into an existing node

### Requirement: Stage 3 — Relation inference uses a controlled relation type set
The relation inference stage SHALL infer typed relations between the memory item and its resolved entities, and between entities where clearly stated in the content. Only the following relation types SHALL be used: `about`, `mentions`, `decided_by`, `for_project`, `depends_on`, `follows_from`, `contradicts`, `references_memory`, `assigned_to`, `resolved_by`. Relations outside this set SHALL NOT be written to the graph.

#### Scenario: Decision attributed to person
- **WHEN** a memory item of kind `decision` states an entity of type `person` made the decision
- **THEN** a `DECIDED_BY` relation is inferred between the memory node and the person node

#### Scenario: Item is primarily about a topic
- **WHEN** an entity is the central subject of the memory item content
- **THEN** an `ABOUT` relation is inferred; secondary references use `MENTIONS`

### Requirement: Stage 4 — AGE writes use MERGE statements and are atomic per item
All entity nodes and relation edges for a single memory item SHALL be written to the AGE `mindstate` graph using `MERGE` statements within one transaction. If the AGE transaction fails, no partial writes SHALL be committed. `memory_links` rows corresponding to the inferred relations SHALL be written in the same transaction. On success, `memory_items.contextualized_at` is set to `NOW()`.

#### Scenario: Idempotent node creation
- **WHEN** `GraphContextualizer.run(memory_id)` is called for an item whose entities already exist in AGE
- **THEN** MERGE does not duplicate existing nodes; only new relations or missing nodes are created

#### Scenario: Relation written to memory_links
- **WHEN** a `DECIDED_BY` relation is written to AGE between a memory node and a person node
- **THEN** a corresponding row is inserted into `memory_links` with `relation_type = 'decided_by'` and the appropriate `linked_memory_id` or entity reference

### Requirement: `remember()` accepts a `contextualize` flag
`MindStateService.remember()` SHALL accept an optional `contextualize: bool` parameter (default `False`). When `True`, or when the item's `kind` is in `AUTO_CONTEXTUALIZE_KINDS`, a contextualization job SHALL be enqueued immediately after the Tier 1 write commits. The `remember()` call SHALL return before contextualization completes.

#### Scenario: Explicit opt-in contextualizes after write
- **WHEN** `remember(payload, contextualize=True)` is called
- **THEN** the Tier 1 write completes and commits, the function returns the `memory_id`, and a background contextualization job is enqueued for that item

#### Scenario: Auto-kind triggers contextualization
- **WHEN** `remember(payload)` is called with `payload.kind = "decision"` and `"decision"` is in `AUTO_CONTEXTUALIZE_KINDS`
- **THEN** a contextualization job is enqueued automatically without the caller passing `contextualize=True`

#### Scenario: Contextualization failure does not affect Tier 1
- **WHEN** the background contextualization job raises an exception
- **THEN** the memory item remains stored and searchable via `recall()`; `contextualized_at` stays NULL

### Requirement: `AUTO_CONTEXTUALIZE_KINDS` is configurable without code changes
The set of memory kinds that trigger automatic contextualization SHALL be read from `MS_AUTO_CONTEXTUALIZE_KINDS` at startup. The default value SHALL be `decision,architecture_note,resolved_blocker,task,observation,claim`. Changes to the environment variable SHALL take effect on next process start without any code modification.

#### Scenario: Default auto-kinds
- **WHEN** `MS_AUTO_CONTEXTUALIZE_KINDS` is not set
- **THEN** `get_settings()` returns a contextualization settings object with the six default kinds

#### Scenario: Custom auto-kinds via environment variable
- **WHEN** `MS_AUTO_CONTEXTUALIZE_KINDS=note,summary` is set
- **THEN** only `note` and `summary` kinds trigger automatic contextualization; the defaults are replaced

### Requirement: `MS_CONTEXTUALIZE_ENABLED=false` disables all graph writes
When `MS_CONTEXTUALIZE_ENABLED` is set to `false`, no contextualization jobs SHALL be enqueued and no AGE writes SHALL occur. The Tier 1 write path is unaffected. Explicit `contextualize(n)` calls return a job response indicating zero items queued.

#### Scenario: Master switch disables contextualization
- **WHEN** `MS_CONTEXTUALIZE_ENABLED=false` is set and `remember(..., contextualize=True)` is called
- **THEN** the item is stored normally but no contextualization job is created