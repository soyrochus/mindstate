# TriStore — Technical Architecture

## Table of Contents

1. [Overview](#1-overview)
2. [Repository Layout](#2-repository-layout)
3. [Infrastructure Layer — The TriStore Database](#3-infrastructure-layer--the-tristore-database)
   - 3.1 [Docker Image](#31-docker-image)
   - 3.2 [Initialization](#32-initialization)
   - 3.3 [Three Storage Modalities](#33-three-storage-modalities)
4. [Python Package — `cypherrepl`](#4-python-package--cypherrepl)
   - 4.1 [Entry Points](#41-entry-points)
   - 4.2 [Module Map](#42-module-map)
5. [Configuration Subsystem (`config.py`)](#5-configuration-subsystem-configpy)
   - 5.1 [Settings Dataclasses](#51-settings-dataclasses)
   - 5.2 [Environment Variables Reference](#52-environment-variables-reference)
   - 5.3 [Default System Prompt](#53-default-system-prompt)
6. [Database Layer (`db.py`)](#6-database-layer-dbpy)
   - 6.1 [Connection](#61-connection)
   - 6.2 [AGE Initialization Sequence](#62-age-initialization-sequence)
   - 6.3 [Cypher Execution Pipeline](#63-cypher-execution-pipeline)
   - 6.4 [Result Formatting](#64-result-formatting)
   - 6.5 [File Execution](#65-file-execution)
7. [Cypher Processing (`cypher.py`)](#7-cypher-processing-cypherpy)
   - 7.1 [Pre-processing](#71-pre-processing)
   - 7.2 [Statement Splitting](#72-statement-splitting)
   - 7.3 [Return-Clause Parser and Column Inference](#73-return-clause-parser-and-column-inference)
   - 7.4 [LLM Query Sanitization](#74-llm-query-sanitization)
8. [LLM Integration Layer (`llm.py`)](#8-llm-integration-layer-llmpy)
   - 8.1 [LLM Factory (`create_llm`)](#81-llm-factory-create_llm)
   - 8.2 [The `send_cypher` Tool](#82-the-send_cypher-tool)
   - 8.3 [Agent Executor Construction](#83-agent-executor-construction)
   - 8.4 [Conversation History](#84-conversation-history)
9. [Logging Subsystem (`logging_utils.py`)](#9-logging-subsystem-logging_utilspy)
   - 9.1 [Standard Logging Setup](#91-standard-logging-setup)
   - 9.2 [`VerboseCallback` — LangChain Callback Handler](#92-verbosecallback--langchain-callback-handler)
   - 9.3 [`log_print` and the Log Sink](#93-log_print-and-the-log-sink)
10. [CLI Interface (`cli.py`)](#10-cli-interface-clipy)
    - 10.1 [Argument Parsing](#101-argument-parsing)
    - 10.2 [Startup Sequence](#102-startup-sequence)
    - 10.3 [REPL Loop](#103-repl-loop)
    - 10.4 [Command Dispatch](#104-command-dispatch)
11. [TUI Interface (`tui.py`)](#11-tui-interface-tuipy)
    - 11.1 [Architecture of `CypherReplTUI`](#111-architecture-of-cypherrepltui)
    - 11.2 [Layout and Widgets](#112-layout-and-widgets)
    - 11.3 [Input Handling](#113-input-handling)
    - 11.4 [Command History](#114-command-history)
    - 11.5 [Async Execution Model](#115-async-execution-model)
    - 11.6 [Textual Version Compatibility](#116-textual-version-compatibility)
    - 11.7 [Verbose / Log Mode in TUI](#117-verbose--log-mode-in-tui)
12. [Legacy Monolith (`cypher_llm_repl.py`)](#12-legacy-monolith-cypher_llm_replpy)
13. [Data Flow Diagrams](#13-data-flow-diagrams)
    - 13.1 [LLM Mode Query Flow](#131-llm-mode-query-flow)
    - 13.2 [Direct Cypher Mode Flow](#132-direct-cypher-mode-flow)
14. [Dependency Stack](#14-dependency-stack)
15. [Key Design Decisions and Patterns](#15-key-design-decisions-and-patterns)

---

## 1. Overview

TriStore is a tool for natural-language and direct Cypher exploration of a PostgreSQL database that exposes three storage modalities at once:

| Modality | Technology | Purpose |
|----------|-----------|---------|
| **Relational** | PostgreSQL 16 | Tables, SQL queries, standard RDBMS |
| **Graph** | Apache AGE (openCypher) | Property graph nodes, edges, paths |
| **Vectors** | pgvector | Embedding storage & similarity search |

The REPL front-end sits on top of this "TriStore" and exposes two query modes:

- **LLM Mode** — the user types natural language; an LLM agent translates it into Cypher and executes it via a bound tool.
- **Direct Mode** — the user types Cypher directly, bypassing the LLM entirely.

Two front-ends share the same back-end logic:

- A **standard terminal REPL** built on `prompt_toolkit`.
- A **full-screen TUI** built on the `textual` library (`-t` / `--tui` flag).

---

## 2. Repository Layout

```
tristore/
├── cypher_llm_repl.py        # Legacy monolith (single-file version of the REPL)
├── cypher_repl.py            # (Unused / earlier prototype)
│
├── cypherrepl/               # Primary refactored package
│   ├── __init__.py           # Version declaration (0.1.0), public API
│   ├── __main__.py           # `python -m cypherrepl` entry point
│   ├── cli.py                # Standard terminal REPL (prompt_toolkit)
│   ├── tui.py                # Textual TUI REPL
│   ├── config.py             # Settings dataclasses + env-var loading
│   ├── db.py                 # Database connection & Cypher execution
│   ├── cypher.py             # Cypher parsing/sanitisation utilities
│   ├── llm.py                # LangChain LLM factory + agent construction
│   └── logging_utils.py      # Logging setup, VerboseCallback, log sink
│
├── Dockerfile                # Builds Postgres 16 + AGE + pgvector image
├── init-tristore.sql         # SQL run at container init (enables extensions)
├── init_graph.cypher         # Optional starter graph data
├── init_graph.sql            # SQL variant of starter graph
├── example.env               # Template environment file
├── pyproject.toml            # Project metadata + dependencies (PEP 517)
├── uv.lock                   # Locked dependency versions (uv)
├── run.sh                    # Convenience launcher shell script
│
├── REPL-MANUAL.md            # End-user manual
├── AGENTS.md                 # Agent / TUI specification notes
└── docs/                     # Future-version specs (ignored here)
```

---

## 3. Infrastructure Layer — The TriStore Database

### 3.1 Docker Image

`Dockerfile` starts from `postgres:16` and compiles and installs two extensions from source:

```
postgres:16 (base)
  └─ pgvector v0.8.0  (cloned from github.com/pgvector/pgvector)
  └─ Apache AGE PG16  (cloned from github.com/apache/age, branch PG16)
```

Both are compiled via `make && make install` against the PostgreSQL 16 development headers. Build tools (`build-essential`, `git`, `postgresql-server-dev-16`, `flex`, `bison`) are installed and the build directories cleaned up to minimize final image size.

The initialization SQL script is placed in `/docker-entrypoint-initdb.d/` so PostgreSQL's entrypoint runs it automatically on first start.

### 3.2 Initialization

[init-tristore.sql](init-tristore.sql) runs once when the container is first created:

```sql
CREATE EXTENSION IF NOT EXISTS vector;      -- pgvector
CREATE EXTENSION IF NOT EXISTS age;         -- Apache AGE
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
SELECT * FROM create_graph('my_graph');     -- creates default graph
```

At REPL startup, the same sequence (minus the `CREATE EXTENSION` calls) is repeated for the session via `Settings.init_statements()`, ensuring `ag_catalog` is on the search path and the configured graph exists.

### 3.3 Three Storage Modalities

**Graph (AGE)**
All graph data is accessed through the `cypher()` PostgreSQL function:

```sql
SELECT * FROM cypher('graph_name', $$ MATCH (n) RETURN n $$) AS (result agtype);
```

The `agtype` is a PostgreSQL type that represents nodes (`:vertex`), edges (`:edge`), and paths (`:path`) as JSON-like serializations.

**Vector (pgvector)**
Vector columns use the `vector(N)` type. Similarity search uses the `<->` (L2 distance) operator:

```sql
SELECT content FROM embeddings ORDER BY embedding <-> '[0.1,0.2,...]' LIMIT 1;
```

**Relational**
Standard PostgreSQL tables and SQL queries run unmodified alongside graph and vector operations.

---

## 4. Python Package — `cypherrepl`

### 4.1 Entry Points

| Entry point | How invoked | What it runs |
|-------------|-------------|--------------|
| `python cypher_llm_repl.py` | Direct script | Legacy monolith `main()` |
| `python -m cypherrepl` | Module | `cypherrepl.__main__._run()` → `cli.main()` |
| `python -m cypherrepl -t` | Module + flag | `cli.main()` → `tui.run_tui()` |

### 4.2 Module Map

```
cypherrepl/
│
├── config.py          ← Settings (pure data, no I/O side effects beyond load_dotenv)
│
├── cypher.py          ← Stateless string-processing functions (no DB, no LLM)
│
├── db.py              ← Stateful: holds cursor/connection references
│   depends on: config, cypher
│
├── llm.py             ← Stateful: LLM instances, agent executor
│   depends on: config, db, logging_utils
│
├── logging_utils.py   ← Stateless helpers + one module-level sink variable
│
├── cli.py             ← Orchestrator for standard REPL
│   depends on: config, db, llm, logging_utils
│
└── tui.py             ← Orchestrator for TUI REPL (lazy-imports textual)
    depends on: config, db, llm, logging_utils
```

---

## 5. Configuration Subsystem (`config.py`)

### 5.1 Settings Dataclasses

Three immutable frozen dataclasses form a hierarchy:

```
Settings
├── db: DBSettings
│   ├── host, port, dbname, user, password
│   └── as_psycopg_kwargs() → dict
│
├── llm: LLMSettings
│   ├── provider ("openai" | "azure_openai")
│   ├── openai_api_key, openai_model, openai_temperature
│   └── azure_api_key, azure_endpoint, azure_api_version, azure_deployment
│
├── graph_name          → AGE graph to query
├── default_cols        → "(result agtype)"  (fallback column def for AGE)
├── history_file        → "~/.cypher_repl_history"
├── default_system_prompt
└── init_statements()   → List[str]  (SQL to run at session start)
```

All instances are frozen (`@dataclass(frozen=True)`), ensuring settings are read-only after construction.

`get_settings()` is the factory that reads the environment and constructs the full `Settings` object. `load_dotenv()` is called at module-import time so `.env` values are available to all `os.environ.get()` calls throughout the module.

### 5.2 Environment Variables Reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `PGHOST` | `localhost` | PostgreSQL host |
| `PGPORT` | `5432` | PostgreSQL port |
| `PGDATABASE` | `postgres` | Database name |
| `PGUSER` | `postgres` | Database user |
| `PGPASSWORD` | _(empty)_ | Database password |
| `AGE_GRAPH` | `demo` | Apache AGE graph name |
| `LLM_PROVIDER` | `openai` | `openai` or `azure_openai` |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `OPENAI_MODEL_NAME` | `gpt-4.1` | OpenAI model identifier |
| `OPENAI_TEMPERATURE` | `0` | Sampling temperature |
| `AZURE_OPENAI_API_KEY` | — | Azure OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | — | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_API_VERSION` | `2024-12-01-preview` | Azure API version |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | `gpt-4o` | Azure deployment name |

### 5.3 Default System Prompt

The system prompt is embedded as `DEFAULT_SYSTEM_PROMPT` in `config.py`. It is intentionally tight and deterministic:

- It names the single available tool: `send_cypher(query)`.
- It specifies when to call the tool vs. when to answer in text.
- It mandates **pure Cypher only** — no SQL wrappers, no graph name, no trailing semicolons.
- It provides few-shot examples for both tool-call and text-only scenarios.

The prompt can be overridden at runtime via the `-s / --system-prompt` CLI flag, which reads a replacement prompt from a file.

---

## 6. Database Layer (`db.py`)

### 6.1 Connection

```python
conn = psycopg2.connect(**settings.db.as_psycopg_kwargs())
cur  = conn.cursor(cursor_factory=RealDictCursor)
```

`RealDictCursor` returns each row as an `OrderedDict` keyed by column name, which is essential for `format_rows` to produce tab-separated output with headers.

### 6.2 AGE Initialization Sequence

`init_age(cur, conn, settings)` iterates `settings.init_statements()` and executes each one, rolling back silently on any error (the `CREATE EXTENSION` and `create_graph` calls fail harmlessly if already present):

```sql
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
SELECT create_graph('<graph_name>');
```

### 6.3 Cypher Execution Pipeline

The primary execution path for a single statement:

```
input query string
        │
        ▼
preprocess_cypher_query()         strip + rstrip(";")
        │
        ▼
sanitize_llm_query_maybe_wrapped() extract inner Cypher if LLM emitted SQL wrapper
        │
        ▼
parse_return_clause()             infer column definitions from RETURN clause
        │
        ▼
BUILD SQL:
  SELECT * FROM cypher('<graph>', $$ <cypher> $$) AS <col_def>;
        │
        ▼
cur.execute(sql)
        │
   ┌────┴────┐
   │ success │  → fetchall() + commit() → (True, rows)
   └────┬────┘
        │ exception (e.g. col count mismatch)
        ▼
   if col_def != default_cols:
     rollback()
     retry with "(result agtype)"
        │
   ┌────┴────┐
   │ success │  → fetchall() + commit() → (True, rows)
   └────┬────┘
        │ still fails
        ▼
   rollback() → (False, "Cypher error: <first line>")
```

The two-attempt strategy handles cases where the RETURN clause inference produces wrong column counts. The fallback `(result agtype)` single-column form is always valid for AGE.

For multi-statement input, `execute_cypher_with_smart_columns` splits on semicolons and calls `execute_single_cypher_statement` in a loop, printing `--- Statement N ---` separators and short-circuiting on the first error.

### 6.4 Result Formatting

`format_rows(rows: Sequence[dict]) -> str`
Produces tab-separated output: first row is column headers, subsequent rows are values. `(no results)` is returned for empty result sets.

`print_result(rows)` is a thin wrapper that prints `format_rows` output to stdout.

### 6.5 File Execution

`load_and_execute_files(cur, conn, files, settings, logger)` reads each file, splits on semicolons (simple tokenization — no comment-stripping), and executes each statement through the standard pipeline.

---

## 7. Cypher Processing (`cypher.py`)

This module contains only pure, stateless string-processing functions. It has no imports from the rest of the package.

### 7.1 Pre-processing

```python
def preprocess_cypher_query(query: str) -> str:
    return query.strip().rstrip(";")
```

Apache AGE's `cypher()` function does not accept trailing semicolons; this strips them.

### 7.2 Statement Splitting

```python
def split_cypher_statements(query: str) -> List[str]:
    return [stmt.strip() for stmt in query.split(";") if stmt.strip()]
```

Splits on literal semicolons. This is intentionally simple — Cypher statements do not normally embed semicolons in string literals in practice.

### 7.3 Return-Clause Parser and Column Inference

`parse_return_clause(query, default_cols)` uses a regex to extract the RETURN clause:

```
\bRETURN\s+(.+?)(?:\s+(?:ORDER|LIMIT|SKIP|UNION)|$)
```

Rules:
- If no RETURN clause is found → use `default_cols` (`(result agtype)`).
- If RETURN has exactly one item → use `default_cols`.
- If RETURN has multiple comma-separated items → generate one `agtype` column per item, naming each column from its `AS <alias>` if present, otherwise from the first identifier token in the expression.

Example:
```
MATCH (n)-[r]->(m) RETURN n AS source, r AS rel, m AS target
→ (source agtype, rel agtype, target agtype)
```

### 7.4 LLM Query Sanitization

Despite explicit instructions, LLMs sometimes emit SQL wrappers instead of pure Cypher. `sanitize_llm_query_maybe_wrapped` handles two patterns:

| Pattern detected | Action |
|-----------------|--------|
| `SELECT * FROM cypher(...$$ ... $$) AS (...)` | Extracts inner Cypher from `$$...$$` |
| `cypher(...$$ ... $$)` | Extracts inner Cypher from `$$...$$` |
| Plain Cypher | Strips trailing semicolon only |

Two compiled regexes (`_SQL_WRAPPER_RE`, `_CYPHER_FN_RE`) are used, both with `IGNORECASE | DOTALL` to handle multiline LLM output.

---

## 8. LLM Integration Layer (`llm.py`)

### 8.1 LLM Factory (`create_llm`)

`create_llm(settings, callbacks=None)` returns a LangChain chat model instance based on `settings.llm.provider`:

| Provider | Class | Required vars |
|----------|-------|--------------|
| `openai` | `ChatOpenAI` | `OPENAI_API_KEY` |
| `azure_openai` | `AzureChatOpenAI` | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT` |

Temperature is applied uniformly. LangChain callbacks (for verbose logging) are passed through `common_kwargs`. Any unknown provider raises `ValueError` immediately — this is also called at startup (before the DB connection) to fail fast on misconfiguration.

### 8.2 The `send_cypher` Tool

`build_send_cypher_tool(cur, conn, settings, logger, is_logging_enabled)` returns a LangChain `@tool`-decorated function.

The closure captures the database cursor, connection, and settings. When called by the agent:

1. Optionally log the query via `log_print("TOOL", query)`.
2. Pass the query through `execute_cypher_with_smart_columns`.
3. On success: call `format_rows` and return the formatted string to the LLM.
4. On failure: return the error string to the LLM (so it can reason about the failure).

The tool's docstring is the LLM-facing description and includes: what queries it accepts, examples, and explicit guidance not to use it for conceptual questions.

### 8.3 Agent Executor Construction

`create_agent_executor(llm, tool, system_prompt)` assembles a standard LangChain ReAct-style tool-calling agent:

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder("chat_history"),   # conversation memory
    ("user", "{input}"),
    MessagesPlaceholder("agent_scratchpad"), # internal agent reasoning
])
agent = create_tool_calling_agent(llm, [tool], prompt)
return AgentExecutor(agent=agent, tools=[tool])
```

The agent supports multi-turn conversation: the calling code maintains `chat_history` as a list of `HumanMessage` / `AIMessage` objects that grows with each exchange.

### 8.4 Conversation History

Both CLI and TUI maintain a `chat_history` list that is passed on each `agent_executor.invoke()` call. This enables follow-up questions like "now delete them" after "show me all nodes" — the LLM has context of what was retrieved.

---

## 9. Logging Subsystem (`logging_utils.py`)

### 9.1 Standard Logging Setup

`setup_logging(verbose: bool)` configures the root Python logger:

- `verbose=True`: `DEBUG` level for the `cypherrepl` logger; noisy third-party loggers (`openai`, `httpx`, `urllib3`, `langchain`, `langchain_openai`) are suppressed to `WARNING` to avoid clutter.
- `verbose=False`: `WARNING` level globally.

### 9.2 `VerboseCallback` — LangChain Callback Handler

`VerboseCallback(BaseCallbackHandler)` hooks into LangChain's event system to log at `DEBUG` level:

| Hook | Logs |
|------|------|
| `on_llm_start` | First 1000 chars of each prompt |
| `on_llm_end` | First 1000 chars of generated text |
| `on_tool_start` | Tool name + first 1000 chars of input |
| `on_tool_end` | First 1000 chars of tool output |

This callback is created only when `--verbose` is passed.

### 9.3 `log_print` and the Log Sink

`log_print(prefix, text)` formats log lines as `[PREFIX] line` and routes them through a module-level `_log_sink`:

- `_log_sink = None` → output goes directly to `print()` (stdout).
- `_log_sink = callable` → each formatted line is passed to the callable instead.

`set_log_sink(sink)` / `set_log_sink(None)` allows the TUI to redirect log output into its on-screen log panel rather than stdout, and to restore the default on unmount.

---

## 10. CLI Interface (`cli.py`)

### 10.1 Argument Parsing

`argparse` handles the following flags:

| Flag | Type | Effect |
|------|------|--------|
| `files` | positional (nargs=*) | Cypher files to load before REPL |
| `-e` / `--execute` | bool | Execute files only, then exit |
| `-t` / `--tui` | bool | Launch TUI instead of standard REPL |
| `-s` / `--system-prompt` | path | Override default system prompt |
| `-v` / `--verbose` | bool | Enable debug logging |

### 10.2 Startup Sequence

```
parse args
    │
setup_logging(verbose)
    │
create_llm(settings)     ← fail-fast LLM config validation (before DB)
    │
connect_db(settings)     ← psycopg2 connect; OperationalError caught cleanly
    │
init_age(cur, conn, settings)
    │
load system_prompt (file or default)
    │
if --tui → run_tui(...)  ← and return
    │
load files (if any)
    │
if --execute → exit
    │
build_send_cypher_tool(...)
create_llm(settings, callbacks)
create_agent_executor(llm, tool, system_prompt)
    │
PromptSession(history=FileHistory(~/.cypher_repl_history), multiline=True)
    │
REPL loop
```

### 10.3 REPL Loop

`prompt_toolkit.PromptSession` drives the standard REPL with:

- **Multiline mode**: `Enter` inserts a newline; `Esc+Enter` submits.
- **Persistent history**: `FileHistory` persists to `~/.cypher_repl_history` across sessions.
- **Prompt string**: `cypher> `
- `KeyboardInterrupt` (Ctrl+C) prints a reminder and continues.
- `EOFError` (Ctrl+D) exits cleanly.

### 10.4 Command Dispatch

Input is checked against backslash commands before being dispatched to LLM or DB:

```
stripped input
    │
    ├── \q          → break loop
    ├── \h          → print help
    ├── \log on|off → toggle log_enabled flag
    ├── \llm on|off → toggle llm_enabled flag
    │
    ├── llm_enabled=True  → agent_executor.invoke({input, chat_history})
    │                        → print output / log_print("LLM", output)
    │                        → append HumanMessage + AIMessage to chat_history
    │
    └── llm_enabled=False → execute_cypher_with_smart_columns(cur, conn, text, ...)
                             → print_result / log_print("DB", formatted)
```

If the LLM agent was not initialized (configuration error), `agent_executor` is `None` and the user is told to use `\llm off`.

---

## 11. TUI Interface (`tui.py`)

### 11.1 Architecture of `CypherReplTUI`

`run_tui()` builds and runs a `textual.app.App` subclass (`CypherReplTUI`) inside a closure that captures `cur`, `conn`, `settings`, `system_prompt`, `verbose`, and `files`.

`textual` is imported lazily inside `run_tui()`. If `textual` is not installed, the function prints an error and returns cleanly — the dependency is effectively optional at import time (though it is listed in `pyproject.toml`).

### 11.2 Layout and Widgets

```
Screen (vertical layout)
├── Static ".title"           "CONVERSATION" header bar
│
├── Horizontal ".main"
│   ├── Vertical ".columns"
│   │   ├── Static ".panel-title"   "Conversation"
│   │   └── RichLog/Log ".pane"     chat_panel  ← unified conversation
│   │
│   └── Vertical "#logs_container"  (hidden unless \log on)
│       ├── Static ".panel-title"   "LOGS"
│       └── RichLog/Log ".pane"     logs_panel
│
├── SubmitTextArea ".input"   Multi-line text input
│
└── Container ".footer"
    ├── Static ".commands"    Key binding reference line
    └── Static ".status"      Status bar (live clock + state indicators)
```

#### Reactive State

Three `reactive` attributes drive auto-updating UI state:

| Reactive | Default | Effect |
|----------|---------|--------|
| `log_enabled` | `False` | Controls logs panel visibility |
| `llm_enabled` | `True` | Controls LLM vs direct Cypher dispatch |
| `connected` | `True` | Reflects DB connection state |
| `model_name` | `""` | Displayed in status bar |

#### Status Bar

A 1-second `Timer` calls `_update_status()` which renders:
```
Status: [Connected] | LLM: [ON/OFF] | Model: <name> | Log: [ON/OFF] | Time: HH:MM
```
Rich markup is used for color coding (green/red/yellow).

### 11.3 Input Handling

`SubmitTextArea` is a custom `TextArea` subclass that implements a two-key send protocol:

```
Key received       _armed_send state    Action
──────────────     ─────────────────    ──────
Escape             False → True         arm send (event stopped)
Enter (armed)      True → False         submit message (event stopped)
Enter (not armed)  False                normal newline (event propagates)
Shift+Enter        (any)                falls through to TextArea (newline)
Any other key      True → False         disarm
```

This matches the standard REPL's `Esc+Enter` submit behavior, preserving muscle memory.

App-level `BINDINGS`:
- `alt+up` → `action_history_prev()`
- `alt+down` → `action_history_next()`

### 11.4 Command History

The TUI maintains its own in-memory command history (independent of `prompt_toolkit`'s file-based history) as `self._history: List[str]` and `self._hist_pos: Optional[int]`.

Navigation:
- `Alt+Up`: move backwards through history.
- `Alt+Down`: move forwards; clears input when past the end.
- Consecutive duplicate entries are deduplicated.
- Positioning resets to `None` when a new message is sent.

### 11.5 Async Execution Model

`CypherReplTUI._send(message)` is an `async` coroutine:

- LLM calls use `asyncio.to_thread()` to run the synchronous `agent_executor.invoke()` in a thread pool, keeping the Textual event loop unblocked.
- Direct Cypher calls similarly use `asyncio.to_thread()` wrapping `execute_cypher_with_smart_columns`.
- The coroutine is dispatched from `SubmitTextArea.on_key` via `asyncio.create_task()`.

### 11.6 Textual Version Compatibility

The TUI handles API differences across Textual versions:

**Log widget**: Three widget types tried in order with `try/except TypeError`:
```python
from textual.widgets import RichLog   # preferred (highlight + markup)
from textual.widgets import Log        # fallback
from textual.widgets import TextLog    # older fallback
```

**Constructor kwargs**: Each widget is tried with progressively fewer kwargs:
```
{"highlight": True, "markup": True, "classes": ...}  → first try
{"highlight": True, "classes": ...}                   → second try
{"classes": ...}                                      → third try
{}                                                    → last resort
```

**Write method**: `_log_write(panel, line)` detects whether the widget is a `RichLog` (`_prefers_rich` attribute) and uses either:
- `panel.write(Text.from_markup(line))` for RichLog.
- `panel.write_line(plain_text)` or `panel.write(plain_text + "\n")` for Log/TextLog.

### 11.7 Verbose / Log Mode in TUI

When `--verbose` is passed:
- The logs container is made visible immediately.
- `sys.stdout` and `sys.stderr` are replaced with a `_UILogStream` that routes writes to `logs_panel`.
- The root Python logger is reconfigured with a `StreamHandler` pointing at the same stream.
- `set_log_sink()` routes `log_print()` output to the logs panel.
- On `on_unmount`, original `stdout`/`stderr` are restored and the log sink is cleared.

---

## 12. Legacy Monolith (`cypher_llm_repl.py`)

`cypher_llm_repl.py` is a self-contained single-file version of the REPL. It contains the same logic as the refactored `cypherrepl/` package but as module-level globals (no dataclasses, no dependency injection):

- Config read directly from `os.environ` into module-level variables.
- `INIT_STATEMENTS` as a module-level list.
- `DEFAULT_COLS` as a module-level constant.
- All utility functions defined in one file.
- LLM, DB, and REPL code all in `main()`.

It does **not** have the TUI (`-t`) flag or the Azure provider abstraction found in the refactored version. It serves as a reference implementation and entry point for users who prefer a single file. Both implementations share identical behavior for all common features.

---

## 13. Data Flow Diagrams

### 13.1 LLM Mode Query Flow

```
User types natural language
        │
        ▼
PromptSession / SubmitTextArea
        │
        ▼
agent_executor.invoke({
    "input": text,
    "chat_history": [HumanMessage, AIMessage, ...]
})
        │
        ▼
LangChain ReAct Agent
  ┌─────────────────────────────┐
  │ LLM (ChatOpenAI /           │
  │      AzureChatOpenAI)       │
  │   + system prompt           │
  │   + chat_history            │
  │   + agent_scratchpad        │
  └──────────────┬──────────────┘
                 │  tool call: send_cypher("MATCH (n) RETURN n")
                 ▼
        send_cypher tool
                 │
                 ▼ (optional: log_print("TOOL", query))
        sanitize_llm_query_maybe_wrapped()
                 │
                 ▼
        execute_cypher_with_smart_columns()
                 │
                 ▼
        PostgreSQL / Apache AGE
          cypher('graph', $$ ... $$) AS (result agtype)
                 │
                 ▼
        format_rows() → tab-separated string
                 │
                 ▼ (optional: log_print("DB", formatted))
        returned to LLM as tool result
                 │
                 ▼
        LLM generates natural language response
                 │
                 ▼
        printed to console / chat_panel
```

### 13.2 Direct Cypher Mode Flow

```
User types Cypher query
        │
        ▼
(optional: log_print("TOOL", text))
        │
        ▼
execute_cypher_with_smart_columns(cur, conn, text, settings)
        │
        ├── split_cypher_statements() → List[str]
        │
        └── for each stmt:
              preprocess_cypher_query()
                      │
              sanitize_llm_query_maybe_wrapped()  (no-op for clean Cypher)
                      │
              parse_return_clause() → col_def
                      │
              SELECT * FROM cypher('graph', $$ stmt $$) AS col_def;
                      │
              [on failure with multi-col] rollback + retry with (result agtype)
                      │
              fetchall() + commit() → rows
        │
        ▼
format_rows(rows) → print / log_print("DB", ...)
```

---

## 14. Dependency Stack

```
Python ≥ 3.13  (pyproject.toml constraint)

Runtime dependencies
────────────────────
psycopg2-binary ≥ 2.9.10    PostgreSQL driver (sync, with RealDictCursor)
python-dotenv   ≥ 1.1.1     .env file loading
prompt-toolkit  ≥ 3.0.51    Terminal REPL (readline-style input, history)
textual         ≥ 5.3.0     Full-screen TUI framework (lazy import)
langchain       ≥ 0.3.27    Agent/chain orchestration
langchain-core  ≥ 0.3.74    Base types (messages, tools, callbacks, prompts)
langchain-openai ≥ 0.3.29   ChatOpenAI + AzureChatOpenAI wrappers
lark            ≥ 1.2.2     Parser toolkit (listed; not currently used in REPL)

Dev dependencies
────────────────
mypy     ≥ 1.17.1    Static type checking
pytest   ≥ 8.4.1     Testing
ruff     ≥ 0.12.8    Linting + formatting

Infrastructure
──────────────
PostgreSQL 16
Apache AGE (PG16 branch)    openCypher graph engine as a PG extension
pgvector v0.8.0             Vector similarity search as a PG extension
Docker (optional)           Containerized tri-store database
uv                          (recommended) fast Python package manager
```

---

## 15. Key Design Decisions and Patterns

### Dual execution modes with graceful fallback

If LLM initialization fails (missing API key, network error), the REPL does not abort. It sets `llm_enabled = False` and continues in direct Cypher mode, printing an informative message. The user can re-enable LLM mode at any time with `\llm on`, which will attempt re-initialization.

### Fail-fast LLM validation before DB connection

`create_llm(settings)` is called before `connect_db()` in the startup sequence. This ensures a misconfigured API key is reported immediately rather than after a potentially slow database connect.

### Two-attempt column strategy for AGE

The `cypher()` function requires a column definition list that must exactly match the RETURN clause. The RETURN-clause parser attempts to infer this dynamically, but inference is heuristic. A failed first attempt rolls back and retries with the single-column fallback `(result agtype)`. This eliminates a whole class of "return row and column definition list do not match" errors without requiring perfect parse logic.

### LLM output sanitization layer

Even with an explicit system prompt forbidding SQL wrappers, LLMs occasionally emit `SELECT * FROM cypher(...)` forms. The `sanitize_llm_query_maybe_wrapped` function acts as a safety net, stripping these before the query reaches the database layer. This makes the system robust to model version changes and prompt drift.

### Immutable settings via frozen dataclasses

All configuration is captured once at startup into `@dataclass(frozen=True)` objects. This prevents accidental mutation of configuration mid-session and makes the data flow explicit: settings are constructed once by `get_settings()` and passed through as dependencies.

### Log sink abstraction

Rather than coupling log output to `sys.stdout`, `log_print` routes through a module-level callable (`_log_sink`). The TUI installs a custom sink that writes to the on-screen log panel and uninstalls it on exit. This decouples the logging mechanism from the display layer cleanly.

### Lazy Textual import

`tui.py` imports Textual inside `run_tui()` rather than at module level. This means `textual` is not required for standard REPL operation — the package can be used without it if the user never passes `-t`.

### Conversation memory in both UIs

Both the CLI and TUI accumulate a `chat_history` list of `HumanMessage`/`AIMessage` pairs and pass it on every `agent_executor.invoke()` call. This gives the LLM agent true multi-turn memory within a session, enabling contextual follow-up queries.

### Monolith preserved alongside package

`cypher_llm_repl.py` is kept as a working single-file alternative. Both implementations are kept functionally synchronized for the core REPL features. The package form (`cypherrepl/`) is the canonical implementation for new features (TUI, Azure OpenAI, structured settings).
