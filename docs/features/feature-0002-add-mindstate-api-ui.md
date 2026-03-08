# Feature 2 — Add the first MindState API and corresponding application UI

## Intent

Once the low-level base has been rebased as MindState, the application should grow from a substrate shell into the first usable MindState product. This feature adds:

* an application API
* a higher-level user interface layered on top of the base shell
* the first implementation of the core MindState behaviors defined in the design documents

This feature is where MindState stops being merely a renamed Cypher tool and starts becoming a memory platform.

## Problem statement

The current implementation is powerful but low-level. It assumes that the user works directly with Cypher or relies on an LLM to generate Cypher. That is useful for substrate access, but it is not yet aligned with the intended MindState model described in the design notes:

* one canonical memory object
* derived vector and graph projections
* behavior-oriented interfaces such as remember, recall, build context, topic insight, decision history, related entities, and work-session logging
* agent-facing cognitive operations rather than storage mechanics 

The new API and UI should expose those capabilities as first-class product features.

## Functional outcome

After this feature, MindState should support two parallel interaction layers:

### Low-level layer

Preserved from Feature 1:

* raw Cypher/graph/vector/relational access
* existing CLI/TUI shell
* direct substrate inspection

### Higher-level MindState layer

New in this feature:

* API endpoints for canonical memory capture and retrieval
* API endpoints for context assembly and project/topic insight
* a first user-facing UI for interacting with MindState as a memory system rather than only as a Cypher REPL
* persistence and retrieval based on the canonical `MemoryItem` and its projections

## Conceptual model to implement

This feature should implement the application around the design principles already established:

* one canonical memory object with multiple derived projections
* Postgres as the initial substrate
* raw/canonical layer, projection layer, retrieval layer, and agent interface layer
* capability-oriented interfaces instead of exposing database mechanics directly 

The existing TriStore/Postgres substrate should be adapted to support this rather than replaced. That is central to the brownfield goal.

## Functional scope

### 1. Canonical memory API

Implement the first MindState API surface for canonical memory operations.

At minimum, the API must expose:

* `remember`
* `recall`
* `build_context`

These are explicitly identified as foundational behavioral operations in the design.  

The first API version should also preferably include:

* topic explanation or digest retrieval
* decision history
* related-entity or related-memory traversal
* work-session logging

These need not all be equally deep in the first iteration, but the API shape should reserve room for them.

### 2. Canonical memory object support

The application must introduce the first implementation of the canonical memory object model. It does not need the full final richness on day one, but it must move beyond raw graph nodes or free-form storage.

At minimum, support a persisted object with fields equivalent to:

* identity
* kind
* content
* content format
* source
* author
* timestamps
* metadata
* provenance anchor

This follows directly from the documented MindState model. 

### 3. Projection pipeline integration

This feature must implement the first real projection workflow on top of the canonical item.

At minimum:

* raw persistence of the memory item
* chunk projection
* embedding projection
* a minimal graph projection or relation-link projection

The graph layer may be modest initially. The design explicitly recommends conservative graph extraction rather than overbuilding. 

### 4. Retrieval behavior

Implement a usable first retrieval model.

At minimum:

* semantic recall over embeddings
* scope/filter support
* ranked result return
* minimal hybrid or graph-aware extension where feasible

The design direction is clear that retrieval should not remain plain storage search. It must become behaviorally meaningful. 

### 5. Context assembly

This is one of the key new application behaviors and should be present in the first version.

Given a task or query, MindState should be able to assemble a bounded context bundle composed of:

* overview/synthesis
* supporting raw items
* relevant entities or linked records
* recent decisions or unresolved items where available
* provenance references

This should be exposed both through API and through the UI.

### 6. Higher-level UI

Implement a first higher-level MindState UI inside the application.

This does **not** replace the low-level shell. It complements it.

The new UI should allow a user to:

* capture a note/decision/observation/session item
* search/retrieve memory without writing Cypher
* request a context bundle for a task
* inspect a memory item and its links/projections
* move between higher-level memory workflows and the low-level REPL/shell

The UI can be implemented as:

* an extended TUI mode
* a web UI served by the application
* or both, if economically feasible

The important point is that the user experiences MindState as an application, not only as a database console.

## Proposed API shape

The first API version should expose a behavior-oriented HTTP surface. The design already points toward this shape. 

Minimum endpoints:

* `POST /v1/memory/remember`
* `POST /v1/memory/recall`
* `POST /v1/context/build`

Recommended additional first-wave endpoints:

* `GET /v1/topics/{id}/explain`
* `GET /v1/decisions/history`
* `GET /v1/memory/{id}`
* `GET /v1/memory/{id}/related`
* `POST /v1/work-sessions/log`

Administrative or maintenance endpoints may be added for rebuild/reprojection, but they are secondary in this feature.

## Brownfield adaptation requirements

This feature must deliberately reuse the current base:

* reuse the existing database connectivity and configuration infrastructure where sensible
* reuse the current CLI/TUI and logging patterns where sensible
* build the new API and UI as additional layers, not as a forked second system
* do not create a separate incompatible application core for the new API

The existing low-level tooling is an asset. The new product surface should sit on top of it.

## Data model requirements

The new implementation should introduce the first canonical tables and services for:

* memory items
* sources
* provenance
* chunk projections
* embedding projections

Graph entities, relation edges, digests, and memory links may begin in a narrower implementation than the full target model, but the schema direction should align with the documented technical design. 

Where the current TriStore implementation already has usable graph/vector structures, map or bridge them instead of needlessly duplicating them.

## Non-goals

This feature does not yet require:

* a fully mature knowledge graph
* complete ontology management
* advanced graph analytics
* autonomous memory pruning
* all future maintenance/admin workflows
* every possible digest type

The goal is a credible first MindState application layer, not total completion.

## Acceptance criteria

1. The application exposes a documented first API for `remember`, `recall`, and `build_context`.
2. The API persists canonical memory items and creates at least raw and embedding projections.
3. The application provides a user-facing UI for memory capture and retrieval that does not require Cypher.
4. The existing low-level shell remains available.
5. A user can store an item, retrieve it semantically, and request a context bundle from the same application.
6. The implementation is visibly built on the reused brownfield base, not as an unrelated rewrite.
7. The system vocabulary and user experience reflect MindState rather than TriStore/Cypher-only terminology.

## Technical notes

The design documents already establish the correct architectural center: capability-oriented interfaces, one canonical item with derived views, and Postgres as the initial substrate. This feature should treat that as normative. 

---


# One practical warning

For Feature 2 and Feature 3, resist the temptation to bypass the new service layer and “just call the old Cypher/db code directly” from every interface. That would preserve the brownfield code, but it would also preserve the wrong abstraction boundary. The old low-level shell should remain available, but the new application behaviors must converge on a proper MindState service layer derived from the canonical model described in the design notes. 

If useful, I can turn these three specs into a numbered backlog format with fields like rationale, dependencies, risks, and test strategy.
