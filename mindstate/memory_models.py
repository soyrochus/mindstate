from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class RememberInput:
    kind: str
    content: str
    content_format: str = "text/plain"
    source: Optional[str] = None
    author: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    provenance_anchor: Optional[str] = None
    occurred_at: Optional[datetime] = None


@dataclass(frozen=True)
class MemoryItem:
    memory_id: str
    kind: str
    content: str
    content_format: str
    source: Optional[str]
    author: Optional[str]
    metadata: Dict[str, Any]
    provenance_anchor: Optional[str]
    occurred_at: Optional[datetime]
    created_at: datetime
    contextualized_at: Optional[datetime] = None
    contextualization_skipped: bool = False


@dataclass(frozen=True)
class RecallInput:
    query: str
    limit: int
    kind: Optional[str] = None
    source: Optional[str] = None


@dataclass(frozen=True)
class RecallResultItem:
    memory_id: str
    kind: str
    content: str
    source: Optional[str]
    author: Optional[str]
    metadata: Dict[str, Any]
    provenance_anchor: Optional[str]
    score: float


@dataclass(frozen=True)
class ContextBuildInput:
    query: str
    limit: int
    kind: Optional[str] = None
    source: Optional[str] = None


@dataclass(frozen=True)
class ContextBundle:
    overview: str
    supporting_items: List[RecallResultItem]
    linked_records: List[Dict[str, Any]]
    provenance_references: List[Dict[str, Any]]


@dataclass(frozen=True)
class ContextualizeInput:
    n: Optional[int] = None
    ids: Optional[List[str]] = None

    def __post_init__(self) -> None:
        has_n = self.n is not None
        has_ids = self.ids is not None
        if has_n == has_ids:
            raise ValueError("exactly one of n or ids must be provided")
        if self.n is not None and self.n < 1:
            raise ValueError("n must be >= 1")
        if self.ids is not None and len(self.ids) == 0:
            raise ValueError("ids must not be empty")


@dataclass(frozen=True)
class ContextualizeJobResponse:
    job_id: str
    queued_count: int
    status: str


@dataclass(frozen=True)
class ContextualizeJobStatus:
    job_id: str
    status: str
    queued_count: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error: Optional[str]
    result: Optional[Dict[str, Any]]


@dataclass(frozen=True)
class WorkSessionInput:
    repo: str
    branch: str
    task: str
    summary: str
    decisions: List[str]
    resolved_blockers: List[str]
    files_changed: List[str]
    next_steps: List[str]
    source_agent: Optional[str]
    contextualize_session: bool = False

    def __init__(
        self,
        repo: str,
        branch: str,
        task: str,
        summary: str,
        decisions: Optional[List[str]] = None,
        resolved_blockers: Optional[List[str]] = None,
        files_changed: Optional[List[str]] = None,
        next_steps: Optional[List[str]] = None,
        source_agent: Optional[str] = None,
        contextualize_session: bool = False,
    ):
        object.__setattr__(self, "repo", repo)
        object.__setattr__(self, "branch", branch)
        object.__setattr__(self, "task", task)
        object.__setattr__(self, "summary", summary)
        object.__setattr__(self, "decisions", decisions or [])
        object.__setattr__(self, "resolved_blockers", resolved_blockers or [])
        object.__setattr__(self, "files_changed", files_changed or [])
        object.__setattr__(self, "next_steps", next_steps or [])
        object.__setattr__(self, "source_agent", source_agent)
        object.__setattr__(self, "contextualize_session", contextualize_session)


@dataclass(frozen=True)
class WorkSessionResult:
    session_memory_id: str
    decision_memory_ids: List[str]
    resolved_blocker_memory_ids: List[str]
