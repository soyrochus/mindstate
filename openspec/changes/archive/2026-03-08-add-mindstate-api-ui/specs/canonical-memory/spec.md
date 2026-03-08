## ADDED Requirements

### Requirement: Canonical memory items are the source of truth
The system SHALL persist each remembered item as a canonical memory object that acts as the source of truth for all derived retrieval and graph projections.

#### Scenario: Canonical item is stored before derived projections
- **WHEN** a memory item is remembered
- **THEN** the canonical memory record is persisted as the authoritative representation before or alongside derived projections

#### Scenario: Retrieval resolves to canonical memory identity
- **WHEN** a memory item is returned by recall or context assembly
- **THEN** the result references the canonical memory identity rather than only a chunk, embedding, or graph-specific identifier

### Requirement: Canonical memory items contain core memory fields
Each canonical memory item SHALL preserve fields equivalent to identity, kind, content, content format, source, author, timestamps, metadata, and provenance anchor.

#### Scenario: Canonical record includes required memory fields
- **WHEN** a canonical memory item is inspected after creation
- **THEN** it includes values or null-safe placeholders for identity, kind, content, content format, source, author, timestamps, metadata, and provenance anchor

#### Scenario: Provenance survives persistence and retrieval
- **WHEN** a stored memory item is retrieved later
- **THEN** its provenance anchor and source metadata remain available to clients and higher-level UI workflows

### Requirement: Remember operations create first-wave derived projections
When a canonical memory item is stored, the system SHALL create derived chunk projections, embedding projections, and a minimal graph or relation-link projection for that item.

#### Scenario: Chunk and embedding projections are created
- **WHEN** a new memory item is remembered
- **THEN** the system creates at least one chunk projection and at least one embedding projection associated with the canonical item

#### Scenario: Minimal relation projection is created conservatively
- **WHEN** the system derives graph or relation information from a remembered item
- **THEN** it creates only minimal, evidence-backed links rather than requiring a full ontology extraction pass

### Requirement: Canonical memory supports extensible metadata without changing the source model
The canonical memory model SHALL allow additional metadata or projection detail to be added in later iterations without replacing the canonical item contract.

#### Scenario: New projection data does not replace canonical storage
- **WHEN** later features add richer graph, digest, or retrieval projections
- **THEN** the canonical memory item remains the stable source model for those derived views