# Feature 1 — Rebase the current low-level TriStore/Cypher REPL into the MindState base application

## Intent

The current implementation should be converted from a narrowly named Cypher/TriStore utility into the **MindState base application**, while deliberately preserving its low-level character. This feature does **not** add higher-order memory behaviors yet. It only renames, repositions, and minimally restructures the existing brownfield implementation so that it becomes the stable technical base for future MindState features.

This means the present low-level capabilities must remain intact:

* direct access to the PostgreSQL/AGE/pgvector substrate
* direct Cypher execution
* LLM-assisted Cypher generation and execution
* CLI REPL
* TUI REPL
* file-based initialization and execution
* verbose logging and toggleable LLM mode

Those capabilities are already present and are explicitly part of the current TriStore/Cypher REPL behavior. 

## Problem statement

The current naming and packaging reflect the implementation history rather than the intended product. At the moment:

* the database substrate is branded as **TriStore**
* the Python package is branded around **cypherrepl**
* the user-facing executable identity is Cypher-centric
* environment naming is generic or tied to TriStore/Cypher naming
* the system reads as a graph exploration tool rather than as the low-level shell of a broader memory platform

That is now a liability. The base implementation should become the **MindState low-level shell**, with `mstate` as the executable identity, while still exposing the current “bare metal” interface to graph, vector, and relational storage.

## Functional outcome

After this feature, a developer should be able to install and launch the application as **M-state / MindState**, and use it exactly as they use the current Cypher REPL today, but under the new conceptual and naming model.

The user should still be able to do the following:

* open a terminal REPL against the backing database
* switch LLM mode on or off
* run direct Cypher
* load files
* use the TUI
* inspect the underlying graph/vector/relational substrate with minimal abstraction

The system should still feel low-level. It is not yet the full memory application. It is the renamed, stabilized technical foundation.

## Scope

This feature includes renaming and structural adaptation at the following levels:

### 1. User-facing identity

The executable name becomes:

* `mstate`

The product/application name becomes:

* `MindState`

The term **TriStore** should be removed from user-facing documentation, prompts, help text, status messages, and visible identifiers unless explicitly retained in migration notes.

The term **Cypher REPL** should cease to be the primary identity. It may still appear descriptively in subcomponents where appropriate, but the user must perceive the system as MindState.

### 2. Package and module naming

The current `cypherrepl` package should be renamed or superseded by a package structure aligned with MindState. The preferred direction is:

* top-level package or app namespace based on `mindstate`

Submodules may still include low-level domains such as `cypher`, `db`, `llm`, `cli`, `tui`, but the root namespace should stop signaling that the application is only a Cypher REPL.

A pragmatic migration path is acceptable. It is not necessary to atomically rename every internal symbol if compatibility shims are cheaper, but the external application boundary must become MindState.

### 3. Configuration and environment variables

Configuration keys and environment variables that are product-specific should be renamed away from TriStore/Cypher naming toward MindState naming.

Examples of what should change:

* graph name defaults or references that use TriStore-centric naming
* history-file defaults with old product names
* prompt text referring to the Cypher REPL or TriStore
* Docker labels, image names, service names, and example `.env` variables where applicable

Not every low-level variable must be prefixed with `MINDSTATE_` if it is a standard PostgreSQL convention such as `PGHOST`, `PGPORT`, and so on. Standard ecosystem variables should remain standard. Product-specific configuration should become explicit and MindState-specific.

### 4. Docker and infrastructure naming

If the Docker image, initialization script names, container defaults, or startup instructions visibly refer to TriStore, they should be updated to MindState equivalents.

The underlying technical choices do **not** change in this feature. The base remains PostgreSQL 16 with Apache AGE and pgvector, as documented in the existing architecture. 

The Dockerfile only needs functional change where naming or file layout requires it. There is no value in rewriting build logic that already works.

### 5. CLI/TUI behavior retention

The current behaviors documented for the CLI and TUI must be preserved:

* standard REPL mode
* TUI mode
* file execution
* verbose logging
* LLM on/off toggling
* direct Cypher mode
* history behavior
* existing command-dispatch semantics, unless a rename is necessary

These are part of the stable low-level base and should not regress. 

## Low-level interface requirements to preserve

This is the most important part of Feature 1.

MindState must retain an explicit low-level interface to the substrate. That interface exists for developers, operators, and advanced users who want to inspect or manipulate the graph/vector/relational layers directly.

The preserved low-level interface should include:

* direct Cypher submission
* file-based Cypher execution
* visibility into raw query results
* ability to bypass higher-level memory abstractions
* optional natural-language-to-Cypher mode through the LLM
* logging that reveals executed tool/query behavior

This low-level shell is not a temporary hack. It is a deliberate product facet. MindState is expected to grow higher-level APIs and UIs later, but it must continue to expose the substrate for debugging, administration, experimentation, and brownfield inspection.

## Required changes

### Naming and executable changes

Implement the application command as `mstate`.

The package should expose something equivalent to:

* `python -m mindstate`
* `mstate`

The current `python -m cypherrepl` style must be replaced or kept only as a deprecated compatibility path.

### Text and prompt changes

All user-visible prompts, banners, help text, logs, and system prompts must replace TriStore/Cypher-REPL identity with MindState identity where appropriate.

Example changes:

* prompt banners
* welcome text
* usage examples
* TUI labels
* help commands
* docs and README language
* example system prompt phrasing

### File and artifact changes

Artifacts such as:

* `init-tristore.sql`
* image names
* sample env files
* run scripts
* history files

should be renamed where doing so improves clarity and reduces brand drift.

A compatibility bridge may be kept for legacy filenames if necessary, but the canonical names should be MindState-oriented.

### Internal code changes

Where code symbols are tightly product-specific, rename them. Where symbols are purely local technical names, avoid churn without value.

For example:

* `CypherReplTUI` should become a MindState-oriented TUI class
* application entry-point modules should reflect the new name
* legacy monolith files may be moved to a compatibility or `legacy/` area rather than deleted immediately

### Migration behavior

Because this is brownfield engineering, the migration should be conservative.

The feature should include:

* backward-compatible startup where reasonable
* explicit deprecation warnings for old entry points if retained
* no forced rewrite of underlying database schema in this feature
* no behavior change in query execution semantics

## Non-goals

This feature does not include:

* semantic memory objects
* high-level REST API
* higher-level “remember/recall/build context” behavior
* MCP server
* UI workflows beyond today’s low-level REPL/TUI model
* re-architecture of the projection model

It is a product rebasing and stabilization feature, not a functional expansion feature.

## Acceptance criteria

A build is acceptable when the following are true:

1. The application can be launched as `mstate`.
2. The application still supports direct Cypher mode and LLM-assisted mode.
3. The current TUI still works under the new name.
4. TriStore branding is removed from user-facing identity except where retained for migration notes.
5. Product-specific variables, prompts, file names, and help text use MindState terminology.
6. No regression is observed in the existing AGE/pgvector/Postgres interaction model.
7. The system remains a low-level substrate exploration tool after the rename.

## Technical notes

This feature should be treated as a controlled brownfield refactor. The existing technical architecture already separates config, DB, LLM, logging, CLI, and TUI concerns reasonably well. That structure should be reused, not discarded. 

---
