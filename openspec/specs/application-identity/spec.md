## Purpose
Define product/package identity and entry points for MindState.

## Requirements

### Requirement: Installed executable is `mstate`
The package SHALL register `mstate` as the installed command-line executable via `[project.scripts]` in `pyproject.toml`, pointing to `mindstate.__main__:_run`.

#### Scenario: Executable available after install
- **WHEN** the package is installed with `pip install` or `uv sync`
- **THEN** `mstate` is available on the system PATH and launches the application

#### Scenario: Direct help flag works
- **WHEN** the user runs `mstate --help`
- **THEN** the application prints usage information and exits with code 0

### Requirement: Module entry point is `python -m mindstate`
The package SHALL support `python -m mindstate` as the canonical programmatic entry point.

#### Scenario: Module invocation launches application
- **WHEN** the user runs `python -m mindstate`
- **THEN** the application starts identically to running `mstate`

### Requirement: Package is named `mindstate`
The `pyproject.toml` project name SHALL be `mindstate`. The source package directory SHALL be `mindstate/`.

#### Scenario: Package name in metadata
- **WHEN** `pip show mindstate` or `uv pip show mindstate` is run after install
- **THEN** the package name shown is `mindstate`

### Requirement: No `cypherrepl` package remains
The old `cypherrepl/` source directory SHALL be deleted. No compatibility shim SHALL be provided.

#### Scenario: Old entry point does not exist
- **WHEN** the user attempts `python -m cypherrepl`
- **THEN** Python raises `No module named cypherrepl`
