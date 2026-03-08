## 1. API and configuration foundation

- [ ] 1.1 Add FastAPI and any required ASGI runtime dependencies to the project packaging
- [ ] 1.2 Extend configuration settings for API server startup, embedding model selection, and any new memory-service defaults
- [ ] 1.3 Add an application entry path for running the FastAPI surface alongside the existing MindState package layout

## 2. Canonical memory persistence

- [ ] 2.1 Design and implement canonical persistence structures for memory items, provenance, sources, and metadata
- [ ] 2.2 Add persistence structures for chunk projections, embedding projections, and minimal relation-link projections
- [ ] 2.3 Implement database-layer helpers for creating and retrieving canonical memory items and their derived projections
- [ ] 2.4 Verify the additive schema preserves existing PostgreSQL, AGE, pgvector, and low-level query behavior

## 3. Shared service layer

- [ ] 3.1 Create a shared MindState service module that owns high-level memory behaviors
- [ ] 3.2 Implement the `remember` service flow with validation, canonical persistence, chunking, embeddings, and conservative link extraction
- [ ] 3.3 Implement the `recall` service flow with embedding-backed ranking, supported filters, and canonical result shaping
- [ ] 3.4 Implement the `build_context` service flow with bounded overview, supporting items, linked records, and provenance references
- [ ] 3.5 Add clear failure handling for missing or unavailable embedding configuration during high-level remember operations

## 4. HTTP API surface

- [ ] 4.1 Create FastAPI request and response models for `POST /v1/memory/remember`
- [ ] 4.2 Create FastAPI request and response models for `POST /v1/memory/recall`
- [ ] 4.3 Create FastAPI request and response models for `POST /v1/context/build`
- [ ] 4.4 Wire the API endpoints to the shared service layer with consistent error mapping and behavior-oriented vocabulary
- [ ] 4.5 Reserve extension points for adjacent first-wave memory endpoints without changing the initial API contract

## 5. Higher-level TUI workflows

- [ ] 5.1 Extend the existing Textual application with navigation or mode switching between the low-level shell and high-level memory workflows
- [ ] 5.2 Implement TUI flows for capturing a note, decision, observation, or session item through the shared service layer
- [ ] 5.3 Implement TUI flows for ranked memory recall without requiring direct Cypher input
- [ ] 5.4 Implement TUI flows for requesting and presenting bounded context bundles
- [ ] 5.5 Implement TUI memory inspection views for content, metadata, provenance, and available links or projections
- [ ] 5.6 Update TUI labels and prompts to use MindState memory vocabulary rather than database-console terminology for the new workflows

## 6. Verification and documentation

- [ ] 6.1 Add automated tests for canonical memory persistence and derived projection creation
- [ ] 6.2 Add automated tests for remember, recall, and build-context service behavior, including embedding-unavailable failure cases
- [ ] 6.3 Add API tests for the FastAPI endpoints and their request validation behavior
- [ ] 6.4 Add integration or smoke tests covering store, recall, and context flows from the same application instance
- [ ] 6.5 Update README, manuals, and examples to document the new API mode, TUI workflows, and embedding configuration requirements