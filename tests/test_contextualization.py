from dataclasses import replace
from datetime import UTC, datetime

from mindstate.config import get_settings
from mindstate.memory_db import get_eligible_for_contextualization
from mindstate.memory_models import ContextBuildInput, MemoryItem, RecallInput, RecallResultItem, RememberInput
from mindstate.memory_service import MindStateService


class FakeCursor:
    def __init__(self):
        self.executed = []
        self._rows = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self._rows


class FakeConn:
    pass


def test_contextualization_settings_defaults_and_env_overrides(monkeypatch):
    for key in [
        "MS_CONTEXTUALIZE_ENABLED",
        "MS_AUTO_CONTEXTUALIZE_KINDS",
        "MS_CONTEXTUALIZE_CONFIDENCE_THRESHOLD",
        "MS_CONTEXTUALIZE_MERGE_THRESHOLD",
        "MS_CONTEXTUALIZE_MAX_ENTITIES_PER_ITEM",
    ]:
        monkeypatch.delenv(key, raising=False)

    default_settings = get_settings()
    assert default_settings.contextualization.enabled is True
    assert default_settings.contextualization.auto_kinds == {
        "decision",
        "architecture_note",
        "resolved_blocker",
        "task",
        "observation",
        "claim",
    }
    assert default_settings.contextualization.confidence_threshold == 0.85
    assert default_settings.contextualization.merge_threshold == 0.92
    assert default_settings.contextualization.max_entities_per_item == 12

    monkeypatch.setenv("MS_CONTEXTUALIZE_ENABLED", "false")
    monkeypatch.setenv("MS_AUTO_CONTEXTUALIZE_KINDS", "note,summary")
    monkeypatch.setenv("MS_CONTEXTUALIZE_CONFIDENCE_THRESHOLD", "0.7")
    monkeypatch.setenv("MS_CONTEXTUALIZE_MERGE_THRESHOLD", "0.95")
    monkeypatch.setenv("MS_CONTEXTUALIZE_MAX_ENTITIES_PER_ITEM", "5")

    overridden = get_settings()
    assert overridden.contextualization.enabled is False
    assert overridden.contextualization.auto_kinds == {"note", "summary"}
    assert overridden.contextualization.confidence_threshold == 0.7
    assert overridden.contextualization.merge_threshold == 0.95
    assert overridden.contextualization.max_entities_per_item == 5


def test_get_eligible_for_contextualization_uses_expected_filters_and_ordering():
    cur = FakeCursor()
    cur._rows = [{"memory_id": "b"}, {"memory_id": "a"}]

    ids = get_eligible_for_contextualization(cur, 2)

    assert ids == ["b", "a"]
    sql = cur.executed[0][0].lower()
    assert "contextualized_at is null" in sql
    assert "contextualization_skipped = false" in sql
    assert "order by created_at desc" in sql


def test_remember_auto_kind_and_explicit_contextualize_enqueue(monkeypatch):
    settings = get_settings()
    settings = replace(
        settings,
        memory=replace(settings.memory, embedding_provider="local", embedding_dimensions=8),
        contextualization=replace(settings.contextualization, enabled=True, auto_kinds={"decision"}),
    )
    enqueued = []

    class _Dispatcher:
        def __init__(self, *_args, **_kwargs):
            pass

        def dispatch(self, memory_ids):
            enqueued.append(list(memory_ids))
            return type("Job", (), {"job_id": "job", "queued_count": len(memory_ids), "status": "queued"})()

    monkeypatch.setattr("mindstate.memory_service.ContextualizationDispatcher", _Dispatcher)
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
    monkeypatch.setattr("mindstate.memory_service.create_chunk", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr("mindstate.memory_service.create_embedding", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("mindstate.memory_service.create_link", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("mindstate.memory_service.commit", lambda *_: None)

    svc = MindStateService(FakeCursor(), FakeConn(), settings)
    svc.remember(RememberInput(kind="decision", content="This is a sufficiently long decision content for testing."))
    svc.remember(
        RememberInput(kind="note", content="This note should still enqueue when explicit flag is enabled."),
        contextualize=True,
    )

    assert enqueued == [
        ["11111111-1111-1111-1111-111111111111"],
        ["11111111-1111-1111-1111-111111111111"],
    ]


def test_contextualization_master_switch_disables_job_creation(monkeypatch):
    settings = get_settings()
    settings = replace(
        settings,
        memory=replace(settings.memory, embedding_provider="local", embedding_dimensions=8),
        contextualization=replace(settings.contextualization, enabled=False, auto_kinds={"decision"}),
    )
    enqueued = []

    class _Dispatcher:
        def __init__(self, *_args, **_kwargs):
            pass

        def dispatch(self, memory_ids):
            enqueued.append(list(memory_ids))

    monkeypatch.setattr("mindstate.memory_service.ContextualizationDispatcher", _Dispatcher)
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
    monkeypatch.setattr("mindstate.memory_service.create_chunk", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr("mindstate.memory_service.create_embedding", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("mindstate.memory_service.create_link", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("mindstate.memory_service.commit", lambda *_: None)

    svc = MindStateService(FakeCursor(), FakeConn(), settings)
    svc.remember(RememberInput(kind="decision", content="This is a sufficiently long decision content for testing."), contextualize=True)

    assert enqueued == []


def test_regression_remember_recall_build_context_when_not_contextualized(monkeypatch):
    settings = get_settings()
    settings = replace(
        settings,
        memory=replace(settings.memory, embedding_provider="local", embedding_dimensions=8),
        contextualization=replace(settings.contextualization, enabled=True, auto_kinds={"decision"}),
    )
    monkeypatch.setattr("mindstate.memory_service.ensure_memory_schema", lambda *_: None)
    monkeypatch.setattr(
        "mindstate.memory_service.create_memory_item",
        lambda _cur, payload: MemoryItem(
            memory_id="33333333-3333-3333-3333-333333333333",
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
    monkeypatch.setattr("mindstate.memory_service.create_chunk", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr("mindstate.memory_service.create_embedding", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("mindstate.memory_service.create_link", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("mindstate.memory_service.commit", lambda *_: None)
    monkeypatch.setattr(
        "mindstate.memory_service.recall_by_embedding",
        lambda *_args, **_kwargs: [
            RecallResultItem(
                memory_id="33333333-3333-3333-3333-333333333333",
                kind="note",
                content="Remember baseline behavior.",
                source=None,
                author=None,
                metadata={},
                provenance_anchor=None,
                score=0.9,
            )
        ],
    )
    monkeypatch.setattr("mindstate.memory_service.get_links_for_memory_ids", lambda *_args, **_kwargs: [])
    monkeypatch.setattr("mindstate.memory_service.get_recent_decisions", lambda *_args, **_kwargs: [])

    svc = MindStateService(FakeCursor(), FakeConn(), settings, embedder=lambda _texts: [[0.1] * 8])
    stored = svc.remember(RememberInput(kind="note", content="Remember baseline behavior."))
    recalled = svc.recall(RecallInput(query="baseline", limit=3))
    bundle = svc.build_context(ContextBuildInput(query="baseline", limit=3))

    assert stored["memory"]["kind"] == "note"
    assert len(recalled) == 1
    assert "Context built" in bundle.overview
