# Feature 3 — Implement the MindState MCP server as an internal application module

## Intent

MindState should provide an MCP server so that external coding agents and assistants can use MindState as their shared cognitive substrate. The MCP server should be implemented as a **distinct internal module/service boundary inside the MindState application**, not as a completely separate product the user must install and operate independently.

This matches the intended usage pattern already described in the agent-behavior discussion: MindState is the canonical substrate, exposed through a small cognitive tool surface, reinforced by instructions/wrappers/hooks as needed. 

## Problem statement

The application will only become genuinely useful across Codex, Copilot, Claude Code, and similar tools if it can expose a compact, stable, agent-usable memory tool surface.

The design problem is twofold:

* the MCP surface must be separate enough internally to remain clean, testable, and evolvable
* the deployment must remain unified enough that the user does not feel they are running unrelated applications

The correct model is: **one application, multiple interfaces**.

## Functional outcome

After this feature, a MindState user should be able to:

* run the main MindState application
* enable or configure an MCP interface from within that application
* let external agents connect to that MCP interface
* use MindState memory capabilities from those agents without manually wiring a second standalone system

The MCP server should be a first-class interface of MindState, analogous to the HTTP API and UI, but targeted at agent tooling.

## Internal architecture requirement

The MCP implementation should be developed as an internal module with its own adapter boundary.

In practical terms:

* it should have its own package/module
* it should depend on MindState application services, not on raw database access as its primary contract
* it should call behavior-oriented application services such as remember/recall/build_context rather than reimplementing business logic
* it should be startable from the main application runtime or distribution

This preserves clean boundaries while avoiding fragmented deployment.

## Functional scope

### 1. MCP transport integration

Implement an MCP server transport supported by the chosen runtime stack. Whether stdio, local socket, or HTTP-based MCP transport is used can be decided pragmatically, but the deployment story must remain simple.

The preferred operational model is that MindState can expose MCP from the same installation/package, even if under a dedicated subcommand or runtime mode.

For example, acceptable shapes include:

* `mstate mcp`
* `mstate serve --mcp`
* a unified app process exposing API/UI plus MCP
* a coordinated internal child process managed by the main app

What is not desirable is telling the user to install and maintain a second distinct product unrelated to MindState.

### 2. Tool surface

The MCP server should expose the compact cognitive toolset already identified in the agent-behavior discussion. At minimum:

* `remember`
* `recall`
* `build_context`

Recommended first-wave tools:

* `log_work_session`
* `find_related_code`
* `get_recent_project_state`
* `topic_digest`
* `decision_history`

These reflect the intended agent usage patterns described in the design conversation. 

### 3. Structured inputs and outputs

Tool calls must accept and return structured data, even if the visible prompt surface in agents is natural language.

This is critical. The design discussion is explicit that writes must be structured or retrieval quality will degrade. Work-session logging in particular should carry fields such as repository, branch, task, decisions, blockers, files changed, next steps, and source agent. 

Therefore, MCP tool contracts should be schema-driven and explicit.

### 4. Agent-context integration

The MCP server should be optimized for the three core interaction moments already identified:

* start-of-task hydration
* checkpoint save
* end-of-task session save

These are the highest-value workflows and should be directly supported by the tool definitions and examples. 

### 5. Same-core guarantee

The MCP server must call the same underlying application services as the HTTP API/UI. There should not be separate “MCP-only” memory logic.

For example:

* HTTP `POST /v1/memory/remember` and MCP `remember` should converge on the same service layer
* HTTP `POST /v1/context/build` and MCP `build_context` should converge on the same service layer

This is essential for correctness and long-term maintainability.

## Detailed tool definitions

### Tool: `remember`

Purpose: store a new memory item or structured observation.

Minimum input:

* text or content
* kind
* workspace/project scope
* optional metadata/tags
* optional source information
* optional author/agent identity

Output:

* stored memory identifier
* status
* any queued projection actions

### Tool: `recall`

Purpose: retrieve memory by semantic or scoped query.

Minimum input:

* query
* workspace/scope
* optional filters
* limit

Output:

* ranked results
* snippets
* provenance references
* optional related entities/topics

### Tool: `build_context`

Purpose: assemble a bounded context bundle for a task.

Minimum input:

* task
* workspace/project scope
* token/size budget
* optional recency preference
* optional focus entities/topics

Output:

* summary
* selected items
* related decisions/open issues
* provenance map

### Tool: `log_work_session`

Purpose: capture a structured coding/agent work session.

Minimum input:

* repo/project
* branch
* task
* summary
* decisions
* blockers
* files changed
* next steps
* source agent

Output:

* stored session item identifier
* status

### Tool: `find_related_code`

Purpose: retrieve memory relevant to a code symbol/module/path/task.

Minimum input:

* repo
* symbol/path/module/concept
* optional branch or workspace

Output:

* related memories
* related decisions
* known pitfalls
* linked files/modules if available

### Tool: `get_recent_project_state`

Purpose: return the latest project-level cognitive summary.

Minimum input:

* repo/project/workspace

Output:

* recent summaries
* open threads
* recent decisions
* unresolved blockers

## Operational requirements

### Single-installation principle

A user installing MindState should obtain MCP capability as part of MindState.

That can still be implemented internally as a separate process/module. The distinction is architectural, not product fragmentation.

### Configuration

MCP-related configuration should live under MindState configuration, not in a detached second config system.

Typical settings may include:

* MCP transport mode
* host/port or stdio mode
* enabled tools
* authentication/authorization if needed
* workspace scoping defaults

### Security and access scope

The MCP server must honor the same workspace, tenant, and visibility constraints as the API/UI. The technical design already makes clear that multi-tenancy and sensitivity boundaries matter and should not be retrofitted later. 

### Observability

MCP calls should be visible in application logs and metrics:

* tool name
* caller/agent identity where available
* success/failure
* duration
* projection side effects for writes

This is particularly important because MCP is part of the control plane for external agents.

## Non-goals

This feature does not require:

* per-agent instruction files for Codex/Copilot/Claude Code shipped in full
* wrapper scripts for every agent workflow
* guaranteed autonomous memory hygiene by external models
* all future advanced MCP tools

Those can follow later. The goal here is the internal MCP server and the initial cognitive tool surface.

## Acceptance criteria

1. MindState can expose an MCP server from the same application/distribution.
2. The MCP server is implemented as a dedicated internal module, not as duplicated business logic.
3. The MCP tool surface includes at least `remember`, `recall`, and `build_context`.
4. At least one structured write-oriented tool such as `log_work_session` is implemented.
5. MCP tool execution uses the same application service layer as the HTTP API/UI.
6. A connected agent can hydrate context, save a checkpoint/session, and retrieve project memory through MindState.
7. The user is not required to install or operate a conceptually separate second application to obtain MCP functionality.

## Technical notes

The agent-behavior document already states the correct overall architecture: MindState database → MindState service/API → MindState MCP server → instructions/skills/wrappers. This feature is the concrete implementation of that principle. 


# One practical warning

For Feature 2 and Feature 3, resist the temptation to bypass the new service layer and “just call the old Cypher/db code directly” from every interface. That would preserve the brownfield code, but it would also preserve the wrong abstraction boundary. The old low-level shell should remain available, but the new application behaviors must converge on a proper MindState service layer derived from the canonical model described in the design notes. 

If useful, I can turn these three specs into a numbered backlog format with fields like rationale, dependencies, risks, and test strategy.
