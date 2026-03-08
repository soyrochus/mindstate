## ADDED Requirements

### Requirement: MindState provides a higher-level memory UI
The application SHALL provide a user-facing interface for memory workflows that does not require users to write Cypher.

#### Scenario: User can use memory workflows without Cypher
- **WHEN** a user enters the higher-level MindState UI
- **THEN** they can capture and retrieve memory without entering raw Cypher statements

#### Scenario: Low-level shell remains available
- **WHEN** the higher-level UI is introduced
- **THEN** the existing low-level shell remains available as a parallel interface rather than being removed

### Requirement: The higher-level UI supports canonical memory capture and retrieval
The higher-level UI SHALL let a user capture a note, decision, observation, or session item and retrieve memory items through the same shared MindState service layer used by the API.

#### Scenario: User captures a memory item from the UI
- **WHEN** a user submits a new memory item from the higher-level UI
- **THEN** the system stores it as a canonical memory item through the shared application service layer

#### Scenario: User retrieves memory from the UI
- **WHEN** a user searches or recalls memory from the higher-level UI
- **THEN** the system returns ranked memory results without requiring direct substrate commands

### Requirement: The higher-level UI supports context requests and memory inspection
The higher-level UI SHALL allow users to request a context bundle for a task and inspect a memory item's links or projections.

#### Scenario: User requests task context from the UI
- **WHEN** a user asks the higher-level UI to build context for a task
- **THEN** the UI presents the assembled context bundle returned by the application service layer

#### Scenario: User inspects a memory item
- **WHEN** a user opens a remembered item in the higher-level UI
- **THEN** the UI exposes the item's content, metadata, provenance, and available links or projections

### Requirement: The UI presents MindState product vocabulary
The higher-level UI SHALL present the system as MindState memory workflows rather than as a Cypher or database console.

#### Scenario: UI language is product-oriented
- **WHEN** the higher-level UI is displayed
- **THEN** its labels and flows are framed around memory behaviors such as remember, recall, and context rather than raw database mechanics