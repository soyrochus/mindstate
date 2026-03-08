## 1. Package and Entry Point

- [ ] 1.1 Rename directory `cypherrepl/` → `mindstate/`
- [ ] 1.2 Update `pyproject.toml`: set `name = "mindstate"`, add `[project.scripts]` with `mstate = "mindstate.__main__:_run"`
- [ ] 1.3 Verify `python -m mindstate` launches the application
- [ ] 1.4 Verify `mstate --help` works after `uv sync` / reinstall

## 2. Configuration Defaults

- [ ] 2.1 In `mindstate/config.py`: change `history_file` default from `~/.cypher_repl_history` to `~/.mstate_history`
- [ ] 2.2 In `mindstate/config.py`: change `AGE_GRAPH` default from `"demo"` to `"mindstate"`
- [ ] 2.3 In `mindstate/config.py`: update `DEFAULT_SYSTEM_PROMPT` to identify the assistant as a MindState agent (remove "Cypher agent" as the primary identity)

## 3. CLI Identity Strings

- [ ] 3.1 In `mindstate/cli.py`: update startup banner (currently `"Cypher REPL for AGE/PostgreSQL - graph: ..."`) to use MindState identity
- [ ] 3.2 In `mindstate/cli.py`: change REPL prompt from `"cypher> "` to `"mstate> "`
- [ ] 3.3 In `mindstate/cli.py`: update `argparse` description from `"Cypher REPL for AGE/PostgreSQL"` to reference MindState

## 4. TUI Identity

- [ ] 4.1 In `mindstate/tui.py`: rename class `CypherReplTUI` → `MindStateTUI` (both definition at line 67 and instantiation at line 609)
- [ ] 4.2 In `mindstate/tui.py`: update any visible TUI title or header text to reference MindState

## 5. Docker and Infrastructure

- [ ] 5.1 Rename `init-tristore.sql` → `init-mindstate.sql`
- [ ] 5.2 Update `Dockerfile`: change `COPY init-tristore.sql` → `COPY init-mindstate.sql`
- [ ] 5.3 Update `run.sh`: replace `--name tristore` and `localhost/tristore-pg` with MindState-oriented names

## 6. Documentation and Supporting Files

- [ ] 6.1 Update `README.md`: replace TriStore/CypherREPL product identity with MindState/mstate throughout
- [ ] 6.2 Update `REPL-MANUAL.md`: replace product identity references, update any prompt examples (`cypher>` → `mstate>`)
- [ ] 6.3 Update `example.env`: update any comments that reference TriStore or CypherREPL identity (variable names unchanged)

## 7. Cleanup

- [ ] 7.1 Delete old `cypherrepl/` directory if it was not renamed in place (no shim to add)
- [ ] 7.2 Grep the repo for remaining `tristore`, `cypherrepl`, `CypherRepl`, `cypher_repl` strings and fix any that carry product identity

## 8. Smoke Test

- [ ] 8.1 Run `mstate --help` — confirm MindState identity in output, no TriStore/CypherREPL references
- [ ] 8.2 Run `python -m mindstate --help` — confirm identical to `mstate --help`
- [ ] 8.3 Confirm `python -m cypherrepl` raises `No module named cypherrepl`
- [ ] 8.4 Connect to database and run a direct Cypher query in CLI mode — confirm no regression
- [ ] 8.5 Launch TUI (`mstate --tui`) — confirm MindState title and functional parity
