"""Parser tests: turn extraction, usage, malformed lines, missing fields."""

from pathlib import Path

from agentxray import claude

FIXTURE = Path(__file__).parent / "fixtures" / "session1.jsonl"


def test_session_id_and_model():
    session = claude.parse_session(FIXTURE)
    assert session.session_id == "sess-001"
    assert session.model == "claude-sonnet-4-5-20250929"
    assert session.cwd == "/home/user/demo-app"


def test_turn_counts_and_kinds():
    session = claude.parse_session(FIXTURE)
    kinds = [t.kind for t in session.turns]
    # 1 system + 2 user + 8 assistant; the malformed line is skipped
    assert len(session.turns) == 11
    assert kinds.count("system") == 1
    assert kinds.count("user") == 2
    assert kinds.count("assistant") == 8


def test_tool_use_extraction():
    session = claude.parse_session(FIXTURE)
    names = [u.name for t in session.turns for u in t.tool_uses]
    assert names.count("Read") == 3
    assert names.count("Glob") == 1
    assert names.count("Edit") == 2
    assert names.count("Bash") == 3
    edits = [
        u for t in session.turns for u in t.tool_uses if u.name == "Edit"
    ]
    assert edits[0].input["file_path"] == "src/auth.py"
    assert edits[1].input["file_path"] == "src/helpers.py"


def test_usage_accumulation():
    session = claude.parse_session(FIXTURE)
    totals = {k: 0 for k in claude.USAGE_KEYS}
    for turn in session.turns:
        for key in totals:
            totals[key] += turn.usage.get(key, 0)
    assert totals["input_tokens"] == 65000
    assert totals["output_tokens"] == 3850
    assert totals["cache_creation_input_tokens"] == 4000
    assert totals["cache_read_input_tokens"] == 407000


def test_user_text_extracted():
    session = claude.parse_session(FIXTURE)
    users = [t for t in session.turns if t.kind == "user"]
    assert "login endpoint" in users[0].text


def test_missing_fields_tolerated():
    # Bare assistant line: no crash, empty turn.
    turn = claude.parse_line({"type": "assistant"}, 99)
    assert turn is not None
    assert turn.text == ""
    assert turn.tool_uses == []
    assert all(v == 0 for v in turn.usage.values())
    # Unknown line type: skipped.
    assert claude.parse_line({"type": "file-history-snapshot"}, 0) is None
    assert claude.parse_line({"type": "assistant", "message": None}, 1) is not None


def test_timestamps_present():
    session = claude.parse_session(FIXTURE)
    assert session.turns[0].timestamp == "2026-10-20T10:00:00Z"
    assert session.turns[-1].timestamp == "2026-10-20T10:12:00Z"
