## Purpose
Define TUI identity and behavioral guarantees for MindState.

## Requirements

### Requirement: TUI application title uses MindState identity
The Textual TUI application title and any visible header labels SHALL identify the application as MindState. The TUI SHALL NOT display "CypherRepl" or "TriStore" as the application name.

#### Scenario: TUI title bar
- **WHEN** the user launches `mstate --tui`
- **THEN** the TUI title or header identifies the application as MindState

### Requirement: TUI class is named `MindStateTUI`
The internal Textual `App` subclass SHALL be named `MindStateTUI`. The class name `CypherReplTUI` SHALL NOT exist in the codebase.

#### Scenario: Class name in source
- **WHEN** the `tui.py` module is inspected
- **THEN** the main App class is named `MindStateTUI`

### Requirement: All existing TUI behaviors are preserved
The TUI SHALL retain all existing functional behaviors without regression:
- Query input and submission
- Result display
- LLM mode toggle
- Logging toggle
- File pre-loading
- Keyboard bindings
- Status display (graph name, LLM state, log state)
- Unified slash-command handling shared with CLI (`\q`, `\h`, `\log`, `\llm`, `\contextualize`, `\mode`, `\remember`, `\recall`, `\context`, `\inspect`)

#### Scenario: TUI launches and accepts input
- **WHEN** the user runs `mstate --tui`
- **THEN** the TUI opens, displays a query input area, and accepts Cypher or natural language input

#### Scenario: LLM toggle in TUI
- **WHEN** the user toggles LLM mode in the TUI
- **THEN** subsequent queries are processed according to the new mode (direct Cypher or LLM-assisted)

#### Scenario: TUI with preloaded files
- **WHEN** the user runs `mstate --tui myfile.cypher`
- **THEN** the file is executed before the TUI opens and results are visible in the output panel

### Requirement: TUI and CLI use a shared slash-command parser
The TUI SHALL use the same command parser/help metadata as the CLI REPL so command syntax and usage messages remain consistent across both interfaces.

#### Scenario: Shared parse behavior
- **WHEN** a slash command is entered in both TUI and CLI
- **THEN** the command is parsed using the same shared module and identical usage guidance is produced for invalid syntax
