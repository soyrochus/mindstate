from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence
from uuid import uuid4

from psycopg2.extras import Json

from .config import Settings
from .memory_models import MemoryItem, RecallResultItem, RememberInput


def _vector_literal(values: Sequence[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in values) + "]"


def ensure_memory_schema(cur, conn, settings: Settings) -> None:
    """Create additive canonical-memory structures while preserving substrate behavior."""
    statements = [
        "CREATE EXTENSION IF NOT EXISTS vector;",
        "CREATE EXTENSION IF NOT EXISTS pgcrypto;",
        """
        CREATE TABLE IF NOT EXISTS memory_items (
            memory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            kind TEXT NOT NULL,
            content TEXT NOT NULL,
            content_format TEXT NOT NULL DEFAULT 'text/plain',
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            provenance_anchor TEXT NULL,
            occurred_at TIMESTAMPTZ NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS memory_sources (
            memory_id UUID PRIMARY KEY REFERENCES memory_items(memory_id) ON DELETE CASCADE,
            source TEXT NULL,
            author TEXT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS memory_chunks (
            chunk_id BIGSERIAL PRIMARY KEY,
            memory_id UUID NOT NULL REFERENCES memory_items(memory_id) ON DELETE CASCADE,
            chunk_index INT NOT NULL,
            chunk_text TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS memory_embeddings (
            embedding_id BIGSERIAL PRIMARY KEY,
            memory_id UUID NOT NULL REFERENCES memory_items(memory_id) ON DELETE CASCADE,
            chunk_id BIGINT NOT NULL REFERENCES memory_chunks(chunk_id) ON DELETE CASCADE,
            model_name TEXT NOT NULL,
            embedding vector({settings.memory.embedding_dimensions}) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS memory_links (
            link_id BIGSERIAL PRIMARY KEY,
            memory_id UUID NOT NULL REFERENCES memory_items(memory_id) ON DELETE CASCADE,
            linked_memory_id UUID NULL REFERENCES memory_items(memory_id) ON DELETE SET NULL,
            relation_type TEXT NOT NULL,
            evidence TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        """
        ALTER TABLE memory_items
            ADD COLUMN IF NOT EXISTS contextualized_at TIMESTAMPTZ NULL;
        """,
        """
        ALTER TABLE memory_items
            ADD COLUMN IF NOT EXISTS contextualization_skipped BOOLEAN NOT NULL DEFAULT FALSE;
        """,
        """
        CREATE TABLE IF NOT EXISTS memory_contextualization_jobs (
            job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            memory_ids UUID[] NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            queued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            started_at TIMESTAMPTZ NULL,
            completed_at TIMESTAMPTZ NULL,
            error TEXT NULL,
            result JSONB NULL
        );
        """,
    ]
    for statement in statements:
        cur.execute(statement)
    conn.commit()


def create_memory_item(cur, payload: RememberInput) -> MemoryItem:
    cur.execute(
        """
        INSERT INTO memory_items (kind, content, content_format, metadata, provenance_anchor, occurred_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING memory_id::text, kind, content, content_format, metadata, provenance_anchor, occurred_at, created_at, contextualized_at, contextualization_skipped;
        """,
        (
            payload.kind,
            payload.content,
            payload.content_format,
            Json(payload.metadata or {}),
            payload.provenance_anchor,
            payload.occurred_at,
        ),
    )
    item_row = cur.fetchone()
    cur.execute(
        """
        INSERT INTO memory_sources (memory_id, source, author)
        VALUES (%s::uuid, %s, %s)
        ON CONFLICT (memory_id) DO UPDATE
        SET source = EXCLUDED.source, author = EXCLUDED.author;
        """,
        (item_row["memory_id"], payload.source, payload.author),
    )
    return MemoryItem(
        memory_id=item_row["memory_id"],
        kind=item_row["kind"],
        content=item_row["content"],
        content_format=item_row["content_format"],
        source=payload.source,
        author=payload.author,
        metadata=item_row["metadata"] or {},
        provenance_anchor=item_row["provenance_anchor"],
        occurred_at=item_row["occurred_at"],
        created_at=item_row["created_at"],
        contextualized_at=item_row.get("contextualized_at"),
        contextualization_skipped=bool(item_row.get("contextualization_skipped", False)),
    )


def create_chunk(cur, memory_id: str, chunk_index: int, chunk_text: str) -> int:
    cur.execute(
        """
        INSERT INTO memory_chunks (memory_id, chunk_index, chunk_text)
        VALUES (%s::uuid, %s, %s)
        RETURNING chunk_id;
        """,
        (memory_id, chunk_index, chunk_text),
    )
    row = cur.fetchone()
    return int(row["chunk_id"])


def create_embedding(cur, memory_id: str, chunk_id: int, model_name: str, values: Sequence[float]) -> None:
    cur.execute(
        """
        INSERT INTO memory_embeddings (memory_id, chunk_id, model_name, embedding)
        VALUES (%s::uuid, %s, %s, %s::vector);
        """,
        (memory_id, chunk_id, model_name, _vector_literal(values)),
    )


def create_link(
    cur,
    memory_id: str,
    relation_type: str,
    evidence: Optional[str],
    linked_memory_id: Optional[str] = None,
) -> None:
    cur.execute(
        """
        INSERT INTO memory_links (memory_id, linked_memory_id, relation_type, evidence)
        VALUES (%s::uuid, %s::uuid, %s, %s);
        """,
        (memory_id, linked_memory_id, relation_type, evidence),
    )


def commit(conn) -> None:
    conn.commit()


def rollback(conn) -> None:
    conn.rollback()


def recall_by_embedding(
    cur,
    query_embedding: Sequence[float],
    limit: int,
    kind: Optional[str] = None,
    source: Optional[str] = None,
) -> List[RecallResultItem]:
    cur.execute(
        """
        SELECT
            mi.memory_id::text AS memory_id,
            mi.kind,
            mi.content,
            COALESCE(ms.source, NULL) AS source,
            COALESCE(ms.author, NULL) AS author,
            mi.metadata,
            mi.provenance_anchor,
            MIN(me.embedding <-> %s::vector) AS distance
        FROM memory_items mi
        JOIN memory_embeddings me ON me.memory_id = mi.memory_id
        LEFT JOIN memory_sources ms ON ms.memory_id = mi.memory_id
        WHERE (%s IS NULL OR mi.kind = %s)
          AND (%s IS NULL OR ms.source = %s)
        GROUP BY mi.memory_id, mi.kind, mi.content, ms.source, ms.author, mi.metadata, mi.provenance_anchor
        ORDER BY distance ASC
        LIMIT %s;
        """,
        (_vector_literal(query_embedding), kind, kind, source, source, limit),
    )
    rows = cur.fetchall()
    out: List[RecallResultItem] = []
    for row in rows:
        distance = float(row["distance"])
        out.append(
            RecallResultItem(
                memory_id=row["memory_id"],
                kind=row["kind"],
                content=row["content"],
                source=row["source"],
                author=row["author"],
                metadata=row["metadata"] or {},
                provenance_anchor=row["provenance_anchor"],
                score=1.0 / (1.0 + distance),
            )
        )
    return out


def get_links_for_memory_ids(cur, memory_ids: Iterable[str]) -> List[Dict[str, Any]]:
    ids = list(memory_ids)
    if not ids:
        return []
    cur.execute(
        """
        SELECT
            memory_id::text AS memory_id,
            COALESCE(linked_memory_id::text, NULL) AS linked_memory_id,
            relation_type,
            evidence
        FROM memory_links
        WHERE memory_id = ANY(%s::uuid[]);
        """,
        (ids,),
    )
    return [dict(row) for row in cur.fetchall()]


def get_recent_decisions(cur, limit: int = 5) -> List[Dict[str, Any]]:
    cur.execute(
        """
        SELECT memory_id::text AS memory_id, kind, content, created_at
        FROM memory_items
        WHERE kind = 'decision'
        ORDER BY created_at DESC
        LIMIT %s;
        """,
        (limit,),
    )
    return [dict(row) for row in cur.fetchall()]


def get_memory_item_by_id(cur, memory_id: str) -> Optional[Dict[str, Any]]:
    cur.execute(
        """
        SELECT
            mi.memory_id::text AS memory_id,
            mi.kind,
            mi.content,
            mi.content_format,
            COALESCE(ms.source, NULL) AS source,
            COALESCE(ms.author, NULL) AS author,
            mi.metadata,
            mi.provenance_anchor,
            mi.occurred_at,
            mi.created_at,
            mi.contextualized_at,
            mi.contextualization_skipped
        FROM memory_items mi
        LEFT JOIN memory_sources ms ON ms.memory_id = mi.memory_id
        WHERE mi.memory_id = %s::uuid
        LIMIT 1;
        """,
        (memory_id,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def get_eligible_for_contextualization(cur, n: int) -> List[str]:
    cur.execute(
        """
        SELECT memory_id::text AS memory_id
        FROM memory_items
        WHERE contextualized_at IS NULL
          AND contextualization_skipped = FALSE
        ORDER BY created_at DESC
        LIMIT %s;
        """,
        (n,),
    )
    return [row["memory_id"] for row in cur.fetchall()]


def create_contextualization_job(cur, conn, memory_ids: Sequence[str]) -> str:
    if not memory_ids:
        return ""
    cur.execute(
        """
        INSERT INTO memory_contextualization_jobs (memory_ids, status)
        VALUES (%s::uuid[], 'queued')
        RETURNING job_id::text AS job_id;
        """,
        (list(memory_ids),),
    )
    row = cur.fetchone()
    conn.commit()
    return row["job_id"] if row else str(uuid4())


def get_contextualization_job(cur, job_id: str) -> Optional[Dict[str, Any]]:
    cur.execute(
        """
        SELECT
            job_id::text AS job_id,
            status,
            COALESCE(array_length(memory_ids, 1), 0) AS queued_count,
            queued_at,
            started_at,
            completed_at,
            error,
            result
        FROM memory_contextualization_jobs
        WHERE job_id = %s::uuid
        LIMIT 1;
        """,
        (job_id,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def update_job_status(
    cur,
    conn,
    job_id: str,
    status: str,
    *,
    error: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
) -> None:
    started_at_expr = "NOW()" if status == "running" else "started_at"
    completed_at_expr = "NOW()" if status in {"done", "failed"} else "completed_at"
    cur.execute(
        f"""
        UPDATE memory_contextualization_jobs
        SET status = %s,
            started_at = {started_at_expr},
            completed_at = {completed_at_expr},
            error = %s,
            result = COALESCE(%s::jsonb, result)
        WHERE job_id = %s::uuid;
        """,
        (status, error, Json(result) if result is not None else None, job_id),
    )
    conn.commit()


def set_contextualized_at(cur, conn, memory_id: str) -> None:
    cur.execute(
        """
        UPDATE memory_items
        SET contextualized_at = NOW(), contextualization_skipped = FALSE
        WHERE memory_id = %s::uuid;
        """,
        (memory_id,),
    )
    conn.commit()


def set_contextualization_skipped(cur, conn, memory_id: str) -> None:
    cur.execute(
        """
        UPDATE memory_items
        SET contextualization_skipped = TRUE
        WHERE memory_id = %s::uuid;
        """,
        (memory_id,),
    )
    conn.commit()


def get_existing_memory_ids(cur, ids: Sequence[str]) -> List[str]:
    if not ids:
        return []
    cur.execute(
        """
        SELECT memory_id::text AS memory_id
        FROM memory_items
        WHERE memory_id = ANY(%s::uuid[]);
        """,
        (list(ids),),
    )
    return [row["memory_id"] for row in cur.fetchall()]
