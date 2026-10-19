"""Defensive parser for Claude Code JSONL session transcripts.

Every field is optional. Unknown line types and unknown fields are skipped,
never fatal. A malformed JSON line is dropped silently — the session is
evidence, and one corrupt line must not destroy the rest.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


@dataclass
class ToolUse:
    """One tool_use content block from an assistant message."""

    name: str
    id: str
    input: Dict[str, Any]


@dataclass
class Turn:
    """One parsed transcript line."""

    index: int
    kind: str  # "user" | "assistant" | "system"
    text: str
    tool_uses: List[ToolUse] = field(default_factory=list)
    usage: Dict[str, int] = field(default_factory=dict)
    timestamp: Optional[str] = None
    model: Optional[str] = None


@dataclass
class ParsedSession:
    """A whole transcript file, parsed."""

    session_id: str
    path: Path
    turns: List[Turn]
    model: Optional[str]
    cwd: Optional[str]


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _usage_of(message: Dict[str, Any]) -> Dict[str, int]:
    raw = _as_dict(message.get("usage"))
    out: Dict[str, int] = {}
    for key in USAGE_KEYS:
        try:
            out[key] = int(raw.get(key) or 0)
        except (TypeError, ValueError):
            out[key] = 0
    return out


def _text_of_content(content: Any) -> str:
    """Extract readable text from a message content field.

    Content may be a plain string, a list of blocks, or something else.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _tool_uses_of(content: Any) -> List[ToolUse]:
    """Extract tool_use blocks; tolerate missing/odd fields."""
    uses: List[ToolUse] = []
    if not isinstance(content, list):
        return uses
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        name = block.get("name")
        if not isinstance(name, str) or not name:
            continue
        uses.append(
            ToolUse(
                name=name,
                id=str(block.get("id") or ""),
                input=_as_dict(block.get("input")),
            )
        )
    return uses


def parse_line(obj: Dict[str, Any], index: int) -> Optional[Turn]:
    """Parse one decoded JSONL object into a Turn, or None to skip it."""
    kind = obj.get("type")
    if kind not in ("user", "assistant", "system"):
        return None  # file-history-snapshot and friends: not our business
    message = _as_dict(obj.get("message"))
    content = message.get("content")
    return Turn(
        index=index,
        kind=kind,
        text=_text_of_content(content),
        tool_uses=_tool_uses_of(content),
        usage=_usage_of(message),
        timestamp=obj.get("timestamp")
        if isinstance(obj.get("timestamp"), str)
        else None,
        model=message.get("model")
        if isinstance(message.get("model"), str)
        else None,
    )


def iter_turns(path: Path) -> Iterator[Turn]:
    """Yield Turns from a JSONL file, skipping malformed lines."""
    index = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue  # corrupt line: drop it, keep the session
            if not isinstance(obj, dict):
                continue
            turn = parse_line(obj, index)
            if turn is not None:
                yield turn
                index += 1


def parse_session(path: Path) -> ParsedSession:
    """Parse a whole transcript file into a ParsedSession."""
    path = Path(path)
    turns = list(iter_turns(path))
    session_id: Optional[str] = None
    cwd: Optional[str] = None
    model: Optional[str] = None
    # Prefer values from the system init line; fall back to anything seen.
    # Simple robust pass: first non-empty value wins, in file order.
    for raw in _raw_objects(path):
        if session_id is None and isinstance(raw.get("sessionId"), str):
            session_id = raw["sessionId"]
        if cwd is None and isinstance(raw.get("cwd"), str):
            cwd = raw["cwd"]
        msg = _as_dict(raw.get("message"))
        if model is None and isinstance(msg.get("model"), str):
            model = msg["model"]
        if session_id and cwd and model:
            break
    return ParsedSession(
        session_id=session_id or path.stem,
        path=path,
        turns=turns,
        model=model,
        cwd=cwd,
    )


def _raw_objects(path: Path) -> Iterator[Dict[str, Any]]:
    """Yield decoded JSON dicts, skipping malformed lines (internal helper)."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict):
                yield obj
