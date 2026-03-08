from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any, Callable, Dict, Optional

import psycopg2

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
        self.handlers = self._build_handlers()

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

    def _error(self, message: str, code: str = "tool_error") -> Dict[str, Any]:
        return {"ok": False, "error": {"code": code, "message": message}}

    def _observe_and_call(self, tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        started = time.perf_counter()
        agent = payload.get("source_agent") or "unknown"
        side_effects: Dict[str, Any] = {}
        success = False
        try:
            self._ensure_connected()
            fn = self.handlers.get(tool_name)
            if fn is None:
                return self._error(f"unknown tool: {tool_name}", code="unknown_tool")
            assert self.service is not None
            data = fn(self.service, payload)
            if isinstance(data, dict):
                for key in ("memory_id", "job_id", "session_memory_id"):
                    if key in data:
                        side_effects[key] = data[key]
            success = True
            return {"ok": True, "data": data}
        except ValidationError as exc:
            return self._error(str(exc), code="validation_error")
        except EmbeddingUnavailableError as exc:
            return self._error(str(exc), code="embedding_unavailable")
        except ValueError as exc:
            return self._error(str(exc), code="validation_error")
        except Exception as exc:
            return self._error(str(exc), code="internal_error")
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
        return self._observe_and_call(tool_name, payload)

    def start(self) -> None:
        self._ensure_connected()
        if self.settings.mcp.transport == "sse":
            LOG.info("SSE transport requested; stdio fallback is used in this build")

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                print(json.dumps(self._error("invalid json", code="bad_request")), flush=True)
                continue

            action = request.get("action")
            if action == "tools/list":
                print(json.dumps({"ok": True, "data": {"tools": self.list_tools()}}), flush=True)
                continue
            if action == "tools/call":
                tool = request.get("tool")
                payload = request.get("payload") or {}
                print(json.dumps(self.call_tool(tool, payload)), flush=True)
                continue

            print(json.dumps(self._error("unknown action", code="bad_request")), flush=True)


def start() -> None:
    MCPServer().start()
