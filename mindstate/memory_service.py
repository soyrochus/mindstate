from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import asdict
from typing import Callable, Dict, List, Optional, Sequence

from langchain_openai import AzureOpenAIEmbeddings, OpenAIEmbeddings

from .config import Settings
from .contextualizer import ContextualizationDispatcher, contextualize_ids, contextualize_n, get_job_status
from .memory_db import (
    commit,
    create_chunk,
    create_embedding,
    create_link,
    create_memory_item,
    ensure_memory_schema,
    get_links_for_memory_ids,
    get_memory_item_by_id,
    get_recent_items_by_kind,
    get_recent_decisions,
    recall_by_embedding,
    rollback,
)
from .memory_models import (
    ContextBuildInput,
    ContextBundle,
    ContextualizeJobResponse,
    RecallInput,
    RecallResultItem,
    RememberInput,
    WorkSessionInput,
    WorkSessionResult,
)

LOG = logging.getLogger(__name__)


class MemoryServiceError(Exception):
    pass


class EmbeddingUnavailableError(MemoryServiceError):
    pass


class ValidationError(MemoryServiceError):
    pass


class MindStateService:
    def __init__(
        self,
        cur,
        conn,
        settings: Settings,
        embedder: Optional[Callable[[Sequence[str]], List[List[float]]]] = None,
    ):
        self.cur = cur
        self.conn = conn
        self.settings = settings
        self._embedder = embedder
        self.dispatcher = ContextualizationDispatcher(self.cur, self.conn, self.settings)
        ensure_memory_schema(self.cur, self.conn, self.settings)

    def remember(self, payload: RememberInput, contextualize: bool = False) -> Dict[str, object]:
        if not payload.content.strip():
            raise ValidationError("content is required")
        if not payload.kind.strip():
            raise ValidationError("kind is required")

        chunks = self._chunk_text(payload.content)
        if not chunks:
            raise ValidationError("content produced no chunks")

        try:
            item = create_memory_item(self.cur, payload)
            vectors = self._embed(chunks)
            contextualization_job_id: Optional[str] = None
            for idx, chunk_text in enumerate(chunks):
                chunk_id = create_chunk(self.cur, item.memory_id, idx, chunk_text)
                create_embedding(
                    self.cur,
                    memory_id=item.memory_id,
                    chunk_id=chunk_id,
                    model_name=self.settings.memory.embedding_model,
                    values=vectors[idx],
                )
            self._create_conservative_links(item.memory_id, payload)
            commit(self.conn)
            should_contextualize = (
                self.settings.contextualization.enabled
                and (contextualize or payload.kind in self.settings.contextualization.auto_kinds)
            )
            if should_contextualize:
                try:
                    job = self.dispatcher.dispatch([item.memory_id])
                    contextualization_job_id = job.job_id or None
                except Exception as exc:
                    LOG.exception("Failed to dispatch contextualization for %s: %s", item.memory_id, exc)
            return {
                "memory": asdict(item),
                "chunk_count": len(chunks),
                "embedding_count": len(vectors),
                "contextualization_job_id": contextualization_job_id,
            }
        except EmbeddingUnavailableError:
            rollback(self.conn)
            raise
        except Exception as exc:
            rollback(self.conn)
            raise MemoryServiceError(str(exc)) from exc

    def recall(self, payload: RecallInput) -> List[RecallResultItem]:
        if not payload.query.strip():
            raise ValidationError("query is required")
        if payload.limit < 1:
            raise ValidationError("limit must be >= 1")
        vector = self._embed([payload.query])[0]
        return recall_by_embedding(
            self.cur,
            query_embedding=vector,
            limit=payload.limit,
            kind=payload.kind,
            source=payload.source,
        )

    def build_context(self, payload: ContextBuildInput) -> ContextBundle:
        recalls = self.recall(
            RecallInput(
                query=payload.query,
                limit=payload.limit,
                kind=payload.kind,
                source=payload.source,
            )
        )
        links = get_links_for_memory_ids(self.cur, [item.memory_id for item in recalls])
        recent_decisions = get_recent_decisions(self.cur, limit=min(5, payload.limit))
        provenance = [
            {
                "memory_id": item.memory_id,
                "source": item.source,
                "provenance_anchor": item.provenance_anchor,
            }
            for item in recalls
        ]
        overview = (
            f"Context built for '{payload.query}' using {len(recalls)} supporting memory item(s)."
            if recalls
            else f"No matching memory items found for '{payload.query}'."
        )
        linked_records = links + [{"relation_type": "recent_decision", **d} for d in recent_decisions]
        return ContextBundle(
            overview=overview,
            supporting_items=recalls,
            linked_records=linked_records[: payload.limit],
            provenance_references=provenance[: payload.limit],
        )

    def inspect_memory(self, memory_id: str) -> Optional[Dict[str, object]]:
        if not memory_id:
            raise ValidationError("memory_id is required")
        return get_memory_item_by_id(self.cur, memory_id)

    def contextualize_n(self, n: int = 1) -> ContextualizeJobResponse:
        if n < 1:
            raise ValidationError("n must be >= 1")
        return contextualize_n(self.cur, self.conn, self.settings, n)

    def contextualize_ids(self, ids: List[str]) -> ContextualizeJobResponse:
        if not ids:
            raise ValidationError("ids must not be empty")
        return contextualize_ids(self.cur, self.conn, self.settings, ids)

    def get_contextualization_job(self, job_id: str) -> Optional[Dict[str, object]]:
        if not job_id:
            raise ValidationError("job_id is required")
        return get_job_status(self.cur, job_id)

    def log_work_session(self, payload: WorkSessionInput) -> WorkSessionResult:
        if not payload.repo.strip():
            raise ValidationError("repo is required")
        if not payload.branch.strip():
            raise ValidationError("branch is required")
        if not payload.task.strip():
            raise ValidationError("task is required")
        if not payload.summary.strip():
            raise ValidationError("summary is required")

        session_result = self.remember(
            RememberInput(
                kind="work_session",
                content=payload.summary,
                source=payload.repo,
                author=payload.source_agent,
                metadata={
                    "branch": payload.branch,
                    "task": payload.task,
                    "files_changed": payload.files_changed,
                    "next_steps": payload.next_steps,
                },
            ),
            contextualize=payload.contextualize_session,
        )

        decision_ids: List[str] = []
        for decision in payload.decisions:
            if not decision.strip():
                continue
            result = self.remember(
                RememberInput(
                    kind="decision",
                    content=decision,
                    source=payload.repo,
                    author=payload.source_agent,
                    metadata={"branch": payload.branch, "task": payload.task},
                ),
                contextualize=False,
            )
            decision_ids.append(str(result["memory"]["memory_id"]))

        resolved_blocker_ids: List[str] = []
        for blocker in payload.resolved_blockers:
            if not blocker.strip():
                continue
            result = self.remember(
                RememberInput(
                    kind="resolved_blocker",
                    content=blocker,
                    source=payload.repo,
                    author=payload.source_agent,
                    metadata={"branch": payload.branch, "task": payload.task},
                ),
                contextualize=False,
            )
            resolved_blocker_ids.append(str(result["memory"]["memory_id"]))

        return WorkSessionResult(
            session_memory_id=str(session_result["memory"]["memory_id"]),
            decision_memory_ids=decision_ids,
            resolved_blocker_memory_ids=resolved_blocker_ids,
        )

    def find_related_code(self, repo: str, symbol: str, branch: Optional[str] = None) -> Dict[str, object]:
        if not repo.strip():
            raise ValidationError("repo is required")
        if not symbol.strip():
            raise ValidationError("symbol is required")

        recalls = self.recall(RecallInput(query=symbol, source=repo, limit=10))
        decisions = get_recent_decisions(self.cur, limit=5, source=repo)
        return {"items": [asdict(item) for item in recalls], "decisions": decisions}

    def get_recent_project_state(self, repo: str) -> Dict[str, object]:
        if not repo.strip():
            raise ValidationError("repo is required")

        summaries = get_recent_items_by_kind(self.cur, "summary", source=repo, limit=10)
        decisions = get_recent_items_by_kind(self.cur, "decision", source=repo, limit=10)
        open_blockers = get_recent_items_by_kind(self.cur, "blocker", source=repo, limit=10)
        return {
            "summaries": summaries,
            "decisions": decisions,
            "open_blockers": open_blockers,
        }

    def _chunk_text(self, text: str) -> List[str]:
        chunk_size = max(64, self.settings.memory.chunk_size)
        max_chunks = max(1, self.settings.memory.max_chunks_per_item)
        words = text.split()
        if not words:
            return []
        chunks: List[str] = []
        current: List[str] = []
        current_len = 0
        for word in words:
            addition = len(word) + (1 if current else 0)
            if current_len + addition > chunk_size and current:
                chunks.append(" ".join(current))
                if len(chunks) >= max_chunks:
                    return chunks
                current = [word]
                current_len = len(word)
            else:
                current.append(word)
                current_len += addition
        if current and len(chunks) < max_chunks:
            chunks.append(" ".join(current))
        return chunks

    def _embed(self, texts: Sequence[str]) -> List[List[float]]:
        if self._embedder is not None:
            return self._embedder(texts)
        provider = self.settings.memory.embedding_provider
        if provider == "local":
            return [self._local_embedding(t) for t in texts]
        if provider == "openai":
            if not self.settings.llm.openai_api_key:
                raise EmbeddingUnavailableError(
                    "OpenAI embedding configuration unavailable: OPENAI_API_KEY is missing."
                )
            emb = OpenAIEmbeddings(
                model=self.settings.memory.embedding_model,
                openai_api_key=self.settings.llm.openai_api_key,
            )
            try:
                return emb.embed_documents(list(texts))
            except Exception as exc:
                raise EmbeddingUnavailableError(f"OpenAI embeddings unavailable: {exc}") from exc
        if provider == "azure_openai":
            if not self.settings.llm.azure_api_key or not self.settings.llm.azure_endpoint:
                raise EmbeddingUnavailableError(
                    "Azure embedding configuration unavailable: AZURE_OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT missing."
                )
            emb = AzureOpenAIEmbeddings(
                model=self.settings.memory.embedding_model,
                azure_deployment=self.settings.llm.azure_deployment,
                azure_endpoint=self.settings.llm.azure_endpoint,
                openai_api_key=self.settings.llm.azure_api_key,
                openai_api_version=self.settings.llm.azure_api_version,
            )
            try:
                return emb.embed_documents(list(texts))
            except Exception as exc:
                raise EmbeddingUnavailableError(f"Azure embeddings unavailable: {exc}") from exc
        raise EmbeddingUnavailableError(f"Unsupported embedding provider: {provider}")

    def _local_embedding(self, text: str) -> List[float]:
        dims = self.settings.memory.embedding_dimensions
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: List[float] = []
        for idx in range(dims):
            byte = digest[idx % len(digest)]
            values.append((byte / 255.0) * 2.0 - 1.0)
        return values

    def _create_conservative_links(self, memory_id: str, payload: RememberInput) -> None:
        if payload.provenance_anchor:
            create_link(
                self.cur,
                memory_id=memory_id,
                relation_type="provenance_anchor",
                evidence=payload.provenance_anchor,
                linked_memory_id=None,
            )
        for candidate in set(re.findall(r"memory:([0-9a-fA-F-]{36})", payload.content)):
            create_link(
                self.cur,
                memory_id=memory_id,
                relation_type="references_memory",
                evidence=f"explicit reference memory:{candidate}",
                linked_memory_id=candidate,
            )
