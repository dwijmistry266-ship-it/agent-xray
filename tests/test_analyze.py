"""Analysis tests: files, claims vs evidence, tokens, cost, blind spots."""

from pathlib import Path

import pytest

from agentxray import analyze, claude, pricing

FIXTURE = Path(__file__).parent / "fixtures" / "session1.jsonl"


def _xray():
    return analyze.analyze(claude.parse_session(FIXTURE))


def test_meta():
    x = _xray()
    assert x.meta.session_id == "sess-001"
    assert x.meta.project == "/home/user/demo-app"
    assert x.meta.model == "claude-sonnet-4-5-20250929"
    assert x.meta.turn_count == 2  # two user->assistant exchanges
    assert x.meta.duration_seconds == pytest.approx(720.0)


def test_write_without_read():
    x = _xray()
    assert x.write_without_read == ["src/helpers.py"]
    assert "src/auth.py" not in x.write_without_read  # it was read first


def test_hot_files():
    x = _xray()
    assert x.hot_files == ["src/auth.py"]  # read 3 times


def test_tool_census():
    x = _xray()
    assert x.tool_census["Read"] == 3
    assert x.tool_census["Edit"] == 2
    assert x.tool_census["Bash"] == 3
    assert x.total_tool_calls == 9


def test_command_classification():
    x = _xray()
    by_cat = {}
    for cmd in x.commands:
        by_cat.setdefault(cmd.category, []).append(cmd.command)
    assert len(by_cat["tests"]) == 2
    assert by_cat["git"] == ["git status --short"]
    assert "other" not in by_cat


def test_claim_with_evidence():
    x = _xray()
    claim = next(c for c in x.claims if "tests pass" in c.claim_text.lower())
    assert "pytest tests/test_auth.py -q" in claim.evidence
    assert "NO test command" not in claim.evidence
    # The pytest that ran AFTER the claim (turn 6) must not be the evidence;
    # the evidence is the run before the claim (turn 4, test_auth).
    assert "test_auth" in claim.evidence


def test_claim_without_evidence():
    x = _xray()
    claim = next(c for c in x.claims if c.claim_text.lower() == "fixed")
    assert claim.evidence == "NO test command found after last code change"


def test_token_totals():
    x = _xray()
    assert x.token_totals == {
        "input": 65000,
        "output": 3850,
        "cache_read": 407000,
        "cache_write": 4000,
    }


def test_cost_estimate_labeled():
    x = _xray()
    # 65000/1e6*3 + 3850/1e6*15 + 4000/1e6*3.75 + 407000/1e6*0.30
    assert x.estimated_cost_usd == pytest.approx(0.3899)
    assert "estimate" in x.cost_note


def test_cost_unknown_model():
    assert pricing.estimate_cost("some-future-model-9", {"input_tokens": 10}) is None
    assert pricing.estimate_cost(None, {}) is None


def test_blind_spots():
    x = _xray()
    assert x.turns_without_tools == [5, 9]  # text-only assistant turns
    assert x.most_expensive_turn["turn"] == 2
    assert x.most_expensive_turn["tokens"] == 173500
