# agent-xray

**REA let your agent look inside any app. agent-xray lets you look inside your agent.**

Your coding agent has a system prompt you've never read, makes tool calls you never see, and burns tokens you'd never approve. agent-xray reads its session transcripts and shows you everything — what it saw, what it skipped, what it claimed, and what it burned.

## The party trick

```
$ agent-xray show sess-001

CLAIMS VS EVIDENCE
------------------
"Tests pass" (turn 5)
  -> pytest tests/test_auth.py -q ran 1 turn after last code change
"Fixed" (turn 9)
  -> NO test command found after last code change
```

Your agent said "fixed." It never ran the tests. Now you know.

## Install

```bash
pip install agentxray

agent-xray sessions    # find your agent's transcripts
agent-xray show <id>   # the full x-ray
```

## What you get

- **Token ledger** — per-turn input / output / cache tokens with estimated cost. Find the turn that burned a dollar re-reading the same file.
- **Tool census** — every tool call it made, counted.
- **File x-ray** — files read vs files written. Flags files the agent **wrote without ever reading**.
- **Command audit** — every shell command, classified: tests, git, installs, other.
- **Claims vs evidence** — "tests pass" is a claim. agent-xray checks whether a test command actually ran after the last code change — and tells you when it didn't.
- **Blind spots** — the most expensive turn, the turns where it did nothing, the files it never looked at.

```bash
agent-xray show <id> --html report.html   # shareable dark-theme report
agent-xray show <id> --json               # machine-readable output
```

## How it works

Your agent already writes everything down. Claude Code stores session transcripts as JSONL under `~/.claude/projects/`. agent-xray parses them — defensively, offline, zero dependencies — and cross-references claims against actions. No AI, no network, no account. The evidence was already on your disk.

## Honest scope

- **v1 reads Claude Code transcripts.** Cursor, Codex CLI, Gemini CLI are detected; parsing them is next.
- **Cost figures are estimates** from public pricing — always labeled as such in the output.
- It reads what the transcript contains. Anything the agent did off-transcript is invisible — same as any observer.

## Privacy

Everything runs on your machine. Transcripts never leave your disk. There is nothing to opt out of, because there is nothing to opt into.

---

*verify, don't trust.*
