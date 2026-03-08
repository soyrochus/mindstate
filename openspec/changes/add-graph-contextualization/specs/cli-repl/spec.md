## ADDED Requirements

### Requirement: `\contextualize` REPL command is available
The CLI REPL SHALL support a `\contextualize` command with two forms:
- `\contextualize [n]` — contextualizes the n most recent non-contextualized items (default n=1)
- `\contextualize --id <UUID>` — contextualizes a specific item by memory_id

The command SHALL enqueue a background job and print the job reference immediately, without waiting for completion.

#### Scenario: Contextualize most recent item
- **WHEN** the user enters `\contextualize` in the REPL
- **THEN** a job is enqueued for the 1 most recent non-contextualized item and a confirmation line is printed showing the job_id and queued_count

#### Scenario: Contextualize n items
- **WHEN** the user enters `\contextualize 5` in the REPL
- **THEN** a job is enqueued for up to 5 non-contextualized items and the confirmation is printed

#### Scenario: Contextualize by ID
- **WHEN** the user enters `\contextualize --id <UUID>` in the REPL
- **THEN** a job is enqueued for that specific memory item and the confirmation is printed

#### Scenario: No eligible items
- **WHEN** the user enters `\contextualize` and no non-contextualized items exist
- **THEN** the REPL prints a message indicating zero items were queued; no error is raised

## MODIFIED Requirements

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
- `\q`, `\h`, `\log`, `\llm`, `\contextualize` REPL commands

#### Scenario: Direct Cypher mode
- **WHEN** the user runs `\llm off` then submits a Cypher query
- **THEN** the query is executed directly against the database and results are displayed

#### Scenario: LLM mode
- **WHEN** LLM mode is enabled and the user submits natural language
- **THEN** the LLM agent translates and executes the appropriate Cypher query

#### Scenario: File execution
- **WHEN** the user runs `mstate --execute myfile.cypher`
- **THEN** the file is executed and the process exits without opening a REPL

#### Scenario: Help command lists contextualize
- **WHEN** the user enters `\h` in the REPL
- **THEN** `\contextualize` is listed among the available REPL commands
