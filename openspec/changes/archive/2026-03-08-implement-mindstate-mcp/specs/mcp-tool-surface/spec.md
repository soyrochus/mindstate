## ADDED Requirements

### Requirement: `remember` tool stores a memory item
The `remember` MCP tool SHALL accept structured input and delegate to `MindStateService.remember()`. It SHALL return the stored `memory_id`, `chunk_count`, `embedding_count`, and `contextualization_job_id` (if a job was enqueued).

Input fields: `kind` (required), `content` (required), `source` (optional), `author` (optional), `source_agent` (optional, maps to `author`), `metadata` (optional dict), `provenance_anchor` (optional), `contextualize` (optional bool, default determined by kind policy).

#### Scenario: Basic remember call
- **WHEN** a client calls `remember` with `kind="note"` and `content="PostgreSQL connection pooling should use pgbouncer"`
- **THEN** the tool returns `{"memory_id": "<uuid>", "chunk_count": 1, "embedding_count": 1, "contextualization_job_id": null}`

#### Scenario: remember with auto-contextualize kind
- **WHEN** a client calls `remember` with `kind="decision"` and `content="Use PostgreSQL 18 for production"`
- **THEN** the tool returns a `contextualization_job_id` (non-null) because `decision` is in `AUTO_CONTEXTUALIZE_KINDS`

#### Scenario: remember with explicit contextualize flag
- **WHEN** a client calls `remember` with `kind="note"` and `contextualize=true`
- **THEN** a contextualization job is enqueued and `contextualization_job_id` is returned

### Requirement: `recall` tool retrieves memory by semantic query
The `recall` MCP tool SHALL accept `query` (required), `limit` (optional, default 10), `kind` (optional), `source` (optional) and delegate to `MindStateService.recall()`. It SHALL return a ranked list of results.

#### Scenario: Basic recall
- **WHEN** a client calls `recall` with `query="database connection strategy"`
- **THEN** the tool returns up to 10 items ranked by semantic similarity, each with `memory_id`, `kind`, `content`, `score`, `source`, `author`

#### Scenario: Filtered recall by kind
- **WHEN** a client calls `recall` with `query="decisions"` and `kind="decision"`
- **THEN** only items with `kind="decision"` are returned

#### Scenario: Empty result set
- **WHEN** a client calls `recall` with a query that matches nothing
- **THEN** the tool returns `{"items": []}` without error

### Requirement: `build_context` tool assembles a bounded context bundle
The `build_context` MCP tool SHALL accept `query` (required), `limit` (optional, default 10), `kind` (optional), `source` (optional) and delegate to `MindStateService.build_context()`. It SHALL return `overview`, `supporting_items`, `linked_records`, and `provenance_references`.

#### Scenario: Context bundle for a task query
- **WHEN** a client calls `build_context` with `query="implement caching layer"`
- **THEN** the tool returns a bundle with an `overview` string, a list of supporting memory items, linked records (including recent decisions), and provenance references

### Requirement: `contextualize` tool triggers graph contextualization
The `contextualize` MCP tool SHALL accept either `n` (int, default 1) or `ids` (list of UUID strings) and delegate to `MindStateService.contextualize_n()` or `MindStateService.contextualize_ids()`. It SHALL return `job_id`, `queued_count`, and `status`.

#### Scenario: Contextualize most recent item
- **WHEN** a client calls `contextualize` with no arguments
- **THEN** the tool returns `{"job_id": "<uuid>", "queued_count": 1, "status": "queued"}`

#### Scenario: Contextualize specific items by id
- **WHEN** a client calls `contextualize` with `ids=["<uuid1>", "<uuid2>"]`
- **THEN** both items are queued in one job and `queued_count=2` is returned

#### Scenario: No eligible items
- **WHEN** a client calls `contextualize` and no non-contextualized items exist
- **THEN** the tool returns `{"job_id": null, "queued_count": 0, "status": "queued"}`

### Requirement: `log_work_session` tool captures a structured work session
The `log_work_session` MCP tool SHALL accept: `repo` (required), `branch` (required), `task` (required), `summary` (required), `decisions` (list of strings, optional), `resolved_blockers` (list of strings, optional), `files_changed` (list of strings, optional), `next_steps` (list of strings, optional), `source_agent` (optional), `contextualize_session` (bool, optional, default false).

It SHALL delegate to `MindStateService.log_work_session()` and return `session_memory_id`, `decision_memory_ids`, `resolved_blocker_memory_ids`, and any `contextualization_job_ids`.

#### Scenario: Session stored with child items
- **WHEN** a client calls `log_work_session` with `repo="myrepo"`, `task="implement auth"`, `decisions=["Use JWT tokens"]`, `resolved_blockers=["Redis timeout fixed"]`
- **THEN** the tool returns `session_memory_id` (kind `work_session`), `decision_memory_ids` with 1 UUID, `resolved_blocker_memory_ids` with 1 UUID

#### Scenario: Decision and resolved_blocker items are auto-contextualized
- **WHEN** `log_work_session` is called with non-empty `decisions` and `resolved_blockers`
- **THEN** each decision and resolved_blocker item has `contextualization_job_id` in the response (they are in `AUTO_CONTEXTUALIZE_KINDS`)

#### Scenario: Session item not auto-contextualized unless opt-in
- **WHEN** `log_work_session` is called without `contextualize_session=true`
- **THEN** the session item (kind `work_session`) has no contextualization job enqueued

#### Scenario: Opt-in session contextualization
- **WHEN** `log_work_session` is called with `contextualize_session=true`
- **THEN** a contextualization job is also enqueued for the session item itself

### Requirement: `find_related_code` tool retrieves memory relevant to a code symbol or path
The `find_related_code` MCP tool SHALL accept `repo` (required), `symbol` (required — a class name, function, path, or concept), `branch` (optional). It SHALL delegate to `MindStateService.find_related_code()` and return a merged set of semantic recall results and recent decisions scoped to `source=repo`.

#### Scenario: Symbol lookup returns related memories
- **WHEN** a client calls `find_related_code` with `repo="myrepo"` and `symbol="ConnectionPool"`
- **THEN** the tool returns memory items whose content mentions or is related to `ConnectionPool`, plus any relevant decisions stored with `source="myrepo"`

#### Scenario: No matches returns empty result
- **WHEN** a client calls `find_related_code` with a symbol that has no memory items
- **THEN** the tool returns `{"items": [], "decisions": []}` without error

### Requirement: `get_recent_project_state` tool returns the latest project cognitive summary
The `get_recent_project_state` MCP tool SHALL accept `repo` (required) and delegate to `MindStateService.get_recent_project_state()`. It SHALL return recent `summary` items, recent `decision` items, and unresolved `blocker` items for that repo.

#### Scenario: Project state for known repo
- **WHEN** a client calls `get_recent_project_state` with `repo="myrepo"`
- **THEN** the tool returns `{"summaries": [...], "decisions": [...], "open_blockers": [...]}` populated from memory items with `source="myrepo"`

#### Scenario: Unknown repo returns empty state
- **WHEN** a client calls `get_recent_project_state` with a `repo` that has no stored memory
- **THEN** the tool returns empty lists in all fields without error

### Requirement: All MCP tools return structured errors on validation failure
If a required tool input is missing or invalid, the tool SHALL return a structured MCP error response (not raise an unhandled exception). The error SHALL include a human-readable message describing the missing or invalid field.

#### Scenario: Missing required field
- **WHEN** a client calls `remember` without the required `content` field
- **THEN** the tool returns an MCP error with a message such as `"content is required"`

#### Scenario: Invalid contextualize arguments
- **WHEN** a client calls `contextualize` with both `n` and `ids` provided simultaneously
- **THEN** the tool returns an MCP error indicating that exactly one of `n` or `ids` must be provided
