from dataclasses import replace
from datetime import UTC, datetime

import pytest

from mindstate.config import get_settings
from mindstate.memory_models import ContextBuildInput, MemoryItem, RecallInput, RecallResultItem, RememberInput
from mindstate.memory_service import EmbeddingUnavailableError, MindStateService


class FakeCursor:
    pass


class FakeConn:
    pass


def _test_settings():
    settings = get_settings()
    settings = replace(
        settings,
        memory=replace(
            settings.memory,
            embedding_provider="local",
            embedding_dimensions=8,
            chunk_size=30,
            max_chunks_per_item=8,
            default_recall_limit=5,
        ),
    )
    return settings


def test_remember_creates_canonical_item_and_projections(monkeypatch):
    calls = {"chunks": [], "embeddings": [], "links": 0, "commits": 0}
    settings = _test_settings()

    monkeypatch.setattr("mindstate.memory_service.ensure_memory_schema", lambda *_: None)
    monkeypatch.setattr(
        "mindstate.memory_service.create_memory_item",
        lambda _cur, payload: MemoryItem(
            memory_id="11111111-1111-1111-1111-111111111111",
            kind=payload.kind,
            content=payload.content,
            content_format=payload.content_format,
            source=payload.source,
            author=payload.author,
            metadata=payload.metadata or {},
            provenance_anchor=payload.provenance_anchor,
            occurred_at=payload.occurred_at,
            created_at=datetime.now(UTC),
        ),
    )

    def _create_chunk(_cur, _memory_id, chunk_index, chunk_text):
        calls["chunks"].append((chunk_index, chunk_text))
        return chunk_index + 1

    def _create_embedding(_cur, memory_id, chunk_id, model_name, values):
        calls["embeddings"].append((memory_id, chunk_id, model_name, list(values)))

    monkeypatch.setattr("mindstate.memory_service.create_chunk", _create_chunk)
    monkeypatch.setattr("mindstate.memory_service.create_embedding", _create_embedding)
    monkeypatch.setattr("mindstate.memory_service.create_link", lambda *_args, **_kwargs: calls.__setitem__("links", calls["links"] + 1))
    monkeypatch.setattr("mindstate.memory_service.commit", lambda _conn: calls.__setitem__("commits", calls["commits"] + 1))
    monkeypatch.setattr("mindstate.memory_service.rollback", lambda _conn: None)

    service = MindStateService(FakeCursor(), FakeConn(), settings)
    result = service.remember(
        RememberInput(
            kind="note",
            content="A short memory item to verify chunk and embedding projection creation.",
            provenance_anchor="doc://source",
        )
    )

    assert result["chunk_count"] >= 1
    assert result["embedding_count"] == result["chunk_count"]
    assert len(calls["chunks"]) == result["chunk_count"]
    assert len(calls["embeddings"]) == result["embedding_count"]
    assert calls["links"] >= 1
    assert calls["commits"] == 1


def test_remember_fails_cleanly_when_embeddings_unavailable(monkeypatch):
    settings = get_settings()
    settings = replace(
        settings,
        llm=replace(settings.llm, provider="openai", openai_api_key=None),
        memory=replace(settings.memory, embedding_provider="openai"),
    )
    rolled_back = {"value": False}

    monkeypatch.setattr("mindstate.memory_service.ensure_memory_schema", lambda *_: None)
    monkeypatch.setattr(
        "mindstate.memory_service.create_memory_item",
        lambda _cur, _payload: MemoryItem(
            memory_id="22222222-2222-2222-2222-222222222222",
            kind="note",
            content="x",
            content_format="text/plain",
            source=None,
            author=None,
            metadata={},
            provenance_anchor=None,
            occurred_at=None,
            created_at=datetime.now(UTC),
        ),
    )
    monkeypatch.setattr("mindstate.memory_service.rollback", lambda _conn: rolled_back.__setitem__("value", True))

    service = MindStateService(FakeCursor(), FakeConn(), settings)
    with pytest.raises(EmbeddingUnavailableError):
        service.remember(RememberInput(kind="note", content="This should fail due to embedding config."))
    assert rolled_back["value"] is True


def test_recall_and_context_use_shared_service_semantics(monkeypatch):
    settings = _test_settings()
    monkeypatch.setattr("mindstate.memory_service.ensure_memory_schema", lambda *_: None)
    monkeypatch.setattr(
        "mindstate.memory_service.recall_by_embedding",
        lambda *_args, **_kwargs: [
            RecallResultItem(
                memory_id="33333333-3333-3333-3333-333333333333",
                kind="note",
                content="Remember to ship MVP this week.",
                source="test",
                author="tester",
                metadata={},
                provenance_anchor="src://1",
                score=0.9,
            )
        ],
    )
    monkeypatch.setattr(
        "mindstate.memory_service.get_links_for_memory_ids",
        lambda *_args, **_kwargs: [{"memory_id": "33333333-3333-3333-3333-333333333333", "relation_type": "references_memory"}],
    )
    monkeypatch.setattr(
        "mindstate.memory_service.get_recent_decisions",
        lambda *_args, **_kwargs: [{"memory_id": "444", "kind": "decision", "content": "Ship now"}],
    )

    service = MindStateService(FakeCursor(), FakeConn(), settings, embedder=lambda _texts: [[0.1] * 8])
    recall_items = service.recall(RecallInput(query="ship", limit=3))
    assert len(recall_items) == 1
    bundle = service.build_context(ContextBuildInput(query="ship", limit=3))
    assert "Context built" in bundle.overview
    assert len(bundle.supporting_items) == 1
    assert len(bundle.linked_records) >= 1
