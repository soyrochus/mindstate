## Purpose
Define the MindState MCP server runtime, registration, and lifecycle behavior.

## Requirements

### Requirement: MCP server is implemented as `mindstate/mcp/` internal package
MindState SHALL provide an MCP server as a dedicated internal package at `mindstate/mcp/` containing at minimum `__init__.py`, `server.py`, and `tools.py`. The package SHALL NOT duplicate business logic from `MindStateService` — all memory operations SHALL delegate to it.

#### Scenario: Package exists and is importable
- **WHEN** `import mindstate.mcp` is executed
- **THEN** the module loads without error and exposes a `run()` entry point

#### Scenario: No business logic duplication
- **WHEN** a MCP tool handler is called
- **THEN** all memory reads and writes are performed through `MindStateService` methods, not through direct DB or `memory_db` calls

### Requirement: `mstate-mcp` is a registered entry point using stdio transport
A `mstate-mcp` script entry point SHALL be registered in `pyproject.toml` pointing to `mindstate.mcp:run`. The server SHALL use stdio transport by default, accepting MCP requests on stdin and writing responses to stdout. Running `mstate-mcp` SHALL start the MCP server and block until the client disconnects.

#### Scenario: Entry point registered
- **WHEN** `pip install -e .` or `uv pip install -e .` is run
- **THEN** `mstate-mcp` is available as a shell command

#### Scenario: stdio transport operational
- **WHEN** `mstate-mcp` is started and a valid MCP `initialize` request is sent on stdin
- **THEN** the server responds with its capabilities on stdout and remains running

#### Scenario: Server lists all registered tools on initialize
- **WHEN** an MCP client calls `tools/list`
- **THEN** the response includes all enabled tools: `remember`, `recall`, `build_context`, `contextualize`, `log_work_session`, `find_related_code`, `get_recent_project_state`

### Requirement: DB connection is long-lived with reconnect-on-error guard
The MCP server SHALL establish a single psycopg2 database connection at startup and reuse it across tool calls. If the connection is lost (`psycopg2.OperationalError`), the server SHALL attempt to reconnect before processing the next tool call. `MindStateService` SHALL be re-instantiated after reconnect.

#### Scenario: Successful startup connects to DB
- **WHEN** `mstate-mcp` starts with valid `PG*` environment variables
- **THEN** a DB connection is established and `ensure_memory_schema` runs before the first tool call is accepted

#### Scenario: Reconnect after connection loss
- **WHEN** a tool call arrives after the DB connection has been lost
- **THEN** the server reconnects, re-instantiates `MindStateService`, and processes the tool call normally

#### Scenario: Unrecoverable DB failure returns MCP error
- **WHEN** reconnection fails (DB is not reachable)
- **THEN** the tool call returns a structured MCP error response; the server does not crash

### Requirement: Each MCP tool call is logged with structured observability data
Every tool call SHALL produce a structured log entry containing: `tool` (name), `agent` (value of `source_agent` param or `"unknown"`), `success` (bool), `duration_ms` (int), and `side_effects` (dict, e.g. `{"contextualization_job_id": "..."}` when applicable). Logging SHALL use the existing `logging_utils` module.

#### Scenario: Successful tool call logged
- **WHEN** a `remember` tool call completes successfully
- **THEN** a log entry is written with `tool="remember"`, `success=True`, `duration_ms` set to elapsed time, and `side_effects` including `memory_id`

#### Scenario: Failed tool call logged
- **WHEN** a tool call raises an exception
- **THEN** a log entry is written with `success=False` and the error message; an MCP error response is returned

### Requirement: `MS_MCP_ENABLED_TOOLS` controls which tools are registered
`get_settings()` SHALL read `MS_MCP_ENABLED_TOOLS` as a comma-separated list of tool names. When set, only the listed tools SHALL be registered with the MCP server. When unset, all tools are registered. This allows deployers to restrict the tool surface without code changes.

#### Scenario: All tools enabled by default
- **WHEN** `MS_MCP_ENABLED_TOOLS` is not set
- **THEN** all 7 tools are registered at server startup

#### Scenario: Restricted tool list
- **WHEN** `MS_MCP_ENABLED_TOOLS=remember,recall,build_context` is set
- **THEN** only those 3 tools are registered; `tools/list` returns only them