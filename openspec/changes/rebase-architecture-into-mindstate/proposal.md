## Why

The current implementation is packaged and branded as a TriStore/CypherREPL utility, which reflects its implementation history rather than its intended product identity. Renaming and repositioning it now establishes a stable, correctly named base before higher-order MindState features are built on top of it.

## What Changes

- Rename the Python package from `cypherrepl` to `mindstate`
- Replace the `python -m cypherrepl` entry point with `python -m mindstate` and the `mstate` executable
- Remove TriStore branding from all user-facing prompts, banners, help text, and documentation
- Rename product-specific environment variables and configuration keys away from TriStore/Cypher naming
- Rename Docker artifacts (image names, init scripts, service labels) from TriStore to MindState naming
- Rename TUI class `CypherReplTUI` to a MindState-oriented equivalent
- Rename `init-tristore.sql` and other TriStore-named artifacts to MindState equivalents
- Retain deprecated compatibility entry points with explicit deprecation warnings where practical
- Preserve all existing low-level behaviors without regression: Cypher REPL, LLM-assisted mode, TUI, file execution, verbose logging, history

## Capabilities

### New Capabilities

- `application-identity`: Package name, executable name (`mstate`), module entry point (`python -m mindstate`), and top-level branding as MindState
- `cli-repl`: Command-line REPL supporting direct Cypher execution, LLM-assisted mode toggle, file-based execution, verbose logging, and history — under MindState identity
- `tui-repl`: Terminal UI (TUI) REPL mode preserving all current TUI behaviors under MindState identity
- `db-substrate`: PostgreSQL/AGE/pgvector connectivity and configuration layer, renamed away from TriStore naming
- `configuration`: Product-specific environment variables, config keys, defaults, and history-file naming under MindState conventions

### Modified Capabilities

<!-- No existing specs — this is the first structured spec pass on the codebase -->

## Impact

- **Python package**: `cypherrepl/` → `mindstate/` (or compatibility shim retained)
- **Executable**: `cypherrepl` → `mstate`
- **Entry point**: `python -m cypherrepl` → `python -m mindstate`
- **Docker**: image name, init SQL filename (`init-tristore.sql`), service labels, sample `.env` files
- **Environment variables**: product-specific vars renamed (e.g., graph name defaults, history file path, prompt text)
- **TUI class**: `CypherReplTUI` → MindState-oriented name
- **Docs and README**: all user-facing language updated to MindState/mstate terminology
- **No schema changes**: underlying PostgreSQL/AGE/pgvector architecture is unchanged
- **No behavior changes**: all query execution, LLM integration, and REPL semantics are preserved
