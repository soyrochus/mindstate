from fastapi.testclient import TestClient

from mindstate.api import create_app, get_service
from mindstate.memory_models import ContextBundle, RecallResultItem
from mindstate.memory_service import EmbeddingUnavailableError


class _FakeService:
    def remember(self, payload):
        return {
            "memory": {"memory_id": "abc", "kind": payload.kind, "content": payload.content},
            "chunk_count": 1,
            "embedding_count": 1,
        }

    def recall(self, _payload):
        return [
            RecallResultItem(
                memory_id="abc",
                kind="note",
                content="sample",
                source="test",
                author="tester",
                metadata={},
                provenance_anchor=None,
                score=0.8,
            )
        ]

    def build_context(self, _payload):
        return ContextBundle(
            overview="Context built",
            supporting_items=self.recall(None),
            linked_records=[{"relation_type": "references_memory"}],
            provenance_references=[{"memory_id": "abc"}],
        )


def _client(service):
    app = create_app()

    def _override():
        yield service

    app.dependency_overrides[get_service] = _override
    return TestClient(app)


def test_remember_request_validation():
    client = _client(_FakeService())
    response = client.post("/v1/memory/remember", json={"kind": "note"})
    assert response.status_code == 422


def test_api_endpoints_use_behavior_models():
    client = _client(_FakeService())
    remember = client.post("/v1/memory/remember", json={"kind": "note", "content": "hello"})
    assert remember.status_code == 200
    assert remember.json()["memory"]["memory_id"] == "abc"

    recall = client.post("/v1/memory/recall", json={"query": "hello"})
    assert recall.status_code == 200
    assert recall.json()["items"][0]["memory_id"] == "abc"

    context = client.post("/v1/context/build", json={"query": "hello"})
    assert context.status_code == 200
    assert "overview" in context.json()


def test_embedding_unavailable_maps_to_503():
    class _FailingService(_FakeService):
        def remember(self, _payload):
            raise EmbeddingUnavailableError("embedding down")

    client = _client(_FailingService())
    response = client.post("/v1/memory/remember", json={"kind": "note", "content": "hello"})
    assert response.status_code == 503
