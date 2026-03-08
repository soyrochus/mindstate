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
