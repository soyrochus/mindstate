from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


class CommandParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedCommand:
    name: str
    args: dict


COMMAND_HELP_LINES: List[str] = [
    r"  \q                                  Quit",
    r"  \h                                  Show this help message",
    r"  \log [on|off]                       Toggle logging",
    r"  \llm [on|off]                       Toggle LLM mode",
    r"  \contextualize [n]                  Queue contextualization for n eligible items (default 1)",
    r"  \contextualize --id <UUID>          Queue contextualization for one memory id",
    r"  \mode [shell|memory]                Switch default input workflow",
    r"  \remember KIND | CONTENT            Store canonical memory",
    r"  \recall QUERY                       Semantic memory recall",
    r"  \context QUERY                      Build bounded context bundle",
    r"  \inspect MEMORY_ID                  Inspect stored memory",
]


def parse_toggle(value: str) -> Optional[bool]:
    val = value.lower()
    if val in {"on", "true"}:
        return True
    if val in {"off", "false"}:
        return False
    return None


def parse_slash_command(text: str) -> ParsedCommand:
    stripped = text.strip()
    if not stripped.startswith("\\"):
        raise CommandParseError("not a command")

    if stripped == "\\q":
        return ParsedCommand(name="quit", args={})
    if stripped == "\\h":
        return ParsedCommand(name="help", args={})

    if stripped.startswith("\\log"):
        parts = stripped.split(maxsplit=1)
        if len(parts) != 2:
            raise CommandParseError(r"Usage: \log [on|off|true|false]")
        toggle = parse_toggle(parts[1])
        if toggle is None:
            raise CommandParseError(r"Usage: \log [on|off|true|false]")
        return ParsedCommand(name="log", args={"enabled": toggle})

    if stripped.startswith("\\llm"):
        parts = stripped.split(maxsplit=1)
        if len(parts) != 2:
            raise CommandParseError(r"Usage: \llm [on|off|true|false]")
        toggle = parse_toggle(parts[1])
        if toggle is None:
            raise CommandParseError(r"Usage: \llm [on|off|true|false]")
        return ParsedCommand(name="llm", args={"enabled": toggle})

    if stripped.startswith("\\contextualize"):
        parts = stripped.split()
        if len(parts) == 1:
            return ParsedCommand(name="contextualize_n", args={"n": 1})
        if len(parts) == 2 and parts[1].isdigit():
            return ParsedCommand(name="contextualize_n", args={"n": int(parts[1])})
        if len(parts) == 3 and parts[1] == "--id":
            return ParsedCommand(name="contextualize_ids", args={"ids": [parts[2]]})
        raise CommandParseError(r"Usage: \contextualize [n] OR \contextualize --id <UUID>")

    if stripped.startswith("\\mode"):
        parts = stripped.split(maxsplit=1)
        if len(parts) != 2 or parts[1] not in {"shell", "memory"}:
            raise CommandParseError(r"Usage: \mode [shell|memory]")
        return ParsedCommand(name="mode", args={"mode": parts[1]})

    if stripped.startswith("\\remember"):
        body = stripped[len("\\remember") :].strip()
        if "|" not in body:
            raise CommandParseError(r"Usage: \remember KIND | CONTENT")
        kind, content = [segment.strip() for segment in body.split("|", 1)]
        if not kind or not content:
            raise CommandParseError(r"Usage: \remember KIND | CONTENT")
        return ParsedCommand(name="remember", args={"kind": kind, "content": content})

    if stripped.startswith("\\recall"):
        query = stripped[len("\\recall") :].strip()
        if not query:
            raise CommandParseError(r"Usage: \recall QUERY")
        return ParsedCommand(name="recall", args={"query": query})

    if stripped.startswith("\\context"):
        query = stripped[len("\\context") :].strip()
        if not query:
            raise CommandParseError(r"Usage: \context QUERY")
        return ParsedCommand(name="context", args={"query": query})

    if stripped.startswith("\\inspect"):
        memory_id = stripped[len("\\inspect") :].strip()
        if not memory_id:
            raise CommandParseError(r"Usage: \inspect MEMORY_ID")
        return ParsedCommand(name="inspect", args={"memory_id": memory_id})

    raise CommandParseError(f"Unknown command: {stripped}")


def help_text() -> str:
    return "Available commands:\n" + "\n".join(COMMAND_HELP_LINES)
