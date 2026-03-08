## Purpose
Define runtime configuration defaults and environment compatibility for MindState.

## Requirements

### Requirement: History file default is `~/.mstate_history`
The default REPL history file path SHALL be `~/.mstate_history`. The old default `~/.cypher_repl_history` SHALL NOT be used.

#### Scenario: History file path in config
- **WHEN** `get_settings()` is called without any override
- **THEN** `settings.history_file` resolves to `~/.mstate_history` (expanded)

#### Scenario: History persists across sessions
- **WHEN** the user runs `mstate`, enters queries, and exits, then starts `mstate` again
- **THEN** previously entered queries are available in history via the up-arrow key

### Requirement: `AGE_GRAPH` default is `"mindstate"`
The default graph name SHALL be `"mindstate"`. The old default `"demo"` SHALL NOT be used.

#### Scenario: Default graph name
- **WHEN** `get_settings()` is called and `AGE_GRAPH` is not set in the environment
- **THEN** `settings.graph_name` is `"mindstate"`

#### Scenario: Environment override still works
- **WHEN** `AGE_GRAPH=mygraph` is set in the environment
- **THEN** `settings.graph_name` is `"mygraph"`

### Requirement: Default system prompt uses MindState identity
The `DEFAULT_SYSTEM_PROMPT` constant SHALL describe the assistant as a MindState agent operating on an AGE/PostgreSQL graph database. It SHALL NOT refer to itself as a "Cypher agent" as the primary identity.

#### Scenario: System prompt identity
- **WHEN** no custom `--system-prompt` is provided
- **THEN** the LLM receives a system prompt that identifies the context as MindState

### Requirement: Standard ecosystem variables are unchanged
The following environment variables SHALL remain as-is with no renaming: `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `AGE_GRAPH`, `LLM_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL_NAME`, `OPENAI_TEMPERATURE`, `AZURE_OPENAI_*`.

#### Scenario: Existing .env files continue to work
- **WHEN** a user has an existing `.env` file using standard PG and LLM variable names
- **THEN** the application reads them correctly without any changes to the `.env` file

### Requirement: `example.env` reflects MindState identity in comments
The `example.env` file comments and documentation language SHALL reference MindState where product identity is described. Technical variable names and values SHALL remain unchanged.

#### Scenario: example.env comment language
- **WHEN** `example.env` is opened
- **THEN** any product-identity comments reference MindState, not TriStore or CypherREPL

### Requirement: `MS_AUTO_CONTEXTUALIZE_KINDS` configures kind-based auto-contextualization
`get_settings()` SHALL read `MS_AUTO_CONTEXTUALIZE_KINDS` as a comma-separated list of memory kinds. The default value SHALL be `decision,architecture_note,resolved_blocker,task,observation,claim`. The setting SHALL be accessible on the `Settings` object and used by `MindStateService` to determine automatic job enqueuing.

#### Scenario: Default auto-kinds when unset
- **WHEN** `MS_AUTO_CONTEXTUALIZE_KINDS` is not set in the environment
- **THEN** `settings.contextualization.auto_kinds` equals `{"decision", "architecture_note", "resolved_blocker", "task", "observation", "claim"}`

#### Scenario: Custom kinds override defaults
- **WHEN** `MS_AUTO_CONTEXTUALIZE_KINDS=note,summary` is set
- **THEN** `settings.contextualization.auto_kinds` equals `{"note", "summary"}` and the defaults are not included

### Requirement: `MS_CONTEXTUALIZE_ENABLED` is a master switch
`get_settings()` SHALL read `MS_CONTEXTUALIZE_ENABLED` as a boolean (values `true`/`false`, case-insensitive). Default is `true`. When `false`, no contextualization jobs SHALL be created by any code path.

#### Scenario: Enabled by default
- **WHEN** `MS_CONTEXTUALIZE_ENABLED` is not set
- **THEN** `settings.contextualization.enabled` is `True`

#### Scenario: Disabled via environment variable
- **WHEN** `MS_CONTEXTUALIZE_ENABLED=false` is set
- **THEN** `settings.contextualization.enabled` is `False`

### Requirement: `MS_CONTEXTUALIZE_CONFIDENCE_THRESHOLD` sets entity inclusion cutoff
`get_settings()` SHALL read `MS_CONTEXTUALIZE_CONFIDENCE_THRESHOLD` as a float. Default is `0.85`. Entities with LLM-assigned confidence below this value SHALL be excluded from resolution and graph writes.

#### Scenario: Default confidence threshold
- **WHEN** `MS_CONTEXTUALIZE_CONFIDENCE_THRESHOLD` is not set
- **THEN** `settings.contextualization.confidence_threshold` is `0.85`

#### Scenario: Override confidence threshold
- **WHEN** `MS_CONTEXTUALIZE_CONFIDENCE_THRESHOLD=0.7` is set
- **THEN** `settings.contextualization.confidence_threshold` is `0.7`

### Requirement: `MS_CONTEXTUALIZE_MERGE_THRESHOLD` sets embedding similarity cutoff for entity resolution
`get_settings()` SHALL read `MS_CONTEXTUALIZE_MERGE_THRESHOLD` as a float. Default is `0.92`. Entity resolution step 2 (embedding similarity) SHALL only auto-merge when cosine similarity exceeds this value.

#### Scenario: Default merge threshold
- **WHEN** `MS_CONTEXTUALIZE_MERGE_THRESHOLD` is not set
- **THEN** `settings.contextualization.merge_threshold` is `0.92`

### Requirement: `MS_CONTEXTUALIZE_MAX_ENTITIES_PER_ITEM` caps LLM entity extraction
`get_settings()` SHALL read `MS_CONTEXTUALIZE_MAX_ENTITIES_PER_ITEM` as an integer. Default is `12`. The entity recognition stage SHALL retain at most this many entities per item, selecting by descending confidence.

#### Scenario: Default entity cap
- **WHEN** `MS_CONTEXTUALIZE_MAX_ENTITIES_PER_ITEM` is not set
- **THEN** `settings.contextualization.max_entities_per_item` is `12`

### Requirement: `MCPSettings` dataclass configures the MCP server
`get_settings()` SHALL read MCP-related environment variables into an `MCPSettings` dataclass with fields: `transport` (str), `host` (str), `port` (int), `enabled_tools` (Optional[Set[str]]). `MCPSettings` SHALL be added as a `mcp: MCPSettings` field on the `Settings` dataclass.

#### Scenario: MCPSettings present on Settings
- **WHEN** `get_settings()` is called
- **THEN** `settings.mcp` is an `MCPSettings` instance

### Requirement: `MS_MCP_TRANSPORT` sets the MCP server transport mode
`get_settings()` SHALL read `MS_MCP_TRANSPORT`. Default is `"stdio"`. Valid values are `"stdio"` and `"sse"`. The MCP server uses this value to select the transport binding at startup.

#### Scenario: Default transport is stdio
- **WHEN** `MS_MCP_TRANSPORT` is not set
- **THEN** `settings.mcp.transport` is `"stdio"`

#### Scenario: SSE transport configured
- **WHEN** `MS_MCP_TRANSPORT=sse` is set
- **THEN** `settings.mcp.transport` is `"sse"`

### Requirement: `MS_MCP_HOST` and `MS_MCP_PORT` configure SSE transport binding
`get_settings()` SHALL read `MS_MCP_HOST` (default `"127.0.0.1"`) and `MS_MCP_PORT` (default `8001`) for use when `transport="sse"`. These values are ignored when transport is `"stdio"`.

#### Scenario: Default SSE binding
- **WHEN** `MS_MCP_HOST` and `MS_MCP_PORT` are not set
- **THEN** `settings.mcp.host` is `"127.0.0.1"` and `settings.mcp.port` is `8001`

#### Scenario: Custom SSE binding
- **WHEN** `MS_MCP_HOST=0.0.0.0` and `MS_MCP_PORT=9000` are set
- **THEN** `settings.mcp.host` is `"0.0.0.0"` and `settings.mcp.port` is `9000`

### Requirement: `MS_MCP_ENABLED_TOOLS` restricts the registered tool set
`get_settings()` SHALL read `MS_MCP_ENABLED_TOOLS` as a comma-separated list of tool names. When set, `settings.mcp.enabled_tools` is a `frozenset` of those names. When not set, `settings.mcp.enabled_tools` is `None` (meaning all tools are enabled).

#### Scenario: All tools enabled when unset
- **WHEN** `MS_MCP_ENABLED_TOOLS` is not set
- **THEN** `settings.mcp.enabled_tools` is `None`

#### Scenario: Restricted tool set
- **WHEN** `MS_MCP_ENABLED_TOOLS=remember,recall` is set
- **THEN** `settings.mcp.enabled_tools` is `frozenset({"remember", "recall"})`
