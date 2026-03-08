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
