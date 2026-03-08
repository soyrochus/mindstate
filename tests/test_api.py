from fastapi.testclient import TestClient

from mindstate.api import create_app, get_service
from mindstate.memory_models import ContextBundle, ContextualizeJobResponse, RecallResultItem
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

    def contextualize_n(self, n):
        return ContextualizeJobResponse(job_id="job-1", queued_count=n, status="queued")

    def contextualize_ids(self, ids):
        return ContextualizeJobResponse(job_id="job-2", queued_count=len(ids), status="queued")

    def get_contextualization_job(self, job_id):
        if job_id == "missing":
            return None
        return {
            "job_id": job_id,
            "status": "running",
            "queued_count": 1,
            "started_at": None,
            "completed_at": None,
            "error": None,
            "result": None,
        }


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


def test_contextualize_api_supports_n_and_ids_modes():
    client = _client(_FakeService())
    resp_n = client.post("/v1/memory/contextualize", json={"n": 3})
    assert resp_n.status_code == 200
    assert resp_n.json()["queued_count"] == 3

    resp_ids = client.post(
        "/v1/memory/contextualize",
        json={"ids": ["11111111-1111-1111-1111-111111111111"]},
    )
    assert resp_ids.status_code == 200
    assert resp_ids.json()["queued_count"] == 1


def test_contextualize_api_validates_exactly_one_mode_and_job_lookup():
    client = _client(_FakeService())
    bad = client.post("/v1/memory/contextualize", json={})
    assert bad.status_code == 422

    ok = client.get("/v1/memory/contextualize/job-1")
    assert ok.status_code == 200
    assert ok.json()["status"] == "running"

    missing = client.get("/v1/memory/contextualize/missing")
    assert missing.status_code == 404
