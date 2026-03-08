from __future__ import annotations

import hashlib
import re
from dataclasses import asdict
from typing import Callable, Dict, List, Optional, Sequence

from langchain_openai import AzureOpenAIEmbeddings, OpenAIEmbeddings

from .config import Settings
from .memory_db import (
    commit,
    create_chunk,
    create_embedding,
    create_link,
    create_memory_item,
    ensure_memory_schema,
    get_links_for_memory_ids,
    get_memory_item_by_id,
    get_recent_decisions,
    recall_by_embedding,
    rollback,
)
from .memory_models import ContextBuildInput, ContextBundle, RecallInput, RecallResultItem, RememberInput


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
        ensure_memory_schema(self.cur, self.conn, self.settings)

    def remember(self, payload: RememberInput) -> Dict[str, object]:
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
            return {
                "memory": asdict(item),
                "chunk_count": len(chunks),
                "embedding_count": len(vectors),
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
