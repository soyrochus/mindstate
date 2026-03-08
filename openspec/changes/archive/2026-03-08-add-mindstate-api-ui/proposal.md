## Why

MindState currently exposes powerful substrate access, but it still behaves primarily like a Cypher-oriented tool rather than a memory application. This change is needed now to establish the first product-layer API and user experience around canonical memory capture, retrieval, and context assembly while preserving the reused low-level shell.

## What Changes

- Add a behavior-oriented MindState API for foundational memory operations, including `remember`, `recall`, and `build_context`, with room for related memory workflows.
- Introduce the first canonical memory model and projection flow so stored items can produce chunk, embedding, and minimal relation/link projections.
- Add a higher-level application UI for capturing items, retrieving memory, requesting context bundles, and inspecting linked memory without writing Cypher.
- Extend retrieval behavior from raw substrate access to semantic recall with filters, ranking, and bounded context assembly.
- Reuse the existing MindState database, configuration, CLI, TUI, and logging base instead of creating a separate incompatible application core.

## Capabilities

### New Capabilities

- `memory-api`: HTTP endpoints for canonical memory capture, retrieval, context building, and related first-wave memory operations.
- `canonical-memory`: Canonical memory item model, provenance fields, and projection lifecycle for raw, chunk, embedding, and minimal link projections.
- `context-assembly`: Behavior for constructing bounded context bundles that combine synthesis, supporting memory items, linked records, and provenance.
- `application-ui`: Higher-level MindState user interface for capture, recall, context requests, and memory inspection without requiring direct Cypher usage.

### Modified Capabilities

- `db-substrate`: Extend the substrate requirements to persist canonical memory items and derived projections while preserving direct PostgreSQL, graph, and vector access.

## Impact

- Adds a new application-layer API surface and supporting service layer on top of the existing MindState base.
- Adds canonical memory tables or equivalent persisted structures plus projection storage for chunks, embeddings, and minimal graph or relation links.
- Adds a higher-level user-facing interface, likely alongside the current CLI and TUI rather than replacing them.
- Affects retrieval logic, ranking, and context-building behavior across the application.
- Likely introduces additional configuration, documentation, and dependency needs for serving the API, UI, and embedding-backed recall workflows.