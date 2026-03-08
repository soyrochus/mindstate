## Context

MindState has a working HTTP API (`mstate-api`), CLI REPL (`mstate`), and TUI. The service layer (`MindStateService`) is the established abstraction boundary — all interface adapters call it rather than the DB layer directly. This is the same-core guarantee that Feature 4 must preserve.

The MCP Python SDK (`mcp`) provides a server runtime that handles protocol framing, tool registration, and transport negotiation. Agents (Claude Code, Copilot, Codex) connect to MCP servers via stdio, treating each tool as a typed function call. The SDK abstracts the wire protocol entirely.

`MindStateService` is constructed with a live psycopg2 `conn`/`cur` pair. The MCP server process is long-lived (unlike the HTTP API which creates a service instance per request). This difference drives the DB connection strategy decision below.

## Goals / Non-Goals

**Goals:**
- Expose MindState memory capabilities to external agents via MCP, using `mstate-mcp` (stdio) as the primary entry point
- Implement 7 tools covering the cognitive tool surface: `remember`, `recall`, `build_context`, `contextualize`, `log_work_session`, `find_related_code`, `get_recent_project_state`
- Add `log_work_session()` to `MindStateService` as a compound service method
- Add `MCPSettings` to `config.py` for transport and tool configuration
- Log each MCP tool call with name, agent identity, success/failure, duration, and side effects
- Share the same service layer as the HTTP API — no MCP-only business logic

**Non-Goals:**
- HTTP SSE or WebSocket MCP transport — stdio is sufficient and is what agents use
- Multi-tenant or per-agent workspace isolation (deferred; use `source` field as workspace proxy for now)
- Per-tool authentication or authorization (deferred)
- Full agent instruction files/wrappers for each coding assistant (deferred to a follow-up)
- `topic_digest` and `decision_history` tools (named in feature doc as optional; deferred to keep scope bounded)

## Decisions

### Decision 1: Separate `mstate-mcp` entry point, not a subcommand of `mstate`

The MCP server runs as `mstate-mcp` (a new entry point in `pyproject.toml`) rather than `mstate mcp` (a subcommand).

Rationale: the existing `mstate` CLI parses positional `files` arguments and has complex initialization (TUI, API mode, LLM, REPL). Adding a `mcp` subcommand would require restructuring the arg parser and conditional initialization paths, adding fragility. A dedicated entry point is cleaner, independently configurable, and matches the existing `mstate-api` pattern exactly.

Alternatives considered:
- `mstate mcp` subcommand: rejected — too much coupling with existing CLI init flow
- Single unified `mstate serve` that starts all interfaces: overkill; the user can run both separately

### Decision 2: Single long-lived DB connection with reconnect-on-error

The MCP server holds one psycopg2 connection for the process lifetime. If the connection drops, it reconnects before the next tool call. No connection pool.

Rationale: stdio MCP transport is serial — one tool call completes before the next begins. There is no concurrent call problem. A single connection matches the REPL model and avoids the overhead of pooling.

The connection is initialized at server startup (same as REPL) and wrapped in a thin `_ensure_connected()` guard that reconnects on `psycopg2.OperationalError`.

Alternatives considered:
- Connection per tool call: correct but adds ~10ms overhead per call for a local DB; unnecessary for serial stdio transport
- `psycopg2.pool.SimpleConnectionPool`: adds complexity for no benefit in a serial single-process server

### Decision 3: `mindstate/mcp/` package with three files

```
mindstate/mcp/
    __init__.py      # run() entry point
    server.py        # MCP server setup, tool registration, startup
    tools.py         # Tool handler functions (thin adapters over MindStateService)
```

`tools.py` contains only input validation, service delegation, and output serialization. No business logic. `server.py` owns the MCP server instance, observability middleware, and connection lifecycle.

Alternatives considered:
- Single `mindstate/mcp.py`: acceptable for now but harder to navigate as tools expand
- Deeper package (`mindstate/mcp/tools/remember.py` etc.): premature for 7 tools

### Decision 4: `log_work_session()` on `MindStateService`

`log_work_session` is implemented as a service method rather than MCP-layer logic. It:
1. Stores the session as a `work_session` memory item (kind not in `AUTO_CONTEXTUALIZE_KINDS` — no auto-contextualization)
2. For each entry in `decisions`: calls `remember()` with `kind="decision"` (auto-contextualized by kind policy)
3. For each entry in `resolved_blockers`: calls `remember()` with `kind="resolved_blocker"` (auto-contextualized)
4. Returns `{session_memory_id, decision_memory_ids, resolved_blocker_memory_ids}`

This is purely a composition of existing `remember()` calls — no new DB logic.

Rationale: `log_work_session` will eventually be callable from the HTTP API too. Implementing it in the service layer makes that trivial.

### Decision 5: `find_related_code` and `get_recent_project_state` as service-layer compositions

Both tools compose existing `MindStateService` methods:

`find_related_code(repo, symbol, branch=None)`:
- `recall(query=symbol, source=repo, limit=10)` for semantic matches
- `get_recent_decisions(limit=5)` for decisions scoped to `source=repo`
- Returns merged result set

`get_recent_project_state(repo)`:
- `recall(query="recent project state summary decisions blockers", source=repo, limit=10)`
- `get_recent_decisions(limit=10)` filtered by source
- Returns structured dict with `summaries`, `decisions`, `open_threads` (items with kind `blocker` and no corresponding `resolved_blocker`)

No new DB queries are required. These can be on `MindStateService` for HTTP API reuse, or as pure MCP tool functions if only needed for MCP. They go on `MindStateService` for consistency.

### Decision 6: Agent identity via explicit `source_agent` tool parameter

MCP does not carry caller identity in the protocol. Tools that write memory (`remember`, `log_work_session`) accept an optional `source_agent: str` field that maps to `RememberInput.author`. This allows the agent to self-identify.

Observability logging always captures `source_agent` if provided; if absent, logs `"unknown"`.

### Decision 7: Observability via structured log lines per tool call

Each tool call is wrapped in a timing + logging decorator in `server.py`:

```python
logger.info("mcp_tool_call", extra={
    "tool": tool_name,
    "agent": source_agent or "unknown",
    "duration_ms": elapsed,
    "success": True/False,
    "side_effects": {...}  # e.g., {"contextualization_job_id": "..."}
})
```

Uses the existing `logging_utils` module. No new logging infrastructure.

## Risks / Trade-offs

**[Risk] Long-lived DB connection drops during a tool call** → Mitigation: `_ensure_connected()` guard reconnects on `OperationalError`; MindStateService is re-instantiated after reconnect so `ensure_memory_schema` re-runs (idempotent). Tool call fails gracefully with a structured MCP error response.

**[Risk] `log_work_session` calls `remember()` multiple times in one tool invocation, increasing latency** → Mitigation: each child item (decision, resolved_blocker) enqueues background contextualization — no added synchronous latency per item. 3–10 child items at ~5ms per `remember()` DB write = acceptable total latency.

**[Risk] `find_related_code` and `get_recent_project_state` depend on `source` field matching repo paths exactly** → Mitigation: these tools accept `repo` as a freeform string; they pass it as `source` filter to `recall()`. Matches depend on how callers have been storing memories. Document this dependency clearly in tool descriptions so agents know to set `source` consistently.

**[Risk] stdio transport serializes all tool calls; slow `log_work_session` blocks the MCP connection** → Mitigation: child `remember()` calls are fast (no LLM on Tier 1 write path). Background contextualization runs in daemon threads and does not block the tool response.

**[Risk] `mcp` SDK version compatibility** → Mitigation: pin `mcp>=1.0.0` in pyproject.toml. The SDK is stable; tool registration API has not changed across minor versions.

## Migration Plan

1. Add `mcp>=1.0.0` to `pyproject.toml` dependencies
2. Add `mstate-mcp = "mindstate.mcp:run"` to `[project.scripts]`
3. Implement `mindstate/mcp/` package (no existing code modified)
4. Add `log_work_session()`, `find_related_code()`, `get_recent_project_state()` to `MindStateService` (additive)
5. Add `MCPSettings` to `config.py` (additive — new field on `Settings`)
6. Run `uv pip install -e .` to register the new entry point
7. No DB migrations — all tables/columns already exist

Rollback: remove the `mindstate/mcp/` package and the entry point from `pyproject.toml`. No DB state is affected.

## Open Questions

- **`MS_MCP_ENABLED_TOOLS`**: should the tools list be configurable per-deployment, or always expose all 7? Default to all enabled; the setting can filter at tool-registration time.
- **HTTP SSE transport**: the `mcp` SDK supports SSE. If a user wants to use a remote MCP server (not local stdio), we could expose `MS_MCP_TRANSPORT=sse` with host/port. Deferred but `MCPSettings` should reserve the field.
- **`work_session` auto-contextualization**: the feature doc says "the agent may call `contextualize` for it if the session was particularly significant." Should `log_work_session` accept a `contextualize_session: bool` param to opt in? Likely yes — add it.
