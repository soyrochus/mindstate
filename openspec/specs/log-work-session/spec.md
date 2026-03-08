## Purpose
Define structured work-session logging and related project-state memory composition.

## Requirements

### Requirement: `MindStateService.log_work_session()` stores a session and child items atomically
`MindStateService` SHALL expose a `log_work_session(payload: WorkSessionInput) -> WorkSessionResult` method. It SHALL store: (1) a `work_session` memory item containing the session summary, (2) one `decision` memory item per entry in `payload.decisions`, (3) one `resolved_blocker` memory item per entry in `payload.resolved_blockers`. Each `decision` and `resolved_blocker` item SHALL be stored using `remember()` with `contextualize=False` (the kind policy triggers auto-contextualization via `AUTO_CONTEXTUALIZE_KINDS`).

#### Scenario: Session creates correct item kinds
- **WHEN** `log_work_session` is called with `decisions=["Use JWT"]` and `resolved_blockers=["Redis fixed"]`
- **THEN** three memory items are created: one with `kind="work_session"`, one with `kind="decision"`, one with `kind="resolved_blocker"`

#### Scenario: Decision items are auto-contextualized by kind policy
- **WHEN** `log_work_session` is called with non-empty `decisions`
- **THEN** each resulting `decision` memory item triggers a contextualization job (because `decision` is in `AUTO_CONTEXTUALIZE_KINDS`) without `log_work_session` explicitly requesting it

#### Scenario: Session item carries structured metadata
- **WHEN** `log_work_session` is called with `repo="myrepo"`, `branch="main"`, `task="implement auth"`, `files_changed=["auth.py"]`, `next_steps=["add tests"]`
- **THEN** the `work_session` memory item has `source="myrepo"`, and its `metadata` contains `branch`, `task`, `files_changed`, and `next_steps`

### Requirement: `WorkSessionInput` model captures all structured session fields
A `WorkSessionInput` dataclass SHALL be added to `memory_models.py` with the following fields: `repo` (str, required), `branch` (str, required), `task` (str, required), `summary` (str, required), `decisions` (List[str], default empty), `resolved_blockers` (List[str], default empty), `files_changed` (List[str], default empty), `next_steps` (List[str], default empty), `source_agent` (Optional[str]), `contextualize_session` (bool, default False).

#### Scenario: Minimal valid input
- **WHEN** `WorkSessionInput(repo="r", branch="b", task="t", summary="s")` is constructed
- **THEN** the object is created with all list fields defaulting to empty and `contextualize_session=False`

#### Scenario: Full input round-trips correctly
- **WHEN** `WorkSessionInput` is constructed with all fields populated
- **THEN** all values are accessible as attributes with correct types

### Requirement: `WorkSessionResult` captures all created item identifiers
A `WorkSessionResult` dataclass SHALL be added to `memory_models.py` with: `session_memory_id` (str), `decision_memory_ids` (List[str]), `resolved_blocker_memory_ids` (List[str]).

#### Scenario: Result contains all created IDs
- **WHEN** `log_work_session` returns successfully with 2 decisions and 1 resolved blocker
- **THEN** `WorkSessionResult.decision_memory_ids` has 2 entries and `resolved_blocker_memory_ids` has 1 entry

### Requirement: `log_work_session` is callable from the HTTP API
`POST /v1/memory/work-session` SHALL accept a `WorkSessionRequest` Pydantic model (mirroring `WorkSessionInput` fields) and delegate to `MindStateService.log_work_session()`. It SHALL return a `WorkSessionResponse` with the created IDs.

#### Scenario: HTTP endpoint stores session and returns IDs
- **WHEN** `POST /v1/memory/work-session` is called with a valid body
- **THEN** HTTP 200 is returned with `session_memory_id`, `decision_memory_ids`, `resolved_blocker_memory_ids`

#### Scenario: Missing required fields returns 422
- **WHEN** `POST /v1/memory/work-session` is called with `repo` missing
- **THEN** HTTP 422 is returned

### Requirement: `MindStateService.find_related_code()` composes recall and decisions
`MindStateService` SHALL expose `find_related_code(repo: str, symbol: str, branch: Optional[str] = None) -> Dict` that calls `recall(query=symbol, source=repo, limit=10)` and `get_recent_decisions(limit=5)` filtered by `source=repo`, returning a merged result dict with keys `items` and `decisions`.

#### Scenario: Symbol search returns related items
- **WHEN** `find_related_code(repo="myrepo", symbol="ConnectionPool")` is called
- **THEN** the result contains `items` (semantic matches) and `decisions` (recent decisions with `source="myrepo"`)

### Requirement: `MindStateService.get_recent_project_state()` composes recall for project overview
`MindStateService` SHALL expose `get_recent_project_state(repo: str) -> Dict` that returns `summaries` (recent `summary` kind items from `source=repo`), `decisions` (recent `decision` kind items), and `open_blockers` (`blocker` kind items that have no corresponding `resolved_blocker` — approximated by most recent `blocker` items for now).

#### Scenario: Project state returned for known repo
- **WHEN** `get_recent_project_state(repo="myrepo")` is called with stored memory items
- **THEN** result has `summaries`, `decisions`, `open_blockers` lists, all scoped to `source="myrepo"`