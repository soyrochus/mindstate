from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from ..memory_models import ContextBuildInput, ContextualizeInput, RecallInput, RememberInput, WorkSessionInput


def _require(payload: Dict[str, Any], key: str) -> Any:
    value = payload.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f"{key} is required")
    return value


def handle_remember(svc, payload: Dict[str, Any]) -> Dict[str, Any]:
    kind = _require(payload, "kind")
    content = _require(payload, "content")
    source_agent = payload.get("source_agent")
    author = payload.get("author") or source_agent
    result = svc.remember(
        RememberInput(
            kind=kind,
            content=content,
            content_format=payload.get("content_format", "text/plain"),
            source=payload.get("source"),
            author=author,
            metadata=payload.get("metadata") or {},
            provenance_anchor=payload.get("provenance_anchor"),
        ),
        contextualize=bool(payload.get("contextualize", False)),
    )
    return {
        "memory_id": result["memory"]["memory_id"],
        "chunk_count": result["chunk_count"],
        "embedding_count": result["embedding_count"],
        "contextualization_job_id": result.get("contextualization_job_id"),
    }


def handle_recall(svc, payload: Dict[str, Any]) -> Dict[str, Any]:
    query = _require(payload, "query")
    items = svc.recall(
        RecallInput(
            query=query,
            limit=int(payload.get("limit", 10)),
            kind=payload.get("kind"),
            source=payload.get("source"),
        )
    )
    return {"items": [asdict(item) for item in items]}


def handle_build_context(svc, payload: Dict[str, Any]) -> Dict[str, Any]:
    query = _require(payload, "query")
    bundle = svc.build_context(
        ContextBuildInput(
            query=query,
            limit=int(payload.get("limit", 10)),
            kind=payload.get("kind"),
            source=payload.get("source"),
        )
    )
    return {
        "overview": bundle.overview,
        "supporting_items": [asdict(item) for item in bundle.supporting_items],
        "linked_records": bundle.linked_records,
        "provenance_references": bundle.provenance_references,
    }


def handle_contextualize(svc, payload: Dict[str, Any]) -> Dict[str, Any]:
    n = payload.get("n")
    ids = payload.get("ids")
    ContextualizeInput(n=n, ids=ids)
    if n is not None:
        job = svc.contextualize_n(int(n))
    else:
        job = svc.contextualize_ids(list(ids))
    return {"job_id": job.job_id or None, "queued_count": job.queued_count, "status": job.status}


def handle_log_work_session(svc, payload: Dict[str, Any]) -> Dict[str, Any]:
    result = svc.log_work_session(
        WorkSessionInput(
            repo=_require(payload, "repo"),
            branch=_require(payload, "branch"),
            task=_require(payload, "task"),
            summary=_require(payload, "summary"),
            decisions=list(payload.get("decisions") or []),
            resolved_blockers=list(payload.get("resolved_blockers") or []),
            files_changed=list(payload.get("files_changed") or []),
            next_steps=list(payload.get("next_steps") or []),
            source_agent=payload.get("source_agent"),
            contextualize_session=bool(payload.get("contextualize_session", False)),
        )
    )
    return asdict(result)


def handle_find_related_code(svc, payload: Dict[str, Any]) -> Dict[str, Any]:
    repo = _require(payload, "repo")
    symbol = _require(payload, "symbol")
    return svc.find_related_code(repo=repo, symbol=symbol, branch=payload.get("branch"))


def handle_get_recent_project_state(svc, payload: Dict[str, Any]) -> Dict[str, Any]:
    repo = _require(payload, "repo")
    return svc.get_recent_project_state(repo)


TOOL_HANDLERS = {
    "remember": handle_remember,
    "recall": handle_recall,
    "build_context": handle_build_context,
    "contextualize": handle_contextualize,
    "log_work_session": handle_log_work_session,
    "find_related_code": handle_find_related_code,
    "get_recent_project_state": handle_get_recent_project_state,
}
