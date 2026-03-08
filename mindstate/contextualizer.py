from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import psycopg2
from langchain_openai import AzureOpenAIEmbeddings, OpenAIEmbeddings
from pydantic import BaseModel, Field
from psycopg2.extras import Json, RealDictCursor

from .config import Settings
from .db import init_age
from .llm import create_llm
from .memory_db import (
    create_chunk,
    create_contextualization_job,
    create_embedding,
    create_link,
    get_contextualization_job,
    get_eligible_for_contextualization,
    get_existing_memory_ids,
    get_memory_item_by_id,
    set_contextualization_skipped,
    set_contextualized_at,
    update_job_status,
)
from .memory_models import ContextualizeJobResponse

LOG = logging.getLogger(__name__)

ENTITY_TYPES = {
    "person",
    "organization",
    "project",
    "topic",
    "technology",
    "concept",
    "artifact",
    "place",
    "decision_ref",
    "task_ref",
}

RELATION_TYPES = {
    "about",
    "mentions",
    "decided_by",
    "for_project",
    "depends_on",
    "follows_from",
    "contradicts",
    "references_memory",
    "assigned_to",
    "resolved_by",
}


@dataclass(frozen=True)
class EntityCandidate:
    surface_form: str
    entity_type: str
    confidence: float


@dataclass(frozen=True)
class ResolvedEntity:
    node_id: str
    entity_type: str
    canonical_name: str
    created: bool


@dataclass(frozen=True)
class InferredRelation:
    source_id: str
    target_id: str
    relation_type: str
    evidence: Optional[str]


class _EntityOut(BaseModel):
    surface_form: str
    entity_type: str
    confidence: float = Field(ge=0.0, le=1.0)


class _EntityListOut(BaseModel):
    entities: List[_EntityOut] = Field(default_factory=list)


class _RelationOut(BaseModel):
    source_id: str
    target_id: str
    relation_type: str
    evidence: Optional[str] = None


class _RelationListOut(BaseModel):
    relations: List[_RelationOut] = Field(default_factory=list)


class _DisambiguationOut(BaseModel):
    selected_id: Optional[str] = None


def _normalize_name(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", value.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _safe_node_id(entity_type: str, canonical_name: str) -> str:
    norm = _normalize_name(canonical_name).replace(" ", "_")
    return f"{entity_type}.{norm}" if norm else f"{entity_type}.unknown"


def _escape_cypher(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


class GraphContextualizer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.conn = psycopg2.connect(**settings.db.as_psycopg_kwargs())
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        init_age(self.cur, self.conn, settings)

    def close(self) -> None:
        try:
            self.cur.close()
        finally:
            self.conn.close()

    def _embed_text(self, text: str) -> List[float]:
        provider = self.settings.memory.embedding_provider
        if provider == "openai":
            emb = OpenAIEmbeddings(
                model=self.settings.memory.embedding_model,
                openai_api_key=self.settings.llm.openai_api_key,
            )
            return emb.embed_query(text)
        if provider == "azure_openai":
            emb = AzureOpenAIEmbeddings(
                model=self.settings.memory.embedding_model,
                azure_deployment=self.settings.llm.azure_deployment,
                azure_endpoint=self.settings.llm.azure_endpoint,
                openai_api_key=self.settings.llm.azure_api_key,
                openai_api_version=self.settings.llm.azure_api_version,
            )
            return emb.embed_query(text)
        return [0.0 for _ in range(self.settings.memory.embedding_dimensions)]

    def _recognize_entities(self, content: str) -> List[EntityCandidate]:
        llm = create_llm(self.settings)
        structured = llm.with_structured_output(_EntityListOut)
        prompt = (
            "Extract entities from the text. Allowed entity_type values only: "
            + ", ".join(sorted(ENTITY_TYPES))
            + ". Return JSON schema output only."
        )
        out = structured.invoke(f"{prompt}\n\nText:\n{content}")
        entities = [
            EntityCandidate(
                surface_form=e.surface_form,
                entity_type=e.entity_type,
                confidence=float(e.confidence),
            )
            for e in out.entities
            if e.entity_type in ENTITY_TYPES and e.confidence >= self.settings.contextualization.confidence_threshold
        ]
        entities.sort(key=lambda e: e.confidence, reverse=True)
        return entities[: self.settings.contextualization.max_entities_per_item]

    def _resolve_exact(self, surface_form: str, entity_type: str) -> Optional[str]:
        normalized = _normalize_name(surface_form)
        if not normalized:
            return None
        self.cur.execute(
            """
            SELECT memory_id::text AS memory_id, chunk_text
            FROM memory_chunks
            WHERE chunk_text IS NOT NULL
              AND LOWER(REGEXP_REPLACE(chunk_text, '[^a-zA-Z0-9\\s]', ' ', 'g')) = %s
            LIMIT 1;
            """,
            (normalized,),
        )
        row = self.cur.fetchone()
        if not row:
            return None
        return _safe_node_id(entity_type, row["chunk_text"])

    def _resolve_by_embedding(self, surface_form: str, entity_type: str) -> Optional[str]:
        query_vec = self._embed_text(surface_form)
        vector_literal = "[" + ",".join(f"{v:.8f}" for v in query_vec) + "]"
        self.cur.execute(
            """
            SELECT mc.chunk_text, (me.embedding <-> %s::vector) AS distance
            FROM memory_embeddings me
            JOIN memory_chunks mc ON mc.chunk_id = me.chunk_id
            WHERE me.model_name = 'entity_canonical'
            ORDER BY distance ASC
            LIMIT 1;
            """,
            (vector_literal,),
        )
        row = self.cur.fetchone()
        if not row:
            return None
        similarity = 1.0 / (1.0 + float(row["distance"]))
        if similarity < self.settings.contextualization.merge_threshold:
            return None
        return _safe_node_id(entity_type, row["chunk_text"])

    def _resolve_by_llm(
        self,
        surface_form: str,
        entity_type: str,
        candidates: Sequence[str],
    ) -> Optional[str]:
        if not candidates:
            return None
        llm = create_llm(self.settings)
        structured = llm.with_structured_output(_DisambiguationOut)
        prompt = (
            f"Entity type: {entity_type}\n"
            f"Surface form: {surface_form}\n"
            f"Candidates: {list(candidates)}\n"
            "Select one candidate id or null when none match."
        )
        out = structured.invoke(prompt)
        if out.selected_id in candidates:
            return out.selected_id
        return None

    def _resolve_entity(self, candidate: EntityCandidate) -> ResolvedEntity:
        exact = self._resolve_exact(candidate.surface_form, candidate.entity_type)
        if exact:
            return ResolvedEntity(exact, candidate.entity_type, candidate.surface_form, False)

        by_embedding = self._resolve_by_embedding(candidate.surface_form, candidate.entity_type)
        if by_embedding:
            return ResolvedEntity(by_embedding, candidate.entity_type, candidate.surface_form, False)

        resolved = None
        if candidate.confidence > self.settings.contextualization.confidence_threshold:
            resolved = self._resolve_by_llm(candidate.surface_form, candidate.entity_type, [by_embedding] if by_embedding else [])
        if resolved:
            return ResolvedEntity(resolved, candidate.entity_type, candidate.surface_form, False)

        return ResolvedEntity(
            _safe_node_id(candidate.entity_type, candidate.surface_form),
            candidate.entity_type,
            candidate.surface_form,
            True,
        )

    def _infer_relations(
        self,
        memory_id: str,
        content: str,
        resolved_entities: Sequence[ResolvedEntity],
    ) -> List[InferredRelation]:
        llm = create_llm(self.settings)
        structured = llm.with_structured_output(_RelationListOut)
        prompt = (
            "Infer relations using only this set: "
            + ", ".join(sorted(RELATION_TYPES))
            + f"\nMemory id: {memory_id}\n"
            + f"Text: {content}\n"
            + f"Entities: {[e.node_id for e in resolved_entities]}"
        )
        out = structured.invoke(prompt)
        relations = []
        for rel in out.relations:
            if rel.relation_type not in RELATION_TYPES:
                continue
            relations.append(
                InferredRelation(
                    source_id=rel.source_id,
                    target_id=rel.target_id,
                    relation_type=rel.relation_type,
                    evidence=rel.evidence,
                )
            )
        return relations

    def _write_to_age(
        self,
        memory_id: str,
        memory_item: Dict[str, Any],
        resolved_entities: Sequence[ResolvedEntity],
        relations: Sequence[InferredRelation],
    ) -> None:
        try:
            memory_content = _escape_cypher(memory_item["content"])
            self.cur.execute(
                f"""
                SELECT * FROM cypher('{self.settings.graph_name}', $$
                    MERGE (m:Memory {{id: '{_escape_cypher(memory_id)}'}})
                    SET m.kind = '{_escape_cypher(memory_item['kind'])}',
                        m.content = '{memory_content}'
                    RETURN m
                $$) AS (v agtype);
                """
            )
            for ent in resolved_entities:
                self.cur.execute(
                    f"""
                    SELECT * FROM cypher('{self.settings.graph_name}', $$
                        MERGE (e:Entity:{ent.entity_type.title()} {{id: '{_escape_cypher(ent.node_id)}'}})
                        SET e.canonical_name = '{_escape_cypher(ent.canonical_name)}',
                            e.entity_type = '{_escape_cypher(ent.entity_type)}'
                        RETURN e
                    $$) AS (v agtype);
                    """
                )
                create_link(
                    self.cur,
                    memory_id=memory_id,
                    relation_type="mentions",
                    evidence=f"entity:{ent.node_id}",
                    linked_memory_id=None,
                )
                if ent.created:
                    chunk_id = create_chunk(self.cur, memory_id, 999999, ent.canonical_name)
                    create_embedding(
                        self.cur,
                        memory_id=memory_id,
                        chunk_id=chunk_id,
                        model_name="entity_canonical",
                        values=self._embed_text(ent.canonical_name),
                    )

            for rel in relations:
                self.cur.execute(
                    f"""
                    SELECT * FROM cypher('{self.settings.graph_name}', $$
                        MATCH (a {{id: '{_escape_cypher(rel.source_id)}'}})
                        MATCH (b {{id: '{_escape_cypher(rel.target_id)}'}})
                        MERGE (a)-[r:{rel.relation_type.upper()}]->(b)
                        RETURN r
                    $$) AS (v agtype);
                    """
                )
                create_link(
                    self.cur,
                    memory_id=memory_id,
                    relation_type=rel.relation_type,
                    evidence=rel.evidence,
                    linked_memory_id=rel.target_id if re.fullmatch(r"[0-9a-fA-F-]{36}", rel.target_id) else None,
                )

            self.conn.commit()
            set_contextualized_at(self.cur, self.conn, memory_id)
        except Exception:
            self.conn.rollback()
            raise

    def run(self, memory_id: str) -> None:
        item = get_memory_item_by_id(self.cur, memory_id)
        if not item:
            raise ValueError(f"memory item not found: {memory_id}")
        words = item["content"].split()
        if len(words) < 10:
            set_contextualization_skipped(self.cur, self.conn, memory_id)
            return

        try:
            entities = self._recognize_entities(item["content"])
            resolved = [self._resolve_entity(entity) for entity in entities]
            relations = self._infer_relations(memory_id, item["content"], resolved)
            self._write_to_age(memory_id, item, resolved, relations)
        except Exception as exc:
            LOG.exception("Contextualization failed for memory_id=%s: %s", memory_id, exc)


class ContextualizationDispatcher:
    _semaphore = threading.BoundedSemaphore(value=4)

    def __init__(self, cur, conn, settings: Settings):
        self.cur = cur
        self.conn = conn
        self.settings = settings

    def dispatch(self, memory_ids: List[str]) -> ContextualizeJobResponse:
        if not self.settings.contextualization.enabled:
            return ContextualizeJobResponse(job_id="", queued_count=0, status="queued")
        if not memory_ids:
            return ContextualizeJobResponse(job_id="", queued_count=0, status="queued")

        job_id = create_contextualization_job(self.cur, self.conn, memory_ids)
        worker = threading.Thread(target=self._run_job, args=(job_id, memory_ids), daemon=True)
        worker.start()
        return ContextualizeJobResponse(job_id=job_id, queued_count=len(memory_ids), status="queued")

    def _run_job(self, job_id: str, memory_ids: Sequence[str]) -> None:
        with self._semaphore:
            conn = psycopg2.connect(**self.settings.db.as_psycopg_kwargs())
            cur = conn.cursor(cursor_factory=RealDictCursor)
            contextualizer: Optional[GraphContextualizer] = None
            try:
                update_job_status(cur, conn, job_id, "running")
                contextualizer = GraphContextualizer(self.settings)
                counts = {"entities": 0, "relations": 0, "nodes_created": 0, "nodes_merged": 0}
                for memory_id in memory_ids:
                    contextualizer.run(memory_id)
                update_job_status(cur, conn, job_id, "done", result=counts)
            except Exception as exc:
                update_job_status(cur, conn, job_id, "failed", error=str(exc))
            finally:
                if contextualizer is not None:
                    contextualizer.close()
                cur.close()
                conn.close()


def contextualize_n(cur, conn, settings: Settings, n: int) -> ContextualizeJobResponse:
    if not settings.contextualization.enabled:
        return ContextualizeJobResponse(job_id="", queued_count=0, status="queued")
    eligible = get_eligible_for_contextualization(cur, n)
    if not eligible:
        return ContextualizeJobResponse(job_id="", queued_count=0, status="queued")
    dispatcher = ContextualizationDispatcher(cur, conn, settings)
    return dispatcher.dispatch(eligible)


def contextualize_ids(cur, conn, settings: Settings, ids: List[str]) -> ContextualizeJobResponse:
    if not settings.contextualization.enabled:
        return ContextualizeJobResponse(job_id="", queued_count=0, status="queued")
    existing = get_existing_memory_ids(cur, ids)
    if not existing:
        return ContextualizeJobResponse(job_id="", queued_count=0, status="queued")
    dispatcher = ContextualizationDispatcher(cur, conn, settings)
    return dispatcher.dispatch(existing)


def get_job_status(cur, job_id: str) -> Optional[Dict[str, Any]]:
    return get_contextualization_job(cur, job_id)
