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
