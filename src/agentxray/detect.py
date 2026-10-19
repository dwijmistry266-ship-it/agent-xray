"""Locate AI coding-agent transcript directories on this machine."""

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

# Each entry: where an agent keeps transcripts, and its CLI binary name
# (the CLI check is informational only).
AGENTS = [
    {
        "key": "claude",
        "label": "Claude Code",
        "rel": ".claude/projects",
        "cli": "claude",
        "globs": ["**/*.jsonl"],
    },
    {
        "key": "codex",
        "label": "Codex CLI",
        "rel": ".codex/sessions",
        "cli": "codex",
        "globs": ["**/*.jsonl"],
    },
    {
        "key": "cursor",
        "label": "Cursor",
        "rel": ".cursor",
        "cli": "cursor",
        "globs": ["**/*.jsonl"],
    },
    {
        "key": "gemini",
        "label": "Gemini CLI",
        "rel": ".gemini",
        "cli": "gemini",
        "globs": ["**/*.jsonl"],
    },
]


@dataclass
class AgentReport:
    """What we found for one agent."""

    key: str
    label: str
    dir: Path
    transcripts_found: bool
    session_count: int
    cli: str
    cli_found: bool


def _home(home: Optional[Path]) -> Path:
    if home is not None:
        return Path(home)
    return Path(os.path.expanduser("~"))


def detect(home: Optional[Path] = None) -> List[AgentReport]:
    """Scan the home directory for agent transcript stores."""
    base = _home(home)
    reports = []
    for agent in AGENTS:
        d = base / agent["rel"]
        found = d.is_dir()
        count = 0
        if found:
            for pattern in agent["globs"]:
                try:
                    count += sum(1 for _ in d.glob(pattern))
                except OSError:
                    continue
        reports.append(
            AgentReport(
                key=agent["key"],
                label=agent["label"],
                dir=d,
                transcripts_found=found,
                session_count=count,
                cli=agent["cli"],
                cli_found=shutil.which(agent["cli"]) is not None,
            )
        )
    return reports


def iter_session_files(
    home: Optional[Path] = None, key: Optional[str] = None
) -> Iterator[Tuple[str, Path]]:
    """Yield (agent_key, path) for every session file found."""
    base = _home(home)
    for agent in AGENTS:
        if key is not None and agent["key"] != key:
            continue
        d = base / agent["rel"]
        if not d.is_dir():
            continue
        for pattern in agent["globs"]:
            try:
                files = sorted(d.glob(pattern))
            except OSError:
                continue
            for f in files:
                if f.is_file():
                    yield agent["key"], f


def _session_id_from_first_line(path: Path) -> Optional[str]:
    """Cheap fallback: read the first JSONL line for a sessionId field."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            line = fh.readline()
        obj = json.loads(line)
        sid = obj.get("sessionId")
        return str(sid) if sid else None
    except (OSError, ValueError):
        return None


def find_session(
    session_id: str, home: Optional[Path] = None
) -> Optional[Tuple[str, Path]]:
    """Find a session by id: filename stem first, then sessionId scan."""
    candidates = list(iter_session_files(home))
    for agent_key, path in candidates:
        if path.stem == session_id:
            return agent_key, path
    for agent_key, path in candidates:
        if _session_id_from_first_line(path) == session_id:
            return agent_key, path
    return None
