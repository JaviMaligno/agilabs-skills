#!/usr/bin/env python3
"""Compact timeline of one transcript, for investigating a category.

  python3 session_timeline.py <transcript.jsonl> [--from ISO] [--to ISO] [--show-text] [--max 300]

Claude Code or Codex CLI. Prints, in local time, one line per event: your inputs (prompt, approval,
answer) with their length, what reached the agent that was not yours (notifications, teammate
messages, compactions), the agent's tool calls by name, cut-off markers (memory kill, network error,
resume, died mid tool call) and the gap since the previous line when it is 3 minutes or more.

By default it never prints prompt or message text, only lengths and tool names. --show-text adds the
first --max characters of your prompts and of the agent's last message before you came back, with
secret-looking strings masked. Read-only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure as M  # noqa: E402

SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}|"
                    r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_.-]+|AKIA[0-9A-Z]{16}|[A-Za-z0-9+/]{40,}={0,2})")
TAGS = re.compile(r"<(system-reminder|local-command-[a-z]+|command-[a-z]+)>.*?</\1>", re.S)


def clean(s: str, n: int) -> str:
    s = TAGS.sub("", s or "")
    s = SECRET.sub("[hidden]", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[:n] + "..."


def events_claude(path: str):
    """(time, label, text-or-None) for a Claude Code main transcript."""
    open_calls, questions = {}, set()
    seen_prompt = sources_seen = False
    for line, o in M._read_jsonl(path, M.CLAUDE_TYPES):
        ts = o.get("timestamp")
        if not ts or o.get("isSidechain"):
            continue
        t = M.to_local_naive(ts)
        typ = o.get("type")
        if typ == "attachment":
            att = o.get("attachment") if isinstance(o.get("attachment"), dict) else {}
            if att.get("type") == "instructions" and seen_prompt and (M.RESUME_PHRASE in line or att.get("reason") == "session_start"):
                yield t, "CUT resume (instructions re-read)", None
            continue
        c = (o.get("message") or {}).get("content")
        if typ == "assistant":
            if o.get("isApiErrorMessage"):
                net = any(s in line for s in M.NETWORK_ERRORS)
                yield t, "CUT network error" if net else "API error", None
            for block in (c if isinstance(c, list) else []):
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    open_calls[block.get("id")] = (t, block.get("name", ""))
                    if block.get("name") == "AskUserQuestion":
                        questions.add(block.get("id"))
                    bg = " (background)" if (block.get("input") or {}).get("run_in_background") else ""
                    yield t, f"  agent tool: {block.get('name', '')}{bg}", None
                elif block.get("type") == "text" and (block.get("text") or "").strip():
                    yield t, f"  agent text ({len(block['text'])} chars)", ("agent", block["text"])
            continue
        results = M.blocks(c, "tool_result")
        if results:
            by_person = M.decided_by_human(o)
            for res in results:
                call_id = res.get("tool_use_id")
                _, tool_name = open_calls.pop(call_id, (None, ""))
                if call_id in questions:
                    yield t, "YOU answer", None
                elif by_person:
                    yield t, f"YOU approval: {tool_name} ({(o.get('permissionDecision') or {}).get('decision', '')})", None
            continue
        if "promptSource" in o:
            sources_seen = True
        kind = M.classify_claude_user(o, sources_seen)
        text = M._text_of(c)
        if kind == "compaction":
            yield t, "-- context compaction (not yours)", None
        elif kind == "yours":
            if open_calls:
                yield t, "CUT died mid tool call (tool calls with no result)", None
                open_calls.clear()
            seen_prompt = True
            yield t, f"YOU prompt ({len(text)} chars)", ("you", text)
        elif text.lstrip().startswith("<task-notification"):
            yield t, "-- task notification" + (" (CUT low memory)" if M.MEMORY_KILL in text else ""), None
        elif text.strip():
            origin = o.get("origin") if isinstance(o.get("origin"), dict) else {}
            yield t, f"-- not yours: {origin.get('kind') or o.get('promptSource') or 'system'}", None


def events_codex(path: str):
    for line, o in M._read_jsonl(path):
        ts = o.get("timestamp")
        if not ts:
            continue
        t = M.to_local_naive(ts)
        p = o.get("payload") if isinstance(o.get("payload"), dict) else {}
        pt = p.get("type")
        if o.get("type") == "compacted" or pt in ("compacted", "compaction", "context_compacted"):
            yield t, "-- context compaction (not yours)", None
        elif o.get("type") == "event_msg" and pt and pt.endswith("approval_request"):
            yield t, "YOU approval requested", None
        elif o.get("type") == "response_item" and pt == "message" and p.get("role") == "user":
            text = M._codex_text(p.get("content"))
            if not text.lstrip().startswith(M.CODEX_INJECTED_PREFIXES):
                yield t, f"YOU prompt ({len(text)} chars)", ("you", text)
        elif o.get("type") == "response_item" and pt in ("function_call", "custom_tool_call", "local_shell_call"):
            yield t, f"  agent tool: {p.get('name', pt)}", None
        elif o.get("type") == "response_item" and pt == "message" and p.get("role") == "assistant":
            text = M._codex_text(p.get("content"))
            yield t, f"  agent text ({len(text)} chars)", ("agent", text)
        elif o.get("type") == "event_msg" and pt in ("error", "stream_error"):
            yield t, "CUT network error" if any(s in line for s in M.NETWORK_ERRORS) else "error", None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--from", dest="frm")
    ap.add_argument("--to")
    ap.add_argument("--show-text", action="store_true", help="also print (masked, truncated) prompt and agent text")
    ap.add_argument("--max", type=int, default=300)
    a = ap.parse_args(argv)
    frm = datetime.fromisoformat(a.frm) if a.frm else None
    to = datetime.fromisoformat(a.to) if a.to else None
    with open(a.file, encoding="utf-8", errors="ignore") as fh:
        first = fh.readline()
    is_codex = '"session_meta"' in first or '"record_type"' in first or os.sep + ".codex" + os.sep in a.file
    events = events_codex(a.file) if is_codex else events_claude(a.file)
    last_t, last_agent_text, agent_lines = None, None, 0
    for t, label, text in events:
        if (frm and t < frm) or (to and t > to):
            continue
        if label.startswith("  agent text"):
            last_agent_text = (t, text[1])  # shown only right before your next prompt
            continue
        if label.startswith("  agent tool"):
            agent_lines += 1
        gap = f" (+{int((t - last_t).total_seconds() // 60)} min)" if last_t and t - last_t >= timedelta(minutes=3) else ""
        if label.startswith("YOU") and a.show_text and last_agent_text:
            print(f"[{last_agent_text[0]:%m-%d %H:%M}]   agent said: {clean(last_agent_text[1], a.max)}")
        print(f"[{t:%m-%d %H:%M}]{gap} {label}")
        if text and a.show_text and text[0] == "you":
            print(f"               > {clean(text[1], a.max)}")
        if label.startswith("YOU"):
            last_agent_text = None
        last_t = t
    return 0


if __name__ == "__main__":
    sys.exit(main())
