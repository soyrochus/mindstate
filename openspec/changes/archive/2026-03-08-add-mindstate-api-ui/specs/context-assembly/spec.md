## ADDED Requirements

### Requirement: MindState builds bounded context bundles
The system SHALL provide a `build_context` behavior that assembles a bounded context bundle for a task or query instead of returning an unstructured list of search hits.

#### Scenario: Context bundle is built for a task
- **WHEN** a client requests context for a task or query
- **THEN** the system returns a structured context bundle rather than only raw recall matches

#### Scenario: Context assembly remains bounded
- **WHEN** the system builds a context bundle
- **THEN** it applies explicit limits to the amount of supporting material included in the response

### Requirement: Context bundles combine synthesis and supporting evidence
Each context bundle SHALL include an overview or synthesis plus supporting raw items and provenance references.

#### Scenario: Context bundle includes synthesis and evidence
- **WHEN** a context bundle is returned
- **THEN** it contains a synthesized overview and references to the supporting memory items used to build it

#### Scenario: Context bundle includes provenance references
- **WHEN** a user inspects the assembled context
- **THEN** the response exposes provenance information for the underlying supporting items

### Requirement: Context assembly incorporates linked records when available
The system SHALL include relevant linked entities, related memory, recent decisions, or unresolved items in a context bundle when those signals are available and relevant.

#### Scenario: Linked context is included when present
- **WHEN** related records or linked memory items exist for the query
- **THEN** the context bundle includes those linked records alongside the primary supporting items

#### Scenario: Missing optional signals do not block context creation
- **WHEN** recent decisions or unresolved items are not available for a query
- **THEN** the system still returns a valid context bundle using the signals it does have

### Requirement: Context assembly is available through API and higher-level UI
The `build_context` behavior SHALL be exposed through the application API and the higher-level MindState UI.

#### Scenario: API and UI use the same context behavior
- **WHEN** a user requests context through either the API or the higher-level UI
- **THEN** both interfaces are backed by the same application-level context assembly behavior