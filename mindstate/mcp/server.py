from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

import psycopg2
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool

from ..config import Settings, get_settings
from ..db import connect_db, init_age
from ..memory_service import EmbeddingUnavailableError, MindStateService, ValidationError
from .tools import TOOL_HANDLERS

LOG = logging.getLogger("mindstate.mcp")


class MCPServer:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.conn = None
        self.cur = None
        self.service: Optional[MindStateService] = None
        self._tool_lock = threading.Lock()
        self.handlers = self._build_handlers()
        self.app = self._build_app()

    def _build_handlers(self) -> Dict[str, Callable[[Any, Dict[str, Any]], Dict[str, Any]]]:
        enabled = self.settings.mcp.enabled_tools
        if enabled is None:
            return dict(TOOL_HANDLERS)
        return {name: fn for name, fn in TOOL_HANDLERS.items() if name in enabled}

    def _connect(self) -> None:
        self.conn, self.cur = connect_db(self.settings)
        init_age(self.cur, self.conn, self.settings)
        self.service = MindStateService(cur=self.cur, conn=self.conn, settings=self.settings)

    def _ensure_connected(self) -> None:
        if self.conn is None or self.cur is None or self.service is None:
            self._connect()
            return
        try:
            self.cur.execute("SELECT 1;")
            self.conn.commit()
        except psycopg2.OperationalError:
            try:
                self.cur.close()
            except Exception:
                pass
            try:
                self.conn.close()
            except Exception:
                pass
            self._connect()

    def list_tools(self) -> list[str]:
        return sorted(self.handlers.keys())

    def _build_app(self) -> FastMCP:
        app = FastMCP(
            name="MindState",
            instructions=(
                "MindState exposes memory-oriented tools for storing, recalling, contextualizing, "
                "and inspecting project knowledge. Prefer read-only tools when gathering context, "
                "and use write tools only when you need to persist new memory or session state."
            ),
        )

        tool_methods = {
            "remember": self.remember_tool,
            "recall": self.recall_tool,
            "build_context": self.build_context_tool,
            "contextualize": self.contextualize_tool,
            "log_work_session": self.log_work_session_tool,
            "find_related_code": self.find_related_code_tool,
            "get_recent_project_state": self.get_recent_project_state_tool,
        }
        for name, method in tool_methods.items():
            if name in self.handlers:
                app.add_tool(method)
        return app

    def _error(self, message: str, code: str = "tool_error") -> Dict[str, Any]:
        return {"ok": False, "error": {"code": code, "message": message}}

    def _dispatch_tool(self, tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        started = time.perf_counter()
        agent = payload.get("source_agent") or "unknown"
        side_effects: Dict[str, Any] = {}
        success = False
        try:
            with self._tool_lock:
                self._ensure_connected()
                fn = self.handlers.get(tool_name)
                if fn is None:
                    raise ValueError(f"unknown tool: {tool_name}")
                assert self.service is not None
                data = fn(self.service, payload)
                if isinstance(data, dict):
                    for key in ("memory_id", "job_id", "session_memory_id"):
                        if key in data:
                            side_effects[key] = data[key]
                success = True
                return data
        except Exception as exc:
            LOG.exception("mcp_tool_failed", extra={"tool": tool_name, "agent": agent})
            raise exc
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            LOG.info(
                "mcp_tool_call",
                extra={
                    "tool": tool_name,
                    "agent": agent,
                    "success": success,
                    "duration_ms": duration_ms,
                    "side_effects": side_effects,
                },
            )

    def call_tool(self, tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return {"ok": True, "data": self._dispatch_tool(tool_name, payload)}
        except ValidationError as exc:
            return self._error(str(exc), code="validation_error")
        except EmbeddingUnavailableError as exc:
            return self._error(str(exc), code="embedding_unavailable")
        except ValueError as exc:
            code = "unknown_tool" if str(exc).startswith("unknown tool:") else "validation_error"
            return self._error(str(exc), code=code)
        except Exception as exc:
            return self._error(str(exc), code="internal_error")

    def close(self) -> None:
        with self._tool_lock:
            if self.cur is not None:
                try:
                    self.cur.close()
                except Exception:
                    pass
                self.cur = None
            if self.conn is not None:
                try:
                    self.conn.close()
                except Exception:
                    pass
                self.conn = None
            self.service = None

    def _run_fastmcp_tool(self, tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self._dispatch_tool(tool_name, payload)
        except (ValidationError, EmbeddingUnavailableError, ValueError) as exc:
            raise ToolError(str(exc)) from exc
        except Exception as exc:
            raise ToolError(str(exc)) from exc

    @tool(
        name="remember",
        annotations={"title": "Remember", "openWorldHint": False},
    )
    def remember_tool(
        self,
        kind: str,
        content: str,
        content_format: str = "text/plain",
        source: str | None = None,
        author: str | None = None,
        metadata: dict[str, Any] | None = None,
        provenance_anchor: str | None = None,
        source_agent: str | None = None,
        contextualize: bool = False,
    ) -> Dict[str, Any]:
        """Store a typed memory item in MindState."""
        return self._run_fastmcp_tool(
            "remember",
            {
                "kind": kind,
                "content": content,
                "content_format": content_format,
                "source": source,
                "author": author,
                "metadata": metadata or {},
                "provenance_anchor": provenance_anchor,
                "source_agent": source_agent,
                "contextualize": contextualize,
            },
        )

    @tool(
        name="recall",
        annotations={"title": "Recall", "readOnlyHint": True, "openWorldHint": False},
    )
    def recall_tool(
        self,
        query: str,
        limit: int = 10,
        kind: str | None = None,
        source: str | None = None,
    ) -> Dict[str, Any]:
        """Semantically retrieve ranked memory items."""
        return self._run_fastmcp_tool(
            "recall",
            {"query": query, "limit": limit, "kind": kind, "source": source},
        )

    @tool(
        name="build_context",
        annotations={"title": "Build Context", "readOnlyHint": True, "openWorldHint": False},
    )
    def build_context_tool(
        self,
        query: str,
        limit: int = 10,
        kind: str | None = None,
        source: str | None = None,
    ) -> Dict[str, Any]:
        """Build a bounded context bundle for a task or query."""
        return self._run_fastmcp_tool(
            "build_context",
            {"query": query, "limit": limit, "kind": kind, "source": source},
        )

    @tool(
        name="contextualize",
        annotations={"title": "Contextualize", "openWorldHint": False},
    )
    def contextualize_tool(self, n: int | None = None, ids: list[str] | None = None) -> Dict[str, Any]:
        """Trigger contextualization for recent or specified memory items."""
        return self._run_fastmcp_tool("contextualize", {"n": n, "ids": ids})

    @tool(
        name="log_work_session",
        annotations={"title": "Log Work Session", "openWorldHint": False},
    )
    def log_work_session_tool(
        self,
        repo: str,
        branch: str,
        task: str,
        summary: str,
        decisions: list[str] | None = None,
        resolved_blockers: list[str] | None = None,
        files_changed: list[str] | None = None,
        next_steps: list[str] | None = None,
        source_agent: str | None = None,
        contextualize_session: bool = False,
    ) -> Dict[str, Any]:
        """Store a structured work session and its child memory items."""
        return self._run_fastmcp_tool(
            "log_work_session",
            {
                "repo": repo,
                "branch": branch,
                "task": task,
                "summary": summary,
                "decisions": decisions or [],
                "resolved_blockers": resolved_blockers or [],
                "files_changed": files_changed or [],
                "next_steps": next_steps or [],
                "source_agent": source_agent,
                "contextualize_session": contextualize_session,
            },
        )

    @tool(
        name="find_related_code",
        annotations={"title": "Find Related Code", "readOnlyHint": True, "openWorldHint": False},
    )
    def find_related_code_tool(self, repo: str, symbol: str, branch: str | None = None) -> Dict[str, Any]:
        """Look up related code memories for a repository symbol or concept."""
        return self._run_fastmcp_tool(
            "find_related_code",
            {"repo": repo, "symbol": symbol, "branch": branch},
        )

    @tool(
        name="get_recent_project_state",
        annotations={"title": "Get Recent Project State", "readOnlyHint": True, "openWorldHint": False},
    )
    def get_recent_project_state_tool(self, repo: str) -> Dict[str, Any]:
        """Fetch recent summaries, decisions, and blockers for a repository."""
        return self._run_fastmcp_tool("get_recent_project_state", {"repo": repo})

    def start(self) -> None:
        self._ensure_connected()
        transport = self.settings.mcp.transport
        try:
            if transport == "stdio":
                self.app.run()
                return
            if transport in {"sse", "http"}:
                self.app.run(transport=transport, host=self.settings.mcp.host, port=self.settings.mcp.port)
                return
            raise ValueError(f"unsupported MCP transport: {transport}")
        finally:
            self.close()


def start() -> None:
    MCPServer().start()
