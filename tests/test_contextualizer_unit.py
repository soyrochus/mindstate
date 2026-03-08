from dataclasses import replace

from mindstate.config import get_settings
from mindstate.contextualizer import EntityCandidate, GraphContextualizer


class _FakeStructured:
    def __init__(self, output):
        self._output = output

    def invoke(self, _prompt):
        return self._output


class _FakeLLM:
    def __init__(self, output):
        self._output = output

    def with_structured_output(self, _schema):
        return _FakeStructured(self._output)


class _Entity:
    def __init__(self, surface_form, entity_type, confidence):
        self.surface_form = surface_form
        self.entity_type = entity_type
        self.confidence = confidence


class _EntityOut:
    def __init__(self, entities):
        self.entities = entities


def _ctx(monkeypatch):
    settings = get_settings()
    settings = replace(
        settings,
        contextualization=replace(settings.contextualization, confidence_threshold=0.85, max_entities_per_item=2),
    )
    ctx = GraphContextualizer.__new__(GraphContextualizer)
    ctx.settings = settings
    ctx.cur = None
    ctx.conn = None
    monkeypatch.setattr("mindstate.contextualizer.create_llm", lambda _settings: _FakeLLM(_EntityOut([])))
    return ctx


def test_graph_contextualizer_entity_recognition_filters_and_caps(monkeypatch):
    ctx = _ctx(monkeypatch)
    output = _EntityOut(
        [
            _Entity("Ada", "person", 0.95),
            _Entity("PostgreSQL", "technology", 0.90),
            _Entity("Low", "topic", 0.10),
            _Entity("BadType", "unknown", 0.99),
        ]
    )
    monkeypatch.setattr("mindstate.contextualizer.create_llm", lambda _settings: _FakeLLM(output))

    entities = ctx._recognize_entities("Ada approved PostgreSQL")

    assert len(entities) == 2
    assert entities[0].surface_form == "Ada"
    assert entities[1].surface_form == "PostgreSQL"


def test_entity_resolution_exact_embedding_fallback_and_new_node(monkeypatch):
    ctx = _ctx(monkeypatch)

    candidate = EntityCandidate(surface_form="Ada Lovelace", entity_type="person", confidence=0.95)

    monkeypatch.setattr(ctx, "_resolve_exact", lambda *_args, **_kwargs: "person.ada_lovelace")
    monkeypatch.setattr(ctx, "_resolve_by_embedding", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ctx, "_resolve_by_llm", lambda *_args, **_kwargs: None)
    exact = ctx._resolve_entity(candidate)
    assert exact.node_id == "person.ada_lovelace"
    assert exact.created is False

    monkeypatch.setattr(ctx, "_resolve_exact", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ctx, "_resolve_by_embedding", lambda *_args, **_kwargs: "person.ada_lovelace")
    emb = ctx._resolve_entity(candidate)
    assert emb.node_id == "person.ada_lovelace"
    assert emb.created is False

    monkeypatch.setattr(ctx, "_resolve_by_embedding", lambda *_args, **_kwargs: None)
    created = ctx._resolve_entity(candidate)
    assert created.node_id.startswith("person.")
    assert created.created is True
