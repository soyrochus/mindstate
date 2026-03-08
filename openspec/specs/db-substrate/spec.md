## Purpose
Define Docker/database substrate naming and behavior guarantees for MindState.

## Requirements

### Requirement: Docker init script is named `init-mindstate.sql`
The PostgreSQL initialization SQL file SHALL be named `init-mindstate.sql`. The filename `init-tristore.sql` SHALL NOT exist in the repository.

#### Scenario: Init file name in repository
- **WHEN** the repository root is listed
- **THEN** `init-mindstate.sql` is present and `init-tristore.sql` is absent

#### Scenario: Dockerfile references correct init script
- **WHEN** the Dockerfile is inspected
- **THEN** the `COPY` instruction references `init-mindstate.sql`, not `init-tristore.sql`

### Requirement: Database substrate behavior is unchanged
The underlying PostgreSQL/AGE/pgvector stack SHALL function identically after the rename. No schema changes, extension changes, or query execution behavior changes SHALL be introduced by this feature.

#### Scenario: AGE extension loads correctly
- **WHEN** the application connects to the database
- **THEN** the AGE extension is loaded and Cypher queries execute successfully

#### Scenario: pgvector remains available
- **WHEN** the database container is initialized using `init-mindstate.sql`
- **THEN** both the `age` and `vector` extensions are available

### Requirement: `run.sh` references MindState artifact names
Any shell scripts that reference Docker image names, container names, or init SQL filenames SHALL be updated to use MindState-oriented names.

#### Scenario: run.sh uses updated names
- **WHEN** `run.sh` is inspected
- **THEN** all references to TriStore artifact names are replaced with MindState equivalents
