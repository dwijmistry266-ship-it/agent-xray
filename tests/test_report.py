"""Report tests: terminal sections, standalone HTML."""

from pathlib import Path

from agentxray import analyze, claude, report

FIXTURE = Path(__file__).parent / "fixtures" / "session1.jsonl"


def _xray():
    return analyze.analyze(claude.parse_session(FIXTURE))


def test_terminal_has_key_sections():
    text = report.render_terminal(_xray())
    for section in (
        "SESSION",
        "TOKENS & COST",
        "TOOL CENSUS",
        "FILES",
        "COMMANDS",
        "CLAIMS VS EVIDENCE",
        "BLIND SPOTS",
    ):
        assert section in text
    assert "sess-001" in text
    assert "src/helpers.py" in text


def test_terminal_flags_unverified_claim():
    text = report.render_terminal(_xray())
    assert "NO test command found after last code change" in text


def test_html_is_standalone():
    page = report.render_html(_xray())
    assert "<!DOCTYPE html>" in page
    assert "sess-001" in page
    # No external assets: nothing to fetch over the network.
    assert "http" not in page.lower()
    assert "<style>" in page


def test_html_escapes_content(tmp_path):
    # A hostile file path must not break the page.
    evil = tmp_path / "evil.jsonl"
    evil.write_text(
        '{"type":"assistant","message":{"role":"assistant","content":'
        '[{"type":"tool_use","id":"1","name":"Read","input":{"file_path":'
        '"<script>alert(1)</script>"}}]}}\n',
        encoding="utf-8",
    )
    xray = analyze.analyze(claude.parse_session(evil))
    page = report.render_html(xray)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page
