## ADDED Requirements

### Requirement: Startup banner uses MindState identity
The CLI SHALL print a startup banner that identifies the application as MindState, including the active graph name. The banner SHALL NOT reference "Cypher REPL" or "TriStore" as the product name.

#### Scenario: Banner on launch
- **WHEN** the user starts `mstate` without `--execute`
- **THEN** the first printed line identifies the application as MindState and shows the active graph name

### Requirement: REPL prompt is `mstate>`
The interactive prompt shown to the user in CLI REPL mode SHALL be `mstate>`. It SHALL NOT be `cypher>`.

#### Scenario: Prompt string
- **WHEN** the CLI REPL is waiting for user input
- **THEN** the prompt displayed is `mstate>`

### Requirement: Argparse description uses MindState identity
The `--help` output description SHALL identify the tool as MindState. It SHALL NOT describe it as "Cypher REPL for AGE/PostgreSQL" as the primary identity.

#### Scenario: Help text identity
- **WHEN** the user runs `mstate --help`
- **THEN** the description references MindState, not "Cypher REPL"

### Requirement: All existing CLI behaviors are preserved
The CLI SHALL retain all existing functional behaviors without regression:
- Direct Cypher execution (`\llm off` mode)
- LLM-assisted natural-language-to-Cypher mode (`\llm on`)
- File loading and execution (`mstate <files>`)
- Batch execution and exit (`--execute`)
- Verbose logging (`--verbose`)
- Custom system prompt (`--system-prompt`)
- TUI launch (`--tui`)
- Command history via prompt-toolkit
- `\q`, `\h`, `\log`, `\llm` REPL commands

#### Scenario: Direct Cypher mode
- **WHEN** the user runs `\llm off` then submits a Cypher query
- **THEN** the query is executed directly against the database and results are displayed

#### Scenario: LLM mode
- **WHEN** LLM mode is enabled and the user submits natural language
- **THEN** the LLM agent translates and executes the appropriate Cypher query

#### Scenario: File execution
- **WHEN** the user runs `mstate --execute myfile.cypher`
- **THEN** the file is executed and the process exits without opening a REPL

#### Scenario: Help command
- **WHEN** the user enters `\h` in the REPL
- **THEN** all available REPL commands are listed
