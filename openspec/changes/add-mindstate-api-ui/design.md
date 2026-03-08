## Context

MindState currently provides a reused brownfield base centered on PostgreSQL, Apache AGE, pgvector, and shared CLI and TUI front ends. The existing package is effective for direct Cypher execution and LLM-assisted graph access, but its abstraction boundary is still substrate-first: user interaction flows through REPL-oriented commands, database execution helpers, and prompt-driven query generation rather than through a product-level memory service.

This change introduces the first application layer that treats MindState as a memory system. The feature brief and proposal establish four new capabilities: a behavior-oriented memory API, a canonical memory object and projection lifecycle, bounded context assembly, and a higher-level application UI. The design must preserve the existing low-level shell, reuse the current database and configuration infrastructure, and avoid creating a second incompatible application core.

The current architecture already has the key primitives needed for a brownfield expansion: one Python package, a shared configuration model, a common database layer, logging utilities, and substrate support for relational, vector, and graph access. The missing piece is a service layer that accepts memory-oriented requests, persists canonical items, drives projection work, and serves both HTTP and interactive UI use cases from the same domain model.

## Goals / Non-Goals

**Goals:**
- Add a first-class MindState service layer above the existing database helpers so new behaviors do not depend on UI-specific or Cypher-specific code paths.
- Define a canonical memory item model with persisted raw content, provenance, metadata, and derived projections for chunks, embeddings, and minimal graph or relation links.
- Expose the service layer through a behavior-oriented HTTP API for `remember`, `recall`, `build_context`, and adjacent retrieval workflows.
- Add a higher-level user interface that supports capture, retrieval, context requests, and memory inspection without requiring direct Cypher input.
- Reuse the existing PostgreSQL, AGE, pgvector, configuration, logging, CLI, and TUI base while preserving the low-level shell as a parallel interface.
- Keep the initial graph and digest behavior conservative so the feature lands a coherent first application layer rather than an overbuilt ontology system.

**Non-Goals:**
- Replacing or removing the current low-level CLI or TUI REPL.
- Building a fully mature knowledge graph, ontology manager, or autonomous memory maintenance system.
- Reworking the substrate into a new storage backend or separate microservice architecture.
- Delivering every aspirational endpoint from the design notes in the first iteration.
- Turning projection generation into a distributed or asynchronous pipeline unless the implementation complexity clearly requires it.

## Decisions

### 1. Introduce a shared MindState service layer between interfaces and the substrate

**Decision:** Add an application service layer that becomes the only entry point for high-level memory behaviors such as remember, recall, related-memory traversal, and context assembly.

**Rationale:** The feature brief explicitly warns against wiring each new interface directly into the existing Cypher and database code. A dedicated service layer keeps behavior-oriented logic centralized, allows the HTTP API and UI to share the same semantics, and preserves the low-level shell as a separate substrate-oriented path rather than the hidden implementation for the new product surface.

**Alternatives considered:**
- Call existing `db.py` and Cypher helpers directly from each endpoint and UI action. Rejected because it would preserve the wrong abstraction boundary and duplicate retrieval and projection logic across interfaces.
- Split the new API into a separate application package or process. Rejected for the first iteration because it adds deployment and integration complexity without solving a present scaling problem.

### 2. Persist canonical memory items in relational tables and derive graph/vector projections from them

**Decision:** Treat a canonical `memory_items` record as the source of truth, with adjacent relational tables for provenance, sources, chunk projections, embedding projections, and minimal relation links or extracted entities.

**Rationale:** The core design principle is one canonical memory object with multiple projections. Relational persistence is the simplest stable representation for the canonical item and works naturally with the existing PostgreSQL substrate. Graph and vector layers remain derived views that support retrieval and linkage without becoming the primary source of truth.

**Alternatives considered:**
- Store canonical memory as AGE vertices only. Rejected because canonical memory requires structured metadata, provenance, and lifecycle management that are easier to govern relationally.
- Store raw memory items in semi-structured JSON only. Rejected because retrieval, provenance tracking, and projection management benefit from explicit schema and joinable fields.

### 3. Implement projection generation as an internal synchronous workflow for the first version

**Decision:** For the initial product layer, execute persistence and initial projection generation in-process during `remember`, producing raw item storage, chunk rows, embeddings, and conservative link extraction before returning success.

**Rationale:** The codebase is currently a single-process application. A synchronous path keeps the initial implementation straightforward, deterministic, and easier to test. It also guarantees that a newly remembered item is immediately available for recall and context assembly without separate job coordination.

**Alternatives considered:**
- Add an asynchronous worker and queue for projection generation. Rejected for the first iteration because it would add deployment, retry, and consistency complexity before product semantics are proven.
- Only store the raw item initially and defer all projections until requested. Rejected because the feature acceptance criteria call for raw plus embedding projections, and immediate availability is important for a usable memory workflow.

### 4. Use a thin HTTP layer over the service layer rather than making the API the primary implementation

**Decision:** Implement the HTTP surface as a transport adapter over the service layer, with endpoint handlers responsible mainly for request validation, response shaping, and error mapping.

**Rationale:** The new API is one interface among several. Keeping the HTTP layer thin prevents business logic from being trapped in web handlers and lets the higher-level UI reuse the same services directly. This also makes it easier to keep naming, ranking, and context-building semantics aligned across interfaces.

**Alternatives considered:**
- Build API-first handlers and have the UI call the HTTP interface internally. Rejected because it introduces unnecessary transport overhead and complicates local integration inside a single process.

### 5. Extend the existing TUI first, with room for a later web UI if justified

**Decision:** The first higher-level UI should be implemented as an additional mode or workflow within the existing application, most naturally by extending the current TUI and CLI integration points rather than introducing a mandatory browser-based UI.

**Rationale:** The feature requires a user-facing UI that does not replace the low-level shell. The existing Textual TUI already provides the right host for richer forms, result panes, and navigation without creating a second application runtime. This fits the brownfield constraint and reduces initial surface area. The design should keep the service layer neutral so a future web UI can be added without re-architecting domain logic.

**Alternatives considered:**
- Build only a web UI in the first iteration. Rejected because it adds a new runtime and deployment story before the service model is stabilized.
- Build both TUI and web UI immediately. Rejected because it spreads the first product-layer iteration too thin.

### 6. Represent context assembly as a first-class domain operation with bounded inputs and outputs

**Decision:** Model `build_context` as a dedicated service operation that accepts a task or query plus optional scope filters and returns a structured bundle containing synthesis, ranked supporting items, linked entities or relations, recent decisions, unresolved items when available, and provenance references.

**Rationale:** Context assembly is a core MindState behavior, not just a different search response shape. Treating it as its own operation keeps API and UI contracts clear and makes bounded result composition an explicit part of the design rather than an ad hoc layer over recall.

**Alternatives considered:**
- Implement context building as a client-side composition of several recall requests. Rejected because the core ranking and bundling logic belongs in the application, where substrate signals can be combined consistently.

### 7. Keep retrieval hybrid-ready but begin with embedding-first ranking plus lightweight graph awareness

**Decision:** The first recall implementation should center on semantic similarity over embeddings, then refine or annotate results with scope filters, recency, memory kind, and conservative relation signals where available.

**Rationale:** The feature brief requires usable semantic recall and ranked results without demanding a full hybrid retrieval engine on day one. Embedding-first ranking is the most direct route to a meaningful first experience, while leaving room to incorporate graph relationships and entity links where they improve result quality.

**Alternatives considered:**
- Use direct SQL or Cypher filtering only. Rejected because that would not meet the semantic retrieval requirement.
- Build a full multi-stage retrieval engine before shipping. Rejected because it would overbuild the first version.

### 8. Use FastAPI for the first HTTP surface

**Decision:** Implement the first HTTP API on FastAPI so the application uses an ASGI stack that is directly compatible with the later FastMCP integration path.

**Rationale:** The user requested an HTTP framework compatible with FastMCP. FastAPI fits the existing single-process Python packaging model, keeps request validation and response modeling straightforward, and aligns with an eventual MCP surface without forcing a second transport stack.

**Alternatives considered:**
- Use Flask or another WSGI-first framework. Rejected because it creates a less direct path for FastMCP-oriented integration and a weaker fit for typed request and response contracts.
- Delay framework choice until implementation starts. Rejected because the API transport layer is now a concrete architectural decision.

### 9. Make the first higher-level UI TUI-only

**Decision:** The first higher-level user interface will be implemented in the existing Textual TUI. No web UI is included in this milestone.

**Rationale:** The user chose the TUI path, and it remains the most economical brownfield extension. It preserves a single application runtime, keeps development focused on the shared service layer, and still satisfies the requirement for a user-facing interface that does not require Cypher.

**Alternatives considered:**
- Add a minimal web UI in the same milestone. Rejected because it would broaden the surface area before the service model and core workflows are proven.
- Build only the HTTP API and defer UI entirely. Rejected because the feature explicitly requires a higher-level user interface.

### 10. Default embeddings to the existing OpenAI-compatible stack

**Decision:** Use the existing `langchain-openai` integration as the default embedding path for the first recall workflow, with `text-embedding-3-small` as the baseline default model unless configuration overrides it.

**Rationale:** The repository already depends on the OpenAI-oriented LangChain stack, so this is the lowest-friction default. `text-embedding-3-small` is a sensible first baseline because it is widely supported, cost-conscious, and adequate for a first semantic recall implementation.

**Alternatives considered:**
- Introduce a new embedding provider in the first milestone. Rejected because it adds configuration and dependency complexity without a demonstrated need.
- Leave the default model unspecified. Rejected because the first recall workflow needs a concrete baseline for implementation and testing.

### 11. Fail embedding-backed remember requests clearly when embeddings are unavailable

**Decision:** The first implementation will treat embeddings as required for the high-level memory workflow. If the configured embedding provider is unavailable, `remember` will fail with a clear error rather than silently storing degraded high-level memory records.

**Rationale:** The first recall behavior is explicitly embedding-backed, and the design currently assumes synchronous projection generation before success is returned. Failing clearly keeps behavior deterministic, avoids hidden partial states in the new product layer, and makes operational problems visible early.

**Alternatives considered:**
- Persist canonical memory without embeddings and mark it degraded. Rejected for the first milestone because it complicates recall semantics and introduces partial-ingestion states before the system has operational tooling for repair or reprojection.
- Queue embeddings for later retry. Rejected because deferred projection is outside the initial synchronous design.

### 12. Keep first-pass relation extraction conservative and context output structured

**Decision:** The first projection pass will extract only high-confidence, evidence-backed links such as explicit references, repeated named entities, or obvious memory-to-memory relationships. The `build_context` service will return structured JSON with an overview field and supporting evidence fields; it will not require a separate LLM-generated free-form summary mode in this milestone.

**Rationale:** Conservative extraction matches the design goal of avoiding premature ontology work. Structured JSON is the right stable contract for API, TUI, and later MCP consumers. An overview field inside the structured response preserves the context-bundle concept without making first delivery depend on a separate synthesis transport or mandatory LLM generation step.

**Alternatives considered:**
- Perform broader entity and relation extraction in the first pass. Rejected because precision risk is high and the milestone does not require a mature graph layer.
- Add a second free-form synthesized context mode immediately. Rejected because the structured bundle is the stable interface, and additional synthesis can be layered in later if needed.

## Risks / Trade-offs

- [Service boundary drift] → If endpoint handlers or UI event code bypass the new service layer, semantics will diverge quickly. Mitigation: make the service layer the only implementation path for new high-level behaviors and keep transport and UI adapters thin.
- [Synchronous remember latency] → Embedding generation and link extraction may increase write latency. Mitigation: keep first-wave projection work conservative, cap chunk sizes, and preserve the option to move projection work async later without changing the canonical model.
- [Schema design churn] → The first canonical memory schema may need refinement as more behaviors arrive. Mitigation: normalize only the stable fields now, keep metadata extensible, and avoid prematurely rigid graph structures.
- [UI complexity inside the existing TUI] → Adding product workflows to the TUI can complicate the current REPL-centric interaction model. Mitigation: separate low-level shell and higher-level memory workflows clearly in navigation and state management.
- [Retrieval quality expectations] → Users may expect better ranking and synthesis than the first implementation can provide. Mitigation: document the initial retrieval model, include provenance in responses, and keep the service interfaces compatible with later ranking improvements.
- [Operational dependency growth] → Serving HTTP plus embedding-backed workflows may add runtime dependencies and configuration burden. Mitigation: layer new dependencies carefully, reuse existing configuration patterns, and keep optional integrations explicit.

## Migration Plan

1. Introduce canonical schema objects and persistence helpers for memory items, provenance, chunks, embeddings, and minimal relation links on top of the current PostgreSQL substrate.
2. Add a MindState service layer that owns remember, recall, related-memory lookup, and context assembly behaviors.
3. Add an HTTP transport layer that exposes the first `/v1/memory/*` and `/v1/context/*` endpoints through the shared services.
4. Extend the existing interactive application with higher-level memory capture and retrieval workflows while preserving the current low-level shell path.
5. Update configuration, documentation, and examples to cover the new API/UI operation mode and any embedding or projection requirements.
6. Validate the brownfield path with smoke tests covering: storing a memory item, generating projections, recalling it semantically, and building a context bundle from the same application.

**Rollback:** Revert the application-layer additions in git and disable the new endpoints or UI mode. Because the initial change is additive and keeps the low-level shell intact, rollback can focus on the new service and interface layers. If schema additions are introduced, they should be additive tables that can be ignored or dropped without affecting existing Cypher REPL behavior.

## Open Questions

- None for the initial milestone.