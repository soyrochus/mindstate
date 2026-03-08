from dataclasses import replace
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from mindstate.api import create_app, get_service
from mindstate.config import get_settings
from mindstate.mcp.server import MCPServer
from mindstate.mcp.tools import handle_contextualize, handle_log_work_session, handle_remember
from mindstate.memory_models import (
    ContextBuildInput,
    ContextualizeJobResponse,
    MemoryItem,
    RecallInput,
    RecallResultItem,
    RememberInput,
    WorkSessionInput,
    WorkSessionResult,
)
from mindstate.memory_service import MindStateService


class FakeCursor:
    pass


class FakeConn:
    pass


def _base_settings():
    settings = get_settings()
    return replace(
        settings,
        memory=replace(settings.memory, embedding_provider="local", embedding_dimensions=8),
    )


def test_mcp_settings_defaults_and_overrides(monkeypatch):
    for key in ["MS_MCP_TRANSPORT", "MS_MCP_HOST", "MS_MCP_PORT", "MS_MCP_ENABLED_TOOLS"]:
        monkeypatch.delenv(key, raising=False)

    defaults = get_settings()
    assert defaults.mcp.transport == "stdio"
    assert defaults.mcp.host == "127.0.0.1"
    assert defaults.mcp.port == 8001
    assert defaults.mcp.enabled_tools is None

    monkeypatch.setenv("MS_MCP_TRANSPORT", "sse")
    monkeypatch.setenv("MS_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MS_MCP_PORT", "9000")
    monkeypatch.setenv("MS_MCP_ENABLED_TOOLS", "remember,recall")

    overridden = get_settings()
    assert overridden.mcp.transport == "sse"
    assert overridden.mcp.host == "0.0.0.0"
    assert overridden.mcp.port == 9000
    assert overridden.mcp.enabled_tools == frozenset({"remember", "recall"})


def test_work_session_models_defaults_and_round_trip():
    minimal = WorkSessionInput(repo="r", branch="b", task="t", summary="s")
    assert minimal.decisions == []
    assert minimal.resolved_blockers == []
    assert minimal.files_changed == []
    assert minimal.next_steps == []
    assert minimal.contextualize_session is False

    result = WorkSessionResult(
        session_memory_id="s1",
        decision_memory_ids=["d1", "d2"],
        resolved_blocker_memory_ids=["b1"],
    )
    assert len(result.decision_memory_ids) == 2
    assert len(result.resolved_blocker_memory_ids) == 1


def test_log_work_session_creates_expected_items_and_contextualization_policy(monkeypatch):
    settings = replace(
        _base_settings(),
        contextualization=replace(get_settings().contextualization, enabled=True, auto_kinds={"decision", "resolved_blocker"}),
    )
    created = []

    class _Dispatcher:
        def __init__(self, *_args, **_kwargs):
            pass

        def dispatch(self, ids):
            return ContextualizeJobResponse(job_id=f"job-{ids[0]}", queued_count=1, status="queued")

    def _create_item(_cur, payload):
        idx = len(created) + 1
        created.append(payload)
        return MemoryItem(
            memory_id=f"00000000-0000-0000-0000-{idx:012d}",
            kind=payload.kind,
            content=payload.content,
            content_format=payload.content_format,
            source=payload.source,
            author=payload.author,
            metadata=payload.metadata or {},
            provenance_anchor=payload.provenance_anchor,
            occurred_at=payload.occurred_at,
            created_at=datetime.now(UTC),
        )

    monkeypatch.setattr("mindstate.memory_service.ContextualizationDispatcher", _Dispatcher)
    monkeypatch.setattr("mindstate.memory_service.ensure_memory_schema", lambda *_: None)
    monkeypatch.setattr("mindstate.memory_service.create_memory_item", _create_item)
    monkeypatch.setattr("mindstate.memory_service.create_chunk", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr("mindstate.memory_service.create_embedding", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("mindstate.memory_service.create_link", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("mindstate.memory_service.commit", lambda *_: None)

    svc = MindStateService(FakeCursor(), FakeConn(), settings)
    result = svc.log_work_session(
        WorkSessionInput(
            repo="myrepo",
            branch="main",
            task="auth",
            summary="Session summary",
            decisions=["Use JWT"],
            resolved_blockers=["Redis fixed"],
        )
    )

    assert len(created) == 3
    assert created[0].kind == "work_session"
    assert created[1].kind == "decision"
    assert created[2].kind == "resolved_blocker"
    assert result.session_memory_id
    assert len(result.decision_memory_ids) == 1
    assert len(result.resolved_blocker_memory_ids) == 1


def test_log_work_session_contextualize_session_true(monkeypatch):
    settings = replace(
        _base_settings(),
        contextualization=replace(get_settings().contextualization, enabled=True, auto_kinds={"decision", "resolved_blocker"}),
    )
    dispatch_calls = []

    class _Dispatcher:
        def __init__(self, *_args, **_kwargs):
            pass

        def dispatch(self, ids):
            dispatch_calls.append(list(ids))
            return ContextualizeJobResponse(job_id="job", queued_count=1, status="queued")

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
    svc.log_work_session(
        WorkSessionInput(
            repo="myrepo",
            branch="main",
            task="auth",
            summary="Session summary",
            decisions=[],
            resolved_blockers=[],
            contextualize_session=True,
        )
    )

    assert dispatch_calls != []


def test_find_related_code_and_project_state_shapes(monkeypatch):
    settings = _base_settings()
    monkeypatch.setattr("mindstate.memory_service.ensure_memory_schema", lambda *_: None)
    monkeypatch.setattr(
        "mindstate.memory_service.recall_by_embedding",
        lambda *_args, **_kwargs: [
            RecallResultItem(
                memory_id="m1",
                kind="note",
                content="ConnectionPool usage",
                source="repo",
                author=None,
                metadata={},
                provenance_anchor=None,
                score=0.9,
            )
        ],
    )
    monkeypatch.setattr("mindstate.memory_service.get_recent_decisions", lambda *_args, **_kwargs: [{"memory_id": "d1"}])
    monkeypatch.setattr("mindstate.memory_service.get_recent_items_by_kind", lambda *_args, **_kwargs: [{"memory_id": "x"}])

    svc = MindStateService(FakeCursor(), FakeConn(), settings, embedder=lambda _texts: [[0.1] * 8])
    related = svc.find_related_code(repo="repo", symbol="ConnectionPool")
    state = svc.get_recent_project_state("repo")

    assert "items" in related and "decisions" in related
    assert "summaries" in state and "decisions" in state and "open_blockers" in state


class _ApiFakeService:
    def log_work_session(self, _payload):
        return WorkSessionResult(
            session_memory_id="session-1",
            decision_memory_ids=["decision-1"],
            resolved_blocker_memory_ids=["blocker-1"],
        )


def test_api_work_session_endpoint_shape():
    app = create_app()

    def _override():
        yield _ApiFakeService()

    app.dependency_overrides[get_service] = _override
    client = TestClient(app)
    response = client.post(
        "/v1/memory/work-session",
        json={
            "repo": "myrepo",
            "branch": "main",
            "task": "auth",
            "summary": "summary",
            "decisions": ["Use JWT"],
            "resolved_blockers": ["Redis fixed"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["session_memory_id"] == "session-1"
    assert len(body["decision_memory_ids"]) == 1


def test_mcp_tool_handlers_mapping():
    class _Svc:
        def remember(self, payload, contextualize=False):
            return {
                "memory": {"memory_id": "m1"},
                "chunk_count": 1,
                "embedding_count": 1,
                "contextualization_job_id": "j1" if contextualize else None,
            }

        def contextualize_n(self, n):
            return ContextualizeJobResponse(job_id="j2", queued_count=n, status="queued")

        def contextualize_ids(self, ids):
            return ContextualizeJobResponse(job_id="j3", queued_count=len(ids), status="queued")

        def log_work_session(self, payload):
            assert payload.repo == "r"
            return WorkSessionResult("s", ["d"], ["b"])

    svc = _Svc()
    remember = handle_remember(svc, {"kind": "note", "content": "hello", "contextualize": True})
    assert remember["memory_id"] == "m1"

    job_n = handle_contextualize(svc, {"n": 2})
    assert job_n["queued_count"] == 2
    job_ids = handle_contextualize(svc, {"ids": ["a", "b"]})
    assert job_ids["queued_count"] == 2

    session = handle_log_work_session(
        svc,
        {
            "repo": "r",
            "branch": "b",
            "task": "t",
            "summary": "s",
        },
    )
    assert session["session_memory_id"] == "s"


def test_mcp_enabled_tools_filtering(monkeypatch):
    settings = get_settings()
    settings = replace(settings, mcp=replace(settings.mcp, enabled_tools=frozenset({"remember", "recall"})))
    server = MCPServer(settings)
    assert sorted(server.list_tools()) == ["recall", "remember"]


def test_regression_existing_service_methods_unchanged(monkeypatch):
    settings = _base_settings()
    monkeypatch.setattr("mindstate.memory_service.ensure_memory_schema", lambda *_: None)
    monkeypatch.setattr(
        "mindstate.memory_service.create_memory_item",
        lambda _cur, payload: MemoryItem(
            memory_id="m1",
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
                memory_id="m1",
                kind="note",
                content="x",
                source=None,
                author=None,
                metadata={},
                provenance_anchor=None,
                score=0.8,
            )
        ],
    )
    monkeypatch.setattr("mindstate.memory_service.get_links_for_memory_ids", lambda *_args, **_kwargs: [])
    monkeypatch.setattr("mindstate.memory_service.get_recent_decisions", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        "mindstate.memory_service.contextualize_n",
        lambda *_args, **_kwargs: ContextualizeJobResponse(job_id="", queued_count=0, status="queued"),
    )

    svc = MindStateService(FakeCursor(), FakeConn(), settings, embedder=lambda _texts: [[0.1] * 8])
    remembered = svc.remember(RememberInput(kind="note", content="x"))
    recalled = svc.recall(RecallInput(query="x", limit=5))
    context = svc.build_context(ContextBuildInput(query="x", limit=5))
    job = svc.contextualize_n(1)

    assert remembered["memory"]["memory_id"] == "m1"
    assert len(recalled) == 1
    assert "overview" in context.__dict__
    assert hasattr(job, "queued_count")
