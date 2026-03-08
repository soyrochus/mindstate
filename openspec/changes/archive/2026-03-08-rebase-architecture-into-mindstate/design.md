## Context

The codebase currently consists of a single Python package `cypherrepl/` with modules `cli`, `config`, `db`, `llm`, `cypher`, `tui`, and `logging_utils`. The `pyproject.toml` project name is `tristore` and defines no `[project.scripts]` entry — there is no registered executable yet. Entry is via `python -m cypherrepl`. A `deprecated/` directory already exists and contains two legacy monolith scripts, establishing a precedent for the migration pattern.

Key naming inventory to change:
- `pyproject.toml`: `name = "tristore"`, no scripts section
- Package directory: `cypherrepl/`
- CLI banner: `"Cypher REPL for AGE/PostgreSQL - graph: ..."`
- CLI prompt: `"cypher> "`
- History file default: `~/.cypher_repl_history`
- Docker init SQL: `init-tristore.sql` (copied into container as init script)
- `example.env`: no product-specific vars (standard PG + LLM vars only — minimal rename needed)

Standard ecosystem variables (`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `AGE_GRAPH`, `LLM_PROVIDER`, `OPENAI_*`, `AZURE_OPENAI_*`) do not carry TriStore or CypherREPL identity and require no renaming.

## Goals / Non-Goals

**Goals:**
- Register `mstate` as an installed executable via `[project.scripts]`
- Enable `python -m mindstate` as the canonical entry point
- Rename the package directory from `cypherrepl/` to `mindstate/`
- Update `pyproject.toml` project name to `mindstate`
- Replace all user-visible TriStore/CypherREPL identity strings (banner, prompt, help text, TUI labels)
- Rename `init-tristore.sql` → `init-mindstate.sql` and update the Dockerfile
- Update history file default to `~/.mstate_history`
- Move `cypherrepl/` to `deprecated/cypherrepl/` as a compatibility shim with a deprecation warning, or simply remove it (decision below)

**Non-Goals:**
- Changing query execution semantics, database schema, or AGE/pgvector interaction
- Renaming standard ecosystem environment variables (`PG*`, `AGE_GRAPH`, `LLM_PROVIDER`, `OPENAI_*`, `AZURE_*`)
- Adding new features or CLI flags
- Rewriting internal technical symbols that carry no product identity (e.g., `DBSettings`, `execute_cypher_with_smart_columns`)

## Decisions

### 1. Direct package rename vs. parallel package with shim

**Decision**: Direct rename — move `cypherrepl/` to `mindstate/`. Add `deprecated/cypherrepl_shim.py` that imports from `mindstate` and prints a deprecation warning.

**Rationale**: There are no downstream library consumers of `cypherrepl` — it is a standalone application. A side-by-side package would add permanent maintenance overhead for no practical benefit. The existing `deprecated/` directory provides the right place for a lightweight shim that allows any scripts still calling `python -m cypherrepl` to continue working with a clear deprecation warning.

**Alternative considered**: Keep `cypherrepl/` in place and add `mindstate/` as a thin wrapper. Rejected — doubles the file tree with no benefit for an end-user application.

### 2. Executable registration

**Decision**: Add `[project.scripts]` to `pyproject.toml`:
```toml
[project.scripts]
mstate = "mindstate.__main__:_run"
```

**Rationale**: The project currently has no registered executable, meaning users must invoke `python -m cypherrepl` directly. Registering `mstate` fulfills the core product identity requirement and is the standard `pyproject.toml` mechanism.

### 3. Compatibility shim for `python -m cypherrepl`

**Decision**: Delete `cypherrepl/` entirely. No shim.

**Rationale**: This is a brownfield application with no external package consumers. There is no value in maintaining a compatibility layer. Clean removal is simpler and avoids permanent dead code.

### 4. History file rename

**Decision**: Change the default from `~/.cypher_repl_history` to `~/.mstate_history` in `config.py`.

**Rationale**: The old name carries product identity that should change. This is a configuration default — users who have set `HISTORY_FILE` or similar are unaffected. Existing history at the old path is not deleted; it simply stops being the default. A startup notice can inform users of the path change if needed.

### 5. Internal symbol renaming scope

**Decision**: Rename only symbols that are user-visible or carry explicit product identity. Do not rename internal technical helpers.

**Rename:**
- `CypherReplTUI` → `MindStateTUI` (user-visible class name, TUI title text)
- CLI banner string, prompt string (`cypher>` → `mstate>`)
- `DEFAULT_SYSTEM_PROMPT` text (replace "Cypher agent" phrasing with MindState-oriented phrasing)

**Do not rename:**
- `execute_cypher_with_smart_columns`, `init_age`, `format_rows` — purely technical, no product identity
- `DBSettings`, `LLMSettings`, `Settings` — generic dataclass names
- `VerboseCallback`, `log_print` — generic utility names

### 6. Docker artifact rename

**Decision**: Rename `init-tristore.sql` → `init-mindstate.sql`. Update the single `COPY` line in the Dockerfile. No other Docker changes needed.

**Rationale**: The init SQL filename is visible to operators and carries TriStore identity. The Dockerfile change is a one-line update.

## Risks / Trade-offs

- **History file migration**: Existing users lose their REPL history when the default path changes. Mitigation: add a one-time startup notice if `~/.cypher_repl_history` exists but `~/.mstate_history` does not, suggesting the user rename the file.
- **pyproject.toml name change**: Changing `name = "tristore"` to `name = "mindstate"` means existing `pip install tristore` (if used) breaks. Mitigation: this is an internal/brownfield application — no published PyPI package exists to break.

## Migration Plan

1. Rename `cypherrepl/` → `mindstate/` (internal relative imports require no changes)
2. Add `[project.scripts]` entry for `mstate` in `pyproject.toml`; update `name` to `mindstate`
3. Update user-visible strings in `cli.py` (banner, prompt, help text, argparse description)
4. Update `config.py` (history file default to `~/.mstate_history`, `AGE_GRAPH` default to `"mindstate"`, `DEFAULT_SYSTEM_PROMPT` text)
5. Rename `init-tristore.sql` → `init-mindstate.sql`; update Dockerfile `COPY` line
6. Update TUI class name and title in `tui.py`
7. Delete old `cypherrepl/` directory (no shim)
8. Update `README.md`, `REPL-MANUAL.md`, `example.env` comments, and any other docs
9. Run smoke test: `mstate --help`, `python -m mindstate --help`

**Rollback**: All changes are in a single branch. Git revert is sufficient. No database schema changes means no data rollback is needed.

## Open Questions

- Should the `run.sh` script be renamed or updated? It likely wraps Docker commands and may reference old artifact names — needs inspection during implementation.
