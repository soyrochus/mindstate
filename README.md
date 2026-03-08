# MindState

![Python Version](https://img.shields.io/badge/Python-3.13%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Experimental-orange)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-informational)
![Graph Engine](https://img.shields.io/badge/Apache%20AGE-openCypher-purple)
![Vectors](https://img.shields.io/badge/pgvector-enabled-blueviolet)

A persistent AI memory substrate that stores knowledge as canonical items and exposes it through cognitive operations — remember, recall, build context — rather than raw storage mechanics.

> **NOTE**: The current implementation is the low-level foundation: a direct `mstate` shell against the PostgreSQL/AGE/pgvector substrate, supporting Cypher execution, LLM-assisted natural language queries, and interactive REPL and TUI modes. Higher-level memory behaviors (capture, recall, context assembly, MCP tools) are planned as the next layer on top of this base.

**Components in this repo**

| Part | What it is | Folder / File |
|------|------------|---------------|
| Interactive REPL (LLM + direct Cypher) | Query graph with natural language or raw Cypher | `mindstate/` |
| Detailed REPL manual | Full feature & usage guide | `REPL-MANUAL.md` |
| Cypher cheat sheet & how‑to | Quick Cypher reminders | `Cypher Cheat Sheet and How-To Guide.md` |
| Dockerized Postgres 16 + AGE + pgvector | Single MindState-oriented container | `Dockerfile`, `init-mindstate.sql` |
| Sample graph init | Optional starting graph | `init_graph.cypher` |


---


## FEATURES

- Interactive MindState REPL for PostgreSQL/AGE
- Execute Cypher scripts from files
- LLM integration for query generation and explanation
- System prompt customization for LLM
- Verbose error output for debugging
- **Colourful Text User Interface (TUI):** Use the `-t` or `--tui` option to launch a modern, colourful Text User Interface for enhanced interaction.

*Simple (default) REPL*
![Simple REPL](images/replsimple.png)

*TUI REPL (using the Textual library)*
![Simple REPL](images/repltui.png)

---

## Startup Options

The MindState REPL can be started with various options to customize its behavior:

```
positional arguments:
  files                 Cypher files to load and execute

options:
  -h, --help            show this help message and exit
  -e, --execute         Execute files and exit (do not start REPL)
  -t, --tui             Launch the Textual TUI instead of the standard REPL (shows a colourful Text User Interface)
  -s, --system-prompt SYSTEM_PROMPT
                        Path to a file containing a system prompt for the LLM
  -v, --verbose         Enable verbose output (show stack traces on errors)
```

---

## REPL Overview (Primary Focus)

The MindState REPL lets you:

* Use plain English (LLM mode) → translated into Cypher and executed
* Fall back to direct Cypher mode instantly (`\llm off` / `\llm on`)
* Run multiple Cypher statements in one line (semicolon separated)
* Auto-detect return columns & format nodes, edges, and paths
* Persist command history between sessions
* Optionally log: natural language → generated Cypher → DB results

See the full manual in `REPL-MANUAL.md` for screenshots, examples, tips.

### Key Commands (inline recap)
| Command |  Description |
|---------|-------------|
| `\q` | Quit the REPL |
| `\log [on \| off]` | Toggle logging of LLM and DB interactions |
| `\llm [on \|off]` | Toggle LLM usage (off executes Cypher directly) |
| `\h` | Show this help message |

### Quick Examples
Natural language (LLM mode):
```
show all nodes and their relationships
create a person named Alice who is 30
find shortest path between Alice and any Button
```

Direct Cypher:
```
MATCH (n) RETURN n;
MATCH (n)-[r]->(m) RETURN n, r, m;
CREATE (p:Person {name: 'Alice', age: 30}) RETURN p;
```

### Environment Variables (REPL)
Put these in a `.env` (see `example.env`):
```
PGHOST=localhost
PGPORT=5432
PGDATABASE=postgres
PGUSER=postgres
PGPASSWORD=secret
AGE_GRAPH=mindstate

# LLM (optional – only needed for natural language mode)
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL_NAME=gpt-4.1
OPENAI_TEMPERATURE=0
```

### Running the REPL
Install Python deps (uses `pyproject.toml`). You can use [uv](https://github.com/astral-sh/uv) or plain pip:
```bash
# With uv (fast)
uv sync

# Start REPL (LLM mode default)
mstate
# or
python -m mindstate

# Execute files then drop into REPL
mstate init_graph.cypher

# Execute files only (no REPL)
mstate -e init_graph.cypher more.cypher
```

For advanced usage, read: `REPL-MANUAL.md`  
For Cypher syntax help: `Cypher Cheat Sheet and How-To Guide.md`

---

## Dockerized MindState (Postgres + AGE + pgvector)

The provided `Dockerfile` builds a single image bundling:
* PostgreSQL 16
* Apache AGE (openCypher property graph)
* pgvector (vector similarity search)

Initialization script: `init-mindstate.sql` (creates extensions + a default graph `mindstate`).

### Build & Run
```bash
docker build -t mindstate-pg:latest .
docker run -d \
  --name mindstate \
  -e POSTGRES_PASSWORD=secret \
  -p 5432:5432 \
  mindstate-pg:latest
```

Defaults:
* Host: `localhost:5432`
* User: `postgres`
* Password: `secret`
* DB: `postgres`
* Graph created at init: `mindstate`

### Verify Extensions
```bash
psql -h localhost -U postgres -d postgres
\dx   # should list age + vector
```

### Simple Graph & Vector Checks
Create a node:
```sql
SELECT * FROM cypher('my_graph', $$CREATE (n:Person {name: 'Alice', age: 30}) RETURN n$$) AS (n agtype);
```
Vector table:
```sql
CREATE TABLE embeddings (
  id serial PRIMARY KEY,
  content text,
  embedding vector(1536)
);
```
Similarity search:
```sql
SELECT * FROM embeddings ORDER BY embedding <-> '[0.1,0.2,0.3]' LIMIT 1;
```

### Using with the REPL
Once the container is running, ensure your `.env` matches the exposed credentials, then start the REPL. Natural language queries will be rewritten into Cypher targeting the configured graph.

---

## Python Access (Outside the REPL)
```python
import psycopg2

conn = psycopg2.connect(
    host="localhost", port=5432,
    user="postgres", password="secret", dbname="postgres"
)
cur = conn.cursor()

# Raw Cypher via AGE
q = "MATCH (p:Person) RETURN p"
cur.execute("SELECT * FROM cypher(%s, %s) AS (p agtype);", ("mindstate", q))
print(cur.fetchall())

# Vector similarity
cur.execute(
    "SELECT content FROM embeddings ORDER BY embedding <-> %s LIMIT 1",
    ([0.12, 0.04, 0.33],)
)
print(cur.fetchone())
```

---

## Project Structure (Abbrev.)
```
mindstate/        # REPL implementation (CLI, db, LLM integration, formatting)
Dockerfile        # Builds Postgres+AGE+pgvector image
init-mindstate.sql # Enables extensions & creates graph
init_graph.cypher # Sample Cypher to preload data
example.env       # Template env vars
REPL-MANUAL.md    # Full REPL manual
Cypher Cheat Sheet and How-To Guide.md
```

---

## Roadmap / Ideas
* Optional local embedding generation
* More graph analytics helpers (degree, centrality summaries)
* Export/import graph snapshots
* Additional model provider abstractions

Contributions / issues welcome.

---
## Principles of Participation

Everyone is invited and welcome to contribute: open issues, propose pull requests, share ideas, or help improve documentation.  
Participation is open to all, regardless of background or viewpoint.  

This project follows the [FOSS Pluralism Manifesto](./FOSS_PLURALISM_MANIFESTO.md),  
which affirms respect for people, freedom to critique ideas, and space for diverse perspectives.  


## License and Copyright

Copyright (c) 2025,2026 Iwan van der Kleijn

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Attribution & Notes
All bundled components (PostgreSQL, Apache AGE, pgvector) are open source. This repo glues them together for a smooth graph + vector + LLM exploration workflow.

If you build something interesting with this, let me know or open a PR to showcase examples.
