## MODIFIED Requirements

### Requirement: Database substrate behavior is unchanged
The underlying PostgreSQL/AGE/pgvector stack SHALL remain the substrate for MindState after this feature. This change MAY add canonical memory and projection storage structures on top of that substrate, but it MUST NOT remove or break existing direct PostgreSQL, AGE, pgvector, or low-level query execution behavior.

#### Scenario: Existing substrate access remains available
- **WHEN** the application connects to the database after the feature is implemented
- **THEN** direct PostgreSQL, AGE, and pgvector access still functions for existing low-level workflows

#### Scenario: Additive memory storage does not replace the substrate
- **WHEN** canonical memory tables or projection structures are introduced
- **THEN** they are added on top of the current PostgreSQL/AGE/pgvector substrate rather than replacing it with a different backend

## ADDED Requirements

### Requirement: The substrate persists canonical memory and derived projections
The database substrate SHALL support persistence for canonical memory items and their derived chunk, embedding, and minimal relation-link projections.

#### Scenario: Canonical memory storage is backed by the substrate
- **WHEN** a memory item is remembered
- **THEN** the substrate stores the canonical record and its associated projection records in database-managed structures

#### Scenario: Derived projections remain queryable through the substrate
- **WHEN** embeddings or relation links are created for a memory item
- **THEN** they remain queryable through the existing PostgreSQL, pgvector, and graph-capable substrate layers

### Requirement: The substrate supports higher-level retrieval without removing direct inspection
The substrate SHALL support application-level semantic recall and context assembly while preserving direct low-level inspection paths.

#### Scenario: High-level retrieval and low-level inspection coexist
- **WHEN** the application adds semantic recall and context assembly behavior
- **THEN** those behaviors use the substrate while direct low-level inspection remains available to users and operators