## ADDED Requirements

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
