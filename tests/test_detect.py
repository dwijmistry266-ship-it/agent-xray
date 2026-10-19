"""Detection tests: fabricated transcript dirs under a tmp HOME."""

from agentxray import detect


def _write(path, text='{"type":"user","message":{"role":"user","content":"hi"}}'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def test_detects_fabricated_dirs(tmp_path):
    _write(tmp_path / ".claude" / "projects" / "proj-a" / "aaa.jsonl")
    _write(tmp_path / ".claude" / "projects" / "proj-a" / "bbb.jsonl")
    _write(tmp_path / ".codex" / "sessions" / "ccc.jsonl")

    reports = {r.key: r for r in detect.detect(home=tmp_path)}

    assert reports["claude"].transcripts_found is True
    assert reports["claude"].session_count == 2
    assert reports["codex"].transcripts_found is True
    assert reports["codex"].session_count == 1
    assert reports["cursor"].transcripts_found is False
    assert reports["cursor"].session_count == 0
    assert reports["gemini"].transcripts_found is False
    assert reports["gemini"].session_count == 0


def test_cli_check_is_boolean(tmp_path):
    for rep in detect.detect(home=tmp_path):
        assert isinstance(rep.cli_found, bool)
        assert isinstance(rep.cli, str) and rep.cli


def test_find_session_by_stem(tmp_path):
    _write(tmp_path / ".claude" / "projects" / "proj-a" / "deadbeef.jsonl")
    found = detect.find_session("deadbeef", home=tmp_path)
    assert found is not None
    key, path = found
    assert key == "claude"
    assert path.name == "deadbeef.jsonl"


def test_find_session_by_session_id(tmp_path):
    _write(
        tmp_path / ".claude" / "projects" / "proj-a" / "uuid-1234.jsonl",
        '{"type":"user","sessionId":"my-real-session","message":{"role":"user","content":"hi"}}',
    )
    found = detect.find_session("my-real-session", home=tmp_path)
    assert found is not None
    assert found[1].name == "uuid-1234.jsonl"


def test_find_session_missing(tmp_path):
    assert detect.find_session("nope", home=tmp_path) is None
