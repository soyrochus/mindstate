## 1. Dependencies and Entry Points

- [x] 1.1 Add `mcp>=1.0.0` to `dependencies` in `pyproject.toml`
- [x] 1.2 Add `mstate-mcp = "mindstate.mcp:run"` to `[project.scripts]` in `pyproject.toml`
- [x] 1.3 Run `uv pip install -e .` to register the new dependency and entry point; verify `mstate-mcp --help` is callable

## 2. Configuration

- [x] 2.1 Add `MCPSettings` dataclass to `config.py` with fields: `transport: str`, `host: str`, `port: int`, `enabled_tools: Optional[frozenset[str]]`
- [x] 2.2 Populate `MCPSettings` in `get_settings()` from `MS_MCP_TRANSPORT` (default `"stdio"`), `MS_MCP_HOST` (default `"127.0.0.1"`), `MS_MCP_PORT` (default `8001`), `MS_MCP_ENABLED_TOOLS` (default `None` = all tools)
- [x] 2.3 Add `mcp: MCPSettings` field to `Settings` dataclass

## 3. Data Models

- [x] 3.1 Add `WorkSessionInput` frozen dataclass to `memory_models.py` with fields: `repo`, `branch`, `task`, `summary`, `decisions: List[str]`, `resolved_blockers: List[str]`, `files_changed: List[str]`, `next_steps: List[str]`, `source_agent: Optional[str]`, `contextualize_session: bool = False`
- [x] 3.2 Add `WorkSessionResult` frozen dataclass to `memory_models.py` with fields: `session_memory_id: str`, `decision_memory_ids: List[str]`, `resolved_blocker_memory_ids: List[str]`

## 4. MindStateService — New Methods

- [x] 4.1 Implement `log_work_session(payload: WorkSessionInput) -> WorkSessionResult` on `MindStateService`: store session as `work_session` kind, each decision as `decision` kind via `remember()`, each resolved blocker as `resolved_blocker` kind via `remember()`; respect `contextualize_session` flag for the session item
- [x] 4.2 Implement `find_related_code(repo: str, symbol: str, branch: Optional[str] = None) -> Dict` on `MindStateService`: compose `recall(query=symbol, source=repo, limit=10)` and `get_recent_decisions(limit=5)` scoped to repo; return `{"items": [...], "decisions": [...]}`
- [x] 4.3 Implement `get_recent_project_state(repo: str) -> Dict` on `MindStateService`: return `summaries` (recent `summary` kind), `decisions` (recent `decision` kind), `open_blockers` (recent `blocker` kind), all scoped to `source=repo`

## 5. HTTP API — Work Session Endpoint

- [x] 5.1 Add `WorkSessionRequest` Pydantic model to `api.py` mirroring `WorkSessionInput` fields
- [x] 5.2 Add `WorkSessionResponse` Pydantic model with `session_memory_id`, `decision_memory_ids`, `resolved_blocker_memory_ids`
- [x] 5.3 Add `POST /v1/memory/work-session` endpoint delegating to `svc.log_work_session()`; return `WorkSessionResponse`

## 6. MCP Package Structure

- [x] 6.1 Create `mindstate/mcp/__init__.py` with `run()` entry point that calls `server.start()`
- [x] 6.2 Create `mindstate/mcp/server.py` with: DB connection init, `_ensure_connected()` reconnect guard, MCP server instance creation, tool registration filtered by `settings.mcp.enabled_tools`, startup/shutdown lifecycle, and per-call observability logging decorator
- [x] 6.3 Create `mindstate/mcp/tools.py` with one handler function per tool: `handle_remember`, `handle_recall`, `handle_build_context`, `handle_contextualize`, `handle_log_work_session`, `handle_find_related_code`, `handle_get_recent_project_state` — all thin adapters over `MindStateService`

## 7. MCP Tool Implementations

- [x] 7.1 Implement `handle_remember`: validate required fields, construct `RememberInput`, call `svc.remember(contextualize=...)`, return `{memory_id, chunk_count, embedding_count, contextualization_job_id}`
- [x] 7.2 Implement `handle_recall`: validate `query`, construct `RecallInput`, call `svc.recall()`, return `{items: [...]}`
- [x] 7.3 Implement `handle_build_context`: validate `query`, construct `ContextBuildInput`, call `svc.build_context()`, serialize `ContextBundle` to dict
- [x] 7.4 Implement `handle_contextualize`: validate exactly one of `n`/`ids`, call `svc.contextualize_n()` or `svc.contextualize_ids()`, return `{job_id, queued_count, status}`; return `{job_id: null, queued_count: 0, status: "queued"}` if no items eligible
- [x] 7.5 Implement `handle_log_work_session`: validate required fields, construct `WorkSessionInput`, call `svc.log_work_session()`, serialize `WorkSessionResult` to dict
- [x] 7.6 Implement `handle_find_related_code`: validate `repo` and `symbol`, call `svc.find_related_code()`, return result dict
- [x] 7.7 Implement `handle_get_recent_project_state`: validate `repo`, call `svc.get_recent_project_state()`, return result dict

## 8. Observability and Error Handling

- [x] 8.1 Add per-call logging decorator in `server.py` that captures `tool`, `agent` (from `source_agent` param or `"unknown"`), `success`, `duration_ms`, `side_effects` (e.g. `memory_id`, `job_id`) using `logging_utils`
- [x] 8.2 Wrap all tool handlers in a try/except that returns a structured MCP error response (not an unhandled exception) on `ValidationError`, `EmbeddingUnavailableError`, and unexpected exceptions; log failures via the observability decorator

## 9. Tests

- [x] 9.1 Unit test `MCPSettings`: defaults, env override for `transport`, `host`, `port`, `enabled_tools`
- [x] 9.2 Unit test `WorkSessionInput`/`WorkSessionResult` construction and field defaults
- [x] 9.3 Unit test `MindStateService.log_work_session()`: verify 3 memory items created (session + decision + resolved_blocker), correct kinds, metadata fields, auto-contextualization triggered for decision/resolved_blocker but not session by default
- [x] 9.4 Unit test `log_work_session` with `contextualize_session=True`: verify session item also gets contextualization job
- [x] 9.5 Unit test `MindStateService.find_related_code()`: mocked recall and decisions, verify merge and return shape
- [x] 9.6 Unit test `MindStateService.get_recent_project_state()`: mocked recalls, verify summaries/decisions/open_blockers shape
- [x] 9.7 Integration test `POST /v1/memory/work-session` via FastAPI TestClient: verify response shape and created item count
- [x] 9.8 Unit test MCP tool handler `handle_remember`: mocked service, verify input mapping and output serialization
- [x] 9.9 Unit test MCP tool handler `handle_contextualize`: test n-mode, ids-mode, and zero-eligible-items case
- [x] 9.10 Unit test MCP tool handler `handle_log_work_session`: verify `WorkSessionInput` construction and result mapping
- [x] 9.11 Unit test `MS_MCP_ENABLED_TOOLS` filtering: verify only listed tools are registered in the MCP server
- [x] 9.12 Regression test: `remember()`, `recall()`, `build_context()`, `contextualize_n()` behavior unchanged by MCP additions
