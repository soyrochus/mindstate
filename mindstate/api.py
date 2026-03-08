from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

from .config import get_settings
from .db import connect_db, init_age
from .memory_models import ContextBuildInput, RecallInput, RememberInput, WorkSessionInput
from .memory_service import EmbeddingUnavailableError, MindStateService, ValidationError


class RememberRequest(BaseModel):
    kind: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    content_format: str = "text/plain"
    source: Optional[str] = None
    author: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    provenance_anchor: Optional[str] = None
    occurred_at: Optional[datetime] = None
    contextualize: bool = False


class RememberResponse(BaseModel):
    memory: Dict[str, Any]
    chunk_count: int
    embedding_count: int


class RecallRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=100)
    kind: Optional[str] = None
    source: Optional[str] = None


class RecallItem(BaseModel):
    memory_id: str
    kind: str
    content: str
    source: Optional[str] = None
    author: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    provenance_anchor: Optional[str] = None
    score: float


class RecallResponse(BaseModel):
    items: List[RecallItem]


class ContextBuildRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
    kind: Optional[str] = None
    source: Optional[str] = None


class ContextBuildResponse(BaseModel):
    overview: str
    supporting_items: List[RecallItem]
    linked_records: List[Dict[str, Any]]
    provenance_references: List[Dict[str, Any]]


class ContextualizeRequest(BaseModel):
    n: Optional[int] = Field(default=None, ge=1)
    ids: Optional[List[str]] = None

    @model_validator(mode="after")
    def validate_exactly_one_mode(self) -> "ContextualizeRequest":
        has_n = self.n is not None
        has_ids = self.ids is not None
        if has_n == has_ids:
            raise ValueError("exactly one of n or ids must be provided")
        if self.ids is not None and len(self.ids) == 0:
            raise ValueError("ids must not be empty")
        return self


class ContextualizeJobResponseModel(BaseModel):
    job_id: str
    queued_count: int
    status: str


class ContextualizeJobStatusModel(BaseModel):
    job_id: str
    status: str
    queued_count: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class WorkSessionRequest(BaseModel):
    repo: str = Field(..., min_length=1)
    branch: str = Field(..., min_length=1)
    task: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    decisions: List[str] = Field(default_factory=list)
    resolved_blockers: List[str] = Field(default_factory=list)
    files_changed: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    source_agent: Optional[str] = None
    contextualize_session: bool = False


class WorkSessionResponse(BaseModel):
    session_memory_id: str
    decision_memory_ids: List[str]
    resolved_blocker_memory_ids: List[str]


# Reserved extension-point request models for adjacent first-wave endpoints.
class MemoryLookupRequest(BaseModel):
    memory_id: str


class RelatedMemoryRequest(BaseModel):
    memory_id: str
    limit: int = Field(default=10, ge=1, le=100)


def get_service() -> Generator[MindStateService, None, None]:
    settings = get_settings()
    try:
        conn, cur = connect_db(settings)
        init_age(cur, conn, settings)
        service = MindStateService(cur=cur, conn=conn, settings=settings)
        yield service
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc
    finally:
        try:
            cur.close()  # type: ignore[name-defined]
        except Exception:
            pass
        try:
            conn.close()  # type: ignore[name-defined]
        except Exception:
            pass


def create_app() -> FastAPI:
    app = FastAPI(title="MindState API", version="1.0")

    @app.post("/v1/memory/remember", response_model=RememberResponse)
    def remember(request: RememberRequest, service: MindStateService = Depends(get_service)) -> RememberResponse:
        try:
            payload = RememberInput(
                kind=request.kind,
                content=request.content,
                content_format=request.content_format,
                source=request.source,
                author=request.author,
                metadata=request.metadata,
                provenance_anchor=request.provenance_anchor,
                occurred_at=request.occurred_at,
            )
            try:
                result = service.remember(payload, contextualize=request.contextualize)
            except TypeError:
                result = service.remember(payload)
            return RememberResponse(**result)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EmbeddingUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/v1/memory/recall", response_model=RecallResponse)
    def recall(request: RecallRequest, service: MindStateService = Depends(get_service)) -> RecallResponse:
        try:
            items = service.recall(
                RecallInput(
                    query=request.query,
                    limit=request.limit,
                    kind=request.kind,
                    source=request.source,
                )
            )
            return RecallResponse(items=[RecallItem(**asdict(item)) for item in items])
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EmbeddingUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/v1/context/build", response_model=ContextBuildResponse)
    def build_context(
        request: ContextBuildRequest, service: MindStateService = Depends(get_service)
    ) -> ContextBuildResponse:
        try:
            bundle = service.build_context(
                ContextBuildInput(
                    query=request.query,
                    limit=request.limit,
                    kind=request.kind,
                    source=request.source,
                )
            )
            return ContextBuildResponse(
                overview=bundle.overview,
                supporting_items=[RecallItem(**asdict(item)) for item in bundle.supporting_items],
                linked_records=bundle.linked_records,
                provenance_references=bundle.provenance_references,
            )
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EmbeddingUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/v1/memory/lookup")
    def memory_lookup(_: MemoryLookupRequest) -> Dict[str, str]:
        raise HTTPException(status_code=501, detail="reserved extension point")

    @app.post("/v1/memory/related")
    def related_memory(_: RelatedMemoryRequest) -> Dict[str, str]:
        raise HTTPException(status_code=501, detail="reserved extension point")

    @app.post("/v1/memory/contextualize", response_model=ContextualizeJobResponseModel)
    def contextualize(
        request: ContextualizeRequest,
        service: MindStateService = Depends(get_service),
    ) -> ContextualizeJobResponseModel:
        try:
            if request.n is not None:
                job = service.contextualize_n(request.n)
            else:
                job = service.contextualize_ids(request.ids or [])
            payload = asdict(job) if is_dataclass(job) else dict(vars(job))
            return ContextualizeJobResponseModel(**payload)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/v1/memory/contextualize/{job_id}", response_model=ContextualizeJobStatusModel)
    def get_contextualize_job(
        job_id: str,
        service: MindStateService = Depends(get_service),
    ) -> ContextualizeJobStatusModel:
        try:
            job = service.get_contextualization_job(job_id)
            if not job:
                raise HTTPException(status_code=404, detail="job not found")
            return ContextualizeJobStatusModel(**job)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/memory/work-session", response_model=WorkSessionResponse)
    def log_work_session(
        request: WorkSessionRequest,
        service: MindStateService = Depends(get_service),
    ) -> WorkSessionResponse:
        try:
            result = service.log_work_session(
                WorkSessionInput(
                    repo=request.repo,
                    branch=request.branch,
                    task=request.task,
                    summary=request.summary,
                    decisions=request.decisions,
                    resolved_blockers=request.resolved_blockers,
                    files_changed=request.files_changed,
                    next_steps=request.next_steps,
                    source_agent=request.source_agent,
                    contextualize_session=request.contextualize_session,
                )
            )
            return WorkSessionResponse(**asdict(result))
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run("mindstate.api:app", host=settings.api.host, port=settings.api.port, reload=False)


if __name__ == "__main__":
    run()
