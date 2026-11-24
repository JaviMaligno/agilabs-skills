#!/usr/bin/env python3
"""agent-multiplier: hours your coding agents worked per hour of your attention.

  python3 agent_multiplier.py [--days 28] [--html out.html] [--json out.json] [--evidence ev.json]
                              [--config config.json] [--calendar cal.json] [--remote 'remote/*.jsonl']
                              [--recommendations DIR] [--include-headless]

Reads Claude Code (~/.claude/projects) and Codex CLI (~/.codex/sessions) transcripts locally. Prints
the global figure and one line per category; never prints or stores prompt text. Sends nothing.
Defaults look in ~/.agent-multiplier/ (config.json, calendar.json, remote/*.jsonl, recommendations/).
Output folders are created when missing.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import measure  # noqa: E402

DATA_DIR = Path(os.path.expanduser(os.environ.get("AGENT_MULTIPLIER_HOME", "~/.agent-multiplier")))
# The template carries this JSON literal where the report goes; an unfilled page shows its empty state.
PAYLOAD_SLOT = '{"__agent_multiplier__":"payload"}'


def public_part(report: dict) -> dict:
    """The report without the private keys (those starting with an underscore)."""
    return {k: v for k, v in report.items() if not k.startswith("_")}


def ensure_parent(path: str | os.PathLike) -> Path:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def write_json(path: str | os.PathLike, obj) -> None:
    ensure_parent(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def load_recommendations(folder: str | os.PathLike | None) -> dict:
    """recommendations/<anything>.json, one per category (format in README.md)."""
    found: dict = {}
    if not folder or not Path(folder).is_dir():
        return found
    for item in sorted(Path(folder).glob("*.json")):
        try:
            rec = json.loads(item.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            print(f"warning: skipping unreadable recommendations file {item}", file=sys.stderr)
            continue
        if isinstance(rec, dict) and rec.get("category"):
            found[rec["category"]] = rec
    return found


def render_html(report: dict, path: str | os.PathLike) -> None:
    template = (SCRIPT_DIR / "page.html").read_text(encoding="utf-8")
    if PAYLOAD_SLOT not in template:
        raise RuntimeError("page.html has lost its payload slot")
    # escaping every "<" keeps the JSON from closing the script element, whatever the data holds
    blob = json.dumps(public_part(report), ensure_ascii=False).replace("<", "\\u003c")
    ensure_parent(path).write_text(template.replace(PAYLOAD_SLOT, blob, 1), encoding="utf-8")


def existing(name: str) -> str | None:
    candidate = DATA_DIR / name
    return str(candidate) if candidate.exists() else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=measure.DEFAULT_DAYS, help="window in days, ending today (default 28)")
    parser.add_argument("--config", default=existing("config.json"), help="categories (see config.example.json)")
    parser.add_argument("--calendar", default=existing("calendar.json"), help="Google Calendar events-list JSON")
    parser.add_argument("--remote", action="append", help="glob of remote-work JSON-lines files (repeatable)")
    parser.add_argument("--recommendations", default=str(DATA_DIR / "recommendations"))
    parser.add_argument("--claude-root", default=os.path.expanduser("~/.claude/projects"))
    parser.add_argument("--codex-root", default=os.path.expanduser("~/.codex/sessions"))
    parser.add_argument("--include-headless", action="store_true",
                        help="also count headless runs (claude -p, codex exec) as agent hours, with no attention")
    parser.add_argument("--exclude-dir", action="append", default=[], help="working directory to leave out (repeatable)")
    parser.add_argument("--attention", choices=sorted(measure.ATTENTION_PROFILES), default=measure.DEFAULT_ATTENTION,
                        help="how much of your time each input counts for (see README, 'Attention profiles')")
    parser.add_argument("--html")
    parser.add_argument("--json")
    parser.add_argument("--evidence", help="per-category list of the sessions behind each figure (for investigating)")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    # create output folders before the (slow) parsing, so a bad path fails at once
    for out in (args.html, args.json, args.evidence):
        if out:
            ensure_parent(out)

    measure.set_attention_profile(args.attention)
    cfg = measure.load_config(args.config)
    today = measure.work_date(datetime.now())
    since = datetime.combine(today - timedelta(days=args.days + 1), time())
    convs = measure.load_all(args.claude_root, args.codex_root, since=since, include_headless=args.include_headless,
                             routine_marker=cfg.get("routine_marker") or measure.DEFAULT_ROUTINE_MARKER,
                             exclude_dirs=args.exclude_dir + cfg.get("exclude_dirs", []))
    meetings = measure.meetings_from(args.calendar) if args.calendar else []
    remote_globs = args.remote or [str(DATA_DIR / "remote" / "*.jsonl")]
    remote = measure.load_remote(sorted({f for g in remote_globs for f in glob.glob(os.path.expanduser(g))}))
    report = measure.compute(convs, cfg, days=args.days, today=today, meetings=meetings, remote=remote,
                             recommendations=load_recommendations(args.recommendations))

    if args.json:
        write_json(args.json, public_part(report))
    if args.evidence:
        write_json(args.evidence, {cat: {"sessions": len(found), "top_sessions": found[:15]}
                                   for cat, found in report["_sessions"].items()})
    if args.html:
        render_html(report, args.html)

    total, disc = report["total"], report["discounts"]
    print(f"{report['since']} .. {report['until']}: x{total['ratio']} = {total['agent']:.1f} agent h / "
          f"{total['attention']:.1f} h of your attention ({total['inputs']} inputs: {total['prompts']} prompts, "
          f"{total['approvals']} approvals, {total['answers']} answers; {total['sittings']} sittings; "
          f"{total['conversations']} conversations)")
    split = total["agent_by_worker"]
    print(f"agent hours by worker: main {split['main']:.1f} · subagents {split['subagent']:.1f} · "
          f"background tasks {split['background']:.1f} · remote {split['remote']:.1f}")
    if split.get("background_capped_tasks"):
        print(f"  of the background hours, {split['background_capped_h']:.1f} h come from {split['background_capped_tasks']} "
              f"tasks that hit the {split['background_cap_h']:g} h cap (often watch or poll loops)")
    print(f"discounted restart prompts: {disc['restart_prompts'] or 0} · compactions ignored: {disc['compactions']} · "
          f"meetings: {report['meetings']}")
    for row in report["rows"]:
        print(f"  {row['category'][:32]:32s} att {row['attention']:6.1f} h · agent {row['agent']:6.1f} h · x{row['ratio']} · "
              f"{row['inputs_per_hour']} in/h · approvals {row['approval_share']} · {row['sittings']} sittings "
              f"({row['median_sitting_min']} min)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
