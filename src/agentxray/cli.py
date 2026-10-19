"""Command line interface for agent-xray."""

import argparse
import dataclasses
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from . import __version__, analyze, claude, detect, report


class XRayError(Exception):
    """A clean, user-facing failure (no traceback needed)."""


def _fmt_mtime(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except OSError:
        return "?"


def cmd_sessions(_args: argparse.Namespace) -> int:
    reports = detect.detect()
    any_found = False
    for rep in reports:
        status = "yes" if rep.transcripts_found else "no"
        cli = "found" if rep.cli_found else "not found"
        print(
            "%-12s transcripts: %-3s  sessions: %-4d  dir: %s  (cli %s: %s)"
            % (rep.label, status, rep.session_count, rep.dir, rep.cli, cli)
        )
        if rep.transcripts_found:
            any_found = True
            for _key, path in detect.iter_session_files(key=rep.key):
                print("    %-36s %s  %s" % (path.stem, _fmt_mtime(path), path))
    if not any_found:
        print(
            "\nNo transcript directories found. "
            "Run one of the supported agents first, or point HOME at a "
            "directory containing them."
        )
    return 0


def _load_session(session_id: str):
    found = detect.find_session(session_id)
    if found is None:
        raise XRayError(
            "session '%s' not found in any known transcript dir "
            "(try `agent-xray sessions`)" % session_id
        )
    agent_key, path = found
    if agent_key != "claude":
        raise XRayError(
            "parsing %s transcripts is not implemented yet "
            "(only Claude Code is supported)" % agent_key
        )
    return claude.parse_session(path)


def cmd_show(args: argparse.Namespace) -> int:
    session = _load_session(args.session)
    if not session.turns:
        raise XRayError("session '%s' has no parseable turns" % args.session)
    xray = analyze.analyze(session)
    if args.json:
        print(json.dumps(dataclasses.asdict(xray), indent=2, default=str))
        return 0
    if args.html:
        out = Path(args.html)
        out.write_text(report.render_html(xray), encoding="utf-8")
        print("wrote %s" % out)
        return 0
    print(report.render_terminal(xray))
    return 0


def cmd_version(_args: argparse.Namespace) -> int:
    print("agent-xray %s" % __version__)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-xray",
        description="X-ray your AI coding agent's session transcripts.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_sessions = sub.add_parser("sessions", help="list detected transcript dirs")
    p_sessions.set_defaults(func=cmd_sessions)

    p_show = sub.add_parser("show", help="analyze one session")
    p_show.add_argument("session", help="session id (filename stem or sessionId)")
    p_show.add_argument("--html", metavar="OUT.html", help="write HTML report")
    p_show.add_argument("--json", action="store_true", help="machine-readable output")
    p_show.set_defaults(func=cmd_show)

    p_version = sub.add_parser("version", help="print version")
    p_version.set_defaults(func=cmd_version)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except XRayError as exc:
        print("agent-xray: error: %s" % exc, file=sys.stderr)
        return 1
    except OSError as exc:
        print("agent-xray: error: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
