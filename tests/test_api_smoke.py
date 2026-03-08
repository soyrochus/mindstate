from fastapi.testclient import TestClient

from mindstate.api import create_app, get_service
from mindstate.memory_models import ContextBundle, RecallResultItem


class InMemoryService:
    def __init__(self):
        self.items = []

    def remember(self, payload):
        memory_id = f"mem-{len(self.items) + 1}"
        item = {"memory_id": memory_id, "kind": payload.kind, "content": payload.content, "source": payload.source}
        self.items.append(item)
        return {"memory": item, "chunk_count": 1, "embedding_count": 1}

    def recall(self, payload):
        matched = [it for it in self.items if payload.query.lower() in it["content"].lower()]
        return [
            RecallResultItem(
                memory_id=it["memory_id"],
                kind=it["kind"],
                content=it["content"],
                source=it.get("source"),
                author=None,
                metadata={},
                provenance_anchor=None,
                score=1.0,
            )
            for it in matched[: payload.limit]
        ]

    def build_context(self, payload):
        recalled = self.recall(payload)
        return ContextBundle(
            overview=f"Context built from {len(recalled)} item(s)",
            supporting_items=recalled,
            linked_records=[],
            provenance_references=[{"memory_id": item.memory_id} for item in recalled],
        )


def test_store_recall_context_smoke_from_same_app_instance():
    service = InMemoryService()
    app = create_app()

    def _override():
        yield service

    app.dependency_overrides[get_service] = _override
    client = TestClient(app)

    stored = client.post("/v1/memory/remember", json={"kind": "note", "content": "MindState stores context-rich memory."})
    assert stored.status_code == 200

    recalled = client.post("/v1/memory/recall", json={"query": "context-rich", "limit": 5})
    assert recalled.status_code == 200
    assert len(recalled.json()["items"]) == 1

    context = client.post("/v1/context/build", json={"query": "context-rich", "limit": 5})
    assert context.status_code == 200
    assert "Context built" in context.json()["overview"]
