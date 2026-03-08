## ADDED Requirements

### Requirement: MindState exposes canonical memory API endpoints
The system SHALL expose a behavior-oriented HTTP API for canonical memory workflows. The first version SHALL include `POST /v1/memory/remember`, `POST /v1/memory/recall`, and `POST /v1/context/build`.

#### Scenario: Required endpoints are published
- **WHEN** the first application API is inspected
- **THEN** it includes `POST /v1/memory/remember`, `POST /v1/memory/recall`, and `POST /v1/context/build`

#### Scenario: API vocabulary is behavior-oriented
- **WHEN** a client reads the first API surface
- **THEN** memory operations are expressed with MindState behaviors rather than direct substrate or Cypher execution primitives

### Requirement: Remember requests persist canonical memory through the shared service layer
The `POST /v1/memory/remember` endpoint SHALL accept a canonical memory submission, validate required fields, and create the memory item through the shared MindState service layer rather than through UI-specific code paths.

#### Scenario: Remember request stores a memory item
- **WHEN** a client submits a valid remember request
- **THEN** the system creates a canonical memory item and returns a successful response containing the stored item identity

#### Scenario: Remember request rejects invalid canonical input
- **WHEN** a client submits a remember request without the required canonical content fields
- **THEN** the system returns a client error and does not persist a partial memory item

### Requirement: Recall requests provide ranked semantic retrieval with filters
The `POST /v1/memory/recall` endpoint SHALL support semantic retrieval over embedding projections, optional scope or metadata filters, and ranked result output.

#### Scenario: Recall returns ranked matches
- **WHEN** a client submits a recall query for previously stored memory
- **THEN** the system returns ranked matching memory items rather than only exact identifier lookups

#### Scenario: Recall applies scope filters
- **WHEN** a client submits a recall query with supported filters such as memory kind, source, or time scope
- **THEN** the returned result set is constrained to items matching those filters

### Requirement: The API surface supports related first-wave memory workflows
The first API version SHALL reserve room for adjacent behaviors such as direct memory lookup, related-memory traversal, decision history, topic explanation, or work-session logging without requiring a second incompatible API design.

#### Scenario: First-wave extension paths are consistent
- **WHEN** additional first-wave memory endpoints are added
- **THEN** they fit under the same versioned behavior-oriented API surface and reuse the same canonical service model