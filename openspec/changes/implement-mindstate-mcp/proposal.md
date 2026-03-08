## Why

MindState has a working HTTP API and REPL but no way for external coding agents (Claude Code, Copilot, Codex) to use it as a shared cognitive substrate. Adding an MCP server as an internal module — one application, multiple interfaces — makes MindState directly agent-usable without requiring users to install and operate a second independent system.

## What Changes

- New `mindstate/mcp/` internal module implementing an MCP server using the Python MCP SDK
- New `mstate mcp` entry point (stdio transport) — the primary deployment shape for agent integration
- New `MCPSettings` in `config.py` for transport mode, host/port, enabled tools, and workspace defaults
- New compound service method `log_work_session()` on `MindStateService` — stores a work session item + child `decision` and `resolved_blocker` items (auto-contextualized by kind policy)
- New service methods `find_related_code()` and `get_recent_project_state()` on `MindStateService`
- MCP tool surface: `remember`, `recall`, `build_context`, `contextualize`, `log_work_session`, `find_related_code`, `get_recent_project_state`
- MCP observability: tool name, agent identity, success/failure, duration, and projection side-effects logged per call
- `mcp` Python SDK added to `pyproject.toml` dependencies

## Capabilities

### New Capabilities

- `mcp-server`: The MCP server module — transport binding (stdio default), tool registration, startup/shutdown lifecycle, agent identity propagation, per-call observability logging. Covers the `mstate mcp` entry point and the `mindstate/mcp/` package structure.
- `mcp-tool-surface`: The seven MCP tool definitions and their input/output schemas: `remember`, `recall`, `build_context`, `contextualize`, `log_work_session`, `find_related_code`, `get_recent_project_state`. All tools delegate to `MindStateService` — no duplicated business logic.
- `log-work-session`: Compound service operation on `MindStateService`. Accepts structured session fields (repo, branch, task, summary, decisions, blockers, files_changed, next_steps, source_agent). Stores session as `work_session` kind; stores each decision as a child `decision` item and each resolved blocker as `resolved_blocker` — both auto-contextualized by the kind policy from Feature 3.

### Modified Capabilities

- `configuration`: New `MCPSettings` dataclass and `MS_MCP_*` environment variables (transport, host, port, enabled tools list, workspace default).

## Impact

- **New package**: `mindstate/mcp/__init__.py`, `mindstate/mcp/server.py`, `mindstate/mcp/tools.py`
- **New entry point**: `mstate-mcp = "mindstate.mcp:run"` in `pyproject.toml`
- **New dependency**: `mcp` (Python MCP SDK) in `pyproject.toml`
- **Modified**: `mindstate/memory_service.py` — three new methods (`log_work_session`, `find_related_code`, `get_recent_project_state`)
- **Modified**: `mindstate/config.py` — new `MCPSettings` dataclass and wiring in `get_settings()`
- **No DB schema changes**: all required tables and columns are already in place from Features 2 and 3
- **Same-core guarantee**: MCP tools share `MindStateService` with the HTTP API; no MCP-only business logic
- **No REPL changes**: `mstate mcp` is a separate process/entry point, not a REPL command
