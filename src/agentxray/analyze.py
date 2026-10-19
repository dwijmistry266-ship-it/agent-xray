"""Build the XRay evidence report from parsed transcript turns."""

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from . import pricing
from .claude import ParsedSession, Turn

# Tools whose input carries the file being read / written.
READ_TOOLS = {"Read": "file_path", "NotebookRead": "notebook_path"}
WRITE_TOOLS = {"Edit": "file_path", "Write": "file_path"}
CODE_CHANGE_TOOLS = {"Edit", "Write"}

# Command classification, checked in this order.
RE_TESTS = re.compile(
    r"pytest|py\.test|npm test|yarn test|jest|vitest|go test|cargo test"
    r"|phpunit|rspec|gradle test|ctest"
)
RE_GIT = re.compile(r"^\s*git\b")
RE_INSTALL = re.compile(r"pip install|npm install|apt-get")

# Claim patterns scanned in assistant TEXT only (never tool inputs).
RE_CLAIM = re.compile(
    r"(?i)\b(tests?\s+(pass|passing|passed)|all green|fixed|verified"
    r"|confirmed working)\b"
)


@dataclass
class TokenRow:
    turn: int
    input: int
    output: int
    cache_read: int
    cache_write: int


@dataclass
class Command:
    command: str
    category: str  # tests | git | install | other
    turn: int


@dataclass
class ClaimFinding:
    claim_text: str
    turn: int
    evidence: str


@dataclass
class Meta:
    session_id: str
    project: Optional[str]
    model: Optional[str]
    started_at: Optional[str]
    ended_at: Optional[str]
    duration_seconds: Optional[float]
    turn_count: int


@dataclass
class XRay:
    meta: Meta
    token_rows: List[TokenRow]
    token_totals: Dict[str, int]
    estimated_cost_usd: Optional[float]
    cost_note: str
    tool_census: Dict[str, int]
    total_tool_calls: int
    read_files: List[str]
    written_files: List[str]
    write_without_read: List[str]
    hot_files: List[str]
    commands: List[Command]
    claims: List[ClaimFinding]
    turns_without_tools: List[int]
    most_expensive_turn: Dict[str, int]


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _exchanges(turns: List[Turn]) -> int:
    """Count user->assistant exchanges (a user turn followed by assistant)."""
    count = 0
    waiting = False
    for turn in turns:
        if turn.kind == "user" and turn.text.strip():
            waiting = True
        elif turn.kind == "assistant" and waiting:
            count += 1
            waiting = False
    return count


def _classify_command(command: str) -> str:
    if RE_TESTS.search(command):
        return "tests"
    if RE_GIT.search(command):
        return "git"
    if RE_INSTALL.search(command):
        return "install"
    return "other"


def _turn_tokens(turn: Turn) -> Dict[str, int]:
    u = turn.usage
    return {
        "input": u.get("input_tokens", 0),
        "output": u.get("output_tokens", 0),
        "cache_read": u.get("cache_read_input_tokens", 0),
        "cache_write": u.get("cache_creation_input_tokens", 0),
    }


def analyze(session: ParsedSession) -> XRay:
    """Turn a parsed session into an XRay evidence report."""
    turns = session.turns

    # ---- meta ----
    timestamps = [t.timestamp for t in turns if t.timestamp]
    started = _parse_ts(timestamps[0]) if timestamps else None
    ended = _parse_ts(timestamps[-1]) if timestamps else None
    duration = None
    if started and ended:
        duration = max(0.0, (ended - started).total_seconds())
    models = Counter(t.model for t in turns if t.model)
    meta = Meta(
        session_id=session.session_id,
        project=session.cwd,
        model=models.most_common(1)[0][0] if models else session.model,
        started_at=timestamps[0] if timestamps else None,
        ended_at=timestamps[-1] if timestamps else None,
        duration_seconds=duration,
        turn_count=_exchanges(turns),
    )

    # ---- tokens ----
    token_rows: List[TokenRow] = []
    totals = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    for turn in turns:
        toks = _turn_tokens(turn)
        if any(toks.values()):
            token_rows.append(TokenRow(turn=turn.index, **toks))
        for key in totals:
            totals[key] += toks[key]
    usage_for_pricing = {
        "input_tokens": totals["input"],
        "output_tokens": totals["output"],
        "cache_creation_input_tokens": totals["cache_write"],
        "cache_read_input_tokens": totals["cache_read"],
    }
    cost = pricing.estimate_cost(meta.model, usage_for_pricing)
    matched = pricing.match_model(meta.model)
    if cost is None:
        cost_note = (
            "model not recognized — cost not estimated "
            "(pricing covers claude-opus-4-*, claude-sonnet-4-*, "
            "claude-3-5-sonnet-*, claude-3-7-sonnet-*, claude-3-5-haiku-*)"
        )
    else:
        cost_note = (
            "estimate only, based on %s pricing — real prices drift" % matched
        )

    # ---- tools ----
    census: Counter = Counter()
    for turn in turns:
        for use in turn.tool_uses:
            census[use.name] += 1

    # ---- files ----
    read_counter: Counter = Counter()
    written: List[str] = []
    for turn in turns:
        for use in turn.tool_uses:
            if use.name in READ_TOOLS:
                path = use.input.get(READ_TOOLS[use.name])
                if isinstance(path, str) and path:
                    read_counter[path] += 1
            if use.name in WRITE_TOOLS:
                path = use.input.get(WRITE_TOOLS[use.name])
                if isinstance(path, str) and path and path not in written:
                    written.append(path)
    read_files = sorted(read_counter)
    write_without_read = [p for p in written if p not in read_counter]
    hot_files = sorted(p for p, n in read_counter.items() if n >= 3)

    # ---- commands ----
    commands: List[Command] = []
    for turn in turns:
        for use in turn.tool_uses:
            if use.name != "Bash":
                continue
            cmd = use.input.get("command")
            if isinstance(cmd, str) and cmd.strip():
                commands.append(
                    Command(
                        command=cmd.strip(),
                        category=_classify_command(cmd),
                        turn=turn.index,
                    )
                )

    # ---- claims vs evidence ----
    code_change_turns = sorted(
        turn.index
        for turn in turns
        if any(u.name in CODE_CHANGE_TOOLS for u in turn.tool_uses)
    )
    test_turns = {c.turn: c.command for c in commands if c.category == "tests"}
    claims: List[ClaimFinding] = []
    for turn in turns:
        if turn.kind != "assistant" or not turn.text:
            continue
        for match in RE_CLAIM.finditer(turn.text):
            earlier = [t for t in code_change_turns if t < turn.index]
            if not earlier:
                evidence = "no code change found before claim"
            else:
                last_change = earlier[-1]
                ran = [
                    (t, cmd)
                    for t, cmd in test_turns.items()
                    if last_change < t <= turn.index
                ]
                if not ran:
                    evidence = "NO test command found after last code change"
                else:
                    t, cmd = max(ran, key=lambda item: item[0])
                    gap = turn.index - t
                    if gap == 0:
                        when = "in the same turn as the claim"
                    elif gap == 1:
                        when = "1 turn after last code change"
                    else:
                        when = "%d turns after last code change" % gap
                    evidence = "%s ran %s" % (cmd, when)
            claims.append(
                ClaimFinding(
                    claim_text=match.group(0), turn=turn.index, evidence=evidence
                )
            )

    # ---- blind spots ----
    without_tools = [
        t.index for t in turns if t.kind == "assistant" and not t.tool_uses
    ]
    most_expensive: Dict[str, int] = {"turn": -1, "tokens": 0}
    for turn in turns:
        toks = _turn_tokens(turn)
        total = sum(toks.values())
        if total > most_expensive["tokens"]:
            most_expensive = {"turn": turn.index, "tokens": total}

    return XRay(
        meta=meta,
        token_rows=token_rows,
        token_totals=totals,
        estimated_cost_usd=cost,
        cost_note=cost_note,
        tool_census=dict(census.most_common()),
        total_tool_calls=sum(census.values()),
        read_files=read_files,
        written_files=written,
        write_without_read=write_without_read,
        hot_files=hot_files,
        commands=commands,
        claims=claims,
        turns_without_tools=without_tools,
        most_expensive_turn=most_expensive,
    )
