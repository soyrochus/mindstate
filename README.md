# MindState

![Python Version](https://img.shields.io/badge/Python-3.13%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Experimental-orange)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-informational)
![Graph Engine](https://img.shields.io/badge/Apache%20AGE-openCypher-purple)
![Vectors](https://img.shields.io/badge/pgvector-enabled-blueviolet)

A persistent AI memory substrate that stores knowledge as canonical items and exposes it through cognitive operations — remember, recall, build context — rather than raw storage mechanics.

> **NOTE**: MindState now includes a first behavior-oriented memory layer (`remember`, `recall`, `build_context`) exposed via FastAPI and TUI workflows, while preserving the low-level Cypher/LLM shell.

![Mindstate](./images/mindstate.png)

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
- Behavior-oriented memory API: `POST /v1/memory/remember`, `POST /v1/memory/recall`, `POST /v1/context/build`
- Higher-level TUI memory workflows (`\\mode memory`, `\\remember`, `\\recall`, `\\context`, `\\inspect`) in `mstate --tui`
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
  --api                 Run the FastAPI service instead of the REPL
  --api-host API_HOST   API host bind address
  --api-port API_PORT   API port
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
| `\contextualize [n]` | Queue graph-contextualization for the latest eligible `n` items (default `1`) |
| `\contextualize --id <UUID>` | Queue graph-contextualization for a specific memory item |
| `\mode [shell \| memory]` | Switch default input workflow between shell and memory |
| `\remember KIND \| CONTENT` | Store canonical memory item |
| `\recall QUERY` | Run ranked semantic memory recall |
| `\context QUERY` | Build a bounded context bundle |
| `\inspect MEMORY_ID` | Inspect stored memory content and metadata |
| `\h` | Show this help message |

These slash commands are intentionally unified between the standard REPL (`mstate`) and TUI (`mstate --tui`) via a shared command parser.

Quick TUI flow:
```bash
mstate --tui
# inside TUI:
\mode memory
\remember note | Project alpha ships Friday.
\recall alpha ships
\context Prepare Friday release context
```

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

### Environment Variables (REPL + Memory API)
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

# API server
MS_API_HOST=127.0.0.1
MS_API_PORT=8000

# Memory embedding configuration
MS_EMBEDDING_PROVIDER=openai
MS_EMBEDDING_MODEL=text-embedding-3-small
MS_EMBEDDING_DIMENSIONS=1536
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

# Run API server
mstate --api
# or
mstate-api
```

### Memory API quick example
```bash
curl -X POST http://127.0.0.1:8000/v1/memory/remember \
  -H "Content-Type: application/json" \
  -d '{"kind":"note","content":"Project alpha ships Friday.","source":"meeting"}'

curl -X POST http://127.0.0.1:8000/v1/memory/recall \
  -H "Content-Type: application/json" \
  -d '{"query":"alpha ships","limit":5}'

curl -X POST http://127.0.0.1:8000/v1/context/build \
  -H "Content-Type: application/json" \
  -d '{"query":"Prepare Friday release context","limit":5}'
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
SELECT * FROM cypher('mindstate', $$CREATE (n:Person {name: 'Alice', age: 30}) RETURN n$$) AS (n agtype);
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
