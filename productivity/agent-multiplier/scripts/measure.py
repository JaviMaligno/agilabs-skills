"""Core of agent-multiplier: read local agent transcripts and measure your attention vs agent time.

Everything here is read-only and local. Prompt text is only ever used for its length (to estimate
typing time) and to look for fixed marker strings; it is never stored in the results.

The model, in short (see README.md, "How it is measured"):
  * an *input* is something you did: a prompt you typed, a permission you granted or denied, an
    answer to a question the agent asked you;
  * each input gets an *attention window*: reading the agent's last output + typing, capped, plus a
    short glance after sending; overlapping windows are merged, so attention is wall-clock time;
  * *agent time* is the time each worker (main agent, every subagent, every background task) spent
    working, summed over workers, so two agents working for one hour count as two agent hours;
  * the multiplier is agent hours / attention hours.
"""
from __future__ import annotations

import bisect
import collections
import glob
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable

# ---------------------------------------------------------------------------------------------
# Parameters (named so the README can point at them)
# ---------------------------------------------------------------------------------------------
READ_CAP = timedelta(seconds=120)          # reading the agent's last output before a prompt
TYPING_CHARS_PER_SEC = 5.0                   # ~60 words per minute
TYPING_CAP = timedelta(seconds=180)        # long or pasted prompts never count more than this
MIN_PROMPT_LEAD = timedelta(seconds=10)    # even "yes" takes a moment
APPROVAL_READ_CAP = timedelta(seconds=30)  # reading a permission request and deciding
ANSWER_READ_CAP = timedelta(seconds=60)    # reading a question the agent asked and answering
AFTER_INPUT = timedelta(seconds=30)        # watching the agent pick your input up
WINDOW_CAP = timedelta(minutes=5)          # hard cap on one input's window
STEP_CAP = timedelta(minutes=30)           # one silent agent step never counts more than this
BACKGROUND_CAP = timedelta(hours=2)        # one background task never counts more than this
# Attention profiles. "conservative" (the default, the values above) counts only the time it takes
# to read the agent's last output and type your input. "generous" also counts reviewing what the
# agent produced and thinking before you answer, which suits work where you read long outputs,
# drafts or diffs before replying. Same transcripts, different assumption: say which one you used.
ATTENTION_PROFILES = {
    "conservative": {"READ_CAP": READ_CAP, "TYPING_CHARS_PER_SEC": TYPING_CHARS_PER_SEC, "TYPING_CAP": TYPING_CAP,
                     "APPROVAL_READ_CAP": APPROVAL_READ_CAP, "ANSWER_READ_CAP": ANSWER_READ_CAP,
                     "AFTER_INPUT": AFTER_INPUT, "WINDOW_CAP": WINDOW_CAP},
    "generous": {"READ_CAP": timedelta(minutes=8), "TYPING_CHARS_PER_SEC": 3.0, "TYPING_CAP": timedelta(minutes=5),
                 "APPROVAL_READ_CAP": timedelta(seconds=60), "ANSWER_READ_CAP": timedelta(minutes=3),
                 "AFTER_INPUT": timedelta(seconds=90), "WINDOW_CAP": timedelta(minutes=12)},
}
DEFAULT_ATTENTION = "conservative"
attention_profile = DEFAULT_ATTENTION


def set_attention_profile(name: str) -> None:
    """Switch the attention parameters for this process (windows read them when computed)."""
    global attention_profile
    if name not in ATTENTION_PROFILES:
        raise ValueError(f"unknown attention profile {name!r}: choose from {sorted(ATTENTION_PROFILES)}")
    globals().update(ATTENTION_PROFILES[name])
    attention_profile = name


SITTING_BREAK = timedelta(minutes=30)        # a gap this long between your inputs starts a new sitting
RESUME_GAP = timedelta(minutes=2)          # session died mid tool call if you come back after this
KILL_WINDOW = timedelta(hours=12)          # a restart prompt must come within this time of the cut
DAY_START_HOUR = 4                           # work after midnight and before 04:00 counts for the day before
DEFAULT_DAYS = 28
DEFAULT_ROUTINE_MARKER = "[agent-multiplier-routine]"
MEETING_MAX = timedelta(hours=3)

NETWORK_ERRORS = ("Can't reach the API server", "ENOTFOUND", "ECONNRESET", "ECONNREFUSED",
                  "Connection error", "fetch failed", "socket hang up", "ETIMEDOUT",
                  "stream disconnected", "error sending request")
MEMORY_KILL = "running low on memory"
RESUME_PHRASE = "were re-read when this session started"
# Values of the transcript's "promptSource" field that mean a person sent the prompt from the terminal.
YOUR_PROMPT_SOURCES = frozenset({"typed", "queued", "suggestion_accepted"})
BACKGROUND_SKIP_TOOLS = {"Agent", "Task"}  # background agents have their own subagent transcript
NOT_YOURS_PREFIXES = ("<task-notification", "<local-command-stdout", "<local-command-stderr",
                      "<bash-stdout", "<bash-stderr", "<system-reminder", "[Request interrupted",
                      "<teammate-message", "<peer-message", "Caveat:",
                      "Another Claude session sent")
# Things you type that recent Claude Code versions still record without a promptSource.
TYPED_WITHOUT_SOURCE = ("<bash-input", "<command-name")
# Codex user-role messages that are context the CLI injects, not something you wrote.
CODEX_INJECTED_PREFIXES = ("<", "# AGENTS.md instructions")
CODEX_WORK_ITEMS = {"message", "reasoning", "function_call", "function_call_output", "custom_tool_call",
                    "custom_tool_call_output", "local_shell_call", "local_shell_call_output",
                    "web_search_call", "tool_search_call", "tool_search_output"}
CODEX_WORK_EVENTS = {"task_complete", "agent_message", "exec_command_end", "patch_apply_end",
                     "mcp_tool_call_end"}


# ---------------------------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------------------------
_FRACTION = re.compile(r"(\.\d{6})\d+")


def to_local_naive(stamp: str) -> datetime:
    """ISO timestamp (with Z or an offset) -> naive datetime in this machine's time zone."""
    text = _FRACTION.sub(r"\1", stamp.strip())
    if text[-1:] in ("Z", "z"):
        text = text[:-1] + "+00:00"
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        return moment
    return datetime.fromtimestamp(moment.timestamp())


def work_date(moment: datetime) -> date:
    """The working day a moment belongs to: before DAY_START_HOUR it still counts for the day before."""
    day = moment.date()
    return day - timedelta(days=1) if moment.hour < DAY_START_HOUR else day


def day_bounds(d: date) -> tuple[datetime, datetime]:
    a = datetime.combine(d, time(DAY_START_HOUR))
    return a, a + timedelta(days=1)


def hours(iv: Iterable[tuple[datetime, datetime]]) -> float:
    return sum((b - a).total_seconds() for a, b in iv) / 3600


def union(spans: Iterable[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """Sorted, disjoint intervals covering exactly the same time as spans (empty spans dropped)."""
    ordered = sorted((s, e) for s, e in spans if e > s)
    covered: list[tuple[datetime, datetime]] = []
    i = 0
    while i < len(ordered):
        start, end = ordered[i]
        i += 1
        while i < len(ordered) and ordered[i][0] <= end:  # touching or overlapping: extend
            end = max(end, ordered[i][1])
            i += 1
        covered.append((start, end))
    return covered


def split_by_day(iv: Iterable[tuple[datetime, datetime]]) -> dict[date, float]:
    """Hours per workday, cutting intervals at the day boundary."""
    out: dict[date, float] = collections.defaultdict(float)
    for a, b in iv:
        while a < b:
            d = work_date(a)
            end = min(b, day_bounds(d)[1])
            out[d] += (end - a).total_seconds() / 3600
            a = end
    return out


def clip(iv, lo: datetime, hi: datetime):
    return [(max(a, lo), min(b, hi)) for a, b in iv if b > lo and a < hi]


# ---------------------------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------------------------
@dataclass
class Input:
    t: datetime
    kind: str                      # "prompt" | "approval" | "answer"
    read_from: datetime | None   # when the thing you reacted to appeared (agent output, request)
    chars: int = 0                 # prompt length (never the text)
    label: str = ""                # tool name for approvals
    category: str = ""

    def window(self) -> tuple[datetime, datetime]:
        if self.kind == "prompt":
            reading = min(self.t - self.read_from, READ_CAP) if self.read_from and self.read_from <= self.t else timedelta(0)
            typing = min(timedelta(seconds=self.chars / TYPING_CHARS_PER_SEC), TYPING_CAP)
            lead = max(reading + typing, MIN_PROMPT_LEAD)
        else:
            cap = APPROVAL_READ_CAP if self.kind == "approval" else ANSWER_READ_CAP
            lead = min(self.t - self.read_from, cap) if self.read_from and self.read_from <= self.t else cap
            if self.kind == "answer":
                lead += timedelta(seconds=min(self.chars / TYPING_CHARS_PER_SEC, 60))
        lead = min(lead, WINDOW_CAP - AFTER_INPUT)
        return self.t - lead, self.t + AFTER_INPUT


@dataclass
class Work:
    start: datetime
    end: datetime
    worker: str                    # "main" | "subagent:<id>" | "background:<id>" | "remote:<source>"
    trigger: Input | None = None   # the input of yours that started this turn, if any
    capped: bool = False           # a background task that ran past BACKGROUND_CAP and was cut there


@dataclass
class Conversation:
    file: str
    tool: str                      # "claude" | "codex"
    cwd: str = ""
    headless: bool = False
    routine: bool = False
    inputs: list[Input] = field(default_factory=list)
    work: list[Work] = field(default_factory=list)
    kills: list[tuple[datetime, str]] = field(default_factory=list)
    compaction_times: list[datetime] = field(default_factory=list)
    discounted: list[tuple[Input, str]] = field(default_factory=list)
    category: str = ""

    @property
    def compactions(self) -> int:
        return len(self.compaction_times)


# ---------------------------------------------------------------------------------------------
# Claude Code transcripts
# ---------------------------------------------------------------------------------------------
def blocks(content, kind: str) -> list[dict]:
    """The content blocks of one type ("text", "tool_use", "tool_result") of a message."""
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, dict) and b.get("type") == kind]


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    return " ".join(filter(None, (b.get("text") for b in blocks(content, "text"))))


def decided_by_human(record: dict) -> bool:
    """True when the record's permission decision was made by a person (source "user..."),
    False for automatic decisions (rules, modes, hooks) or no decision at all."""
    decision = record.get("permissionDecision")
    if not isinstance(decision, dict):
        return False
    return str(decision.get("source") or "").split(":", 1)[0].startswith("user")


def classify_claude_user(o: dict, sources_seen: bool = False) -> str:
    """What a user-role record that is not a tool result is.

    Returns "yours", "compaction" or "other" (task notifications, teammate/peer messages, messages
    from another session, scheduled prompts, hook output, slash-command output: things that reach the
    agent but that you did not type). sources_seen says the transcript already showed a promptSource
    on another record: recent versions put one on every prompt a person sends (except shell and slash
    commands, TYPED_WITHOUT_SOURCE), so any other record without one is then not yours; the text
    fallback only applies to transcripts that never carry the field.
    """
    if o.get("isCompactSummary"):
        return "compaction"
    if o.get("isMeta"):
        return "other"
    if "promptSource" in o:
        return "yours" if o.get("promptSource") in YOUR_PROMPT_SOURCES else "other"
    if sources_seen:
        # shell commands (!cmd) and slash commands you type are still written without a promptSource
        body = _text_of((o.get("message") or {}).get("content")).lstrip()
        return "yours" if body.startswith(TYPED_WITHOUT_SOURCE) else "other"
    origin = o.get("origin")
    if isinstance(origin, dict) and origin.get("kind") not in (None, "human"):
        return "other"
    text = _text_of((o.get("message") or {}).get("content")).lstrip()
    if not text or text.startswith(NOT_YOURS_PREFIXES):
        return "other"
    return "yours"


def _could_carry_marker(o: dict, text: str) -> bool:
    """A record where the routine marker may sit: written text, not meta, not tool or system markup."""
    body = text.lstrip()
    return bool(body) and not o.get("isMeta") and not body.startswith("<") and not body.startswith(NOT_YOURS_PREFIXES)


_NOTIF_TOOL = re.compile(r"<tool-use-id>([^<]+)</tool-use-id>")


CLAUDE_TYPES = ("user", "assistant", "attachment")


def _read_jsonl(path: str, keep: tuple[str, ...] | None = None):
    """(raw line, parsed object) for each JSON line. With keep, lines that start with a top-level
    "type" not in keep (API request logs, snapshots, titles: most of a transcript's bytes) are
    skipped without parsing."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if not line.strip():
                    continue
                if keep is not None and line.startswith('{"type":"'):
                    end = line.find('"', 9)
                    if line[9:end] not in keep:
                        continue
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                if isinstance(o, dict):
                    yield line, o
    except OSError:
        return


def parse_claude(path: str, conv: Conversation, worker: str = "main", is_sub: bool = False,
                 routine_marker: str = DEFAULT_ROUTINE_MARKER) -> None:
    """Add the inputs, agent work and cut-off markers of one Claude Code transcript to conv."""
    clock = None                          # last user/assistant record (the agent's clock)
    last_out = None                       # last agent output you could have been reading
    open_calls: dict[str, datetime] = {}  # tool calls with no result yet
    questions: set[str] = set()
    bg_requested: dict[str, datetime] = {}
    bg_running: dict[str, datetime] = {}
    trigger: Input | None = None
    tool_names: dict[str, str] = {}
    seen_prompt = False
    sources_seen = False                  # this transcript writes promptSource on prompts
    marker_checked = False

    def add_work(a, b):
        if b > a:
            conv.work.append(Work(a, min(b, a + STEP_CAP), worker, trigger))

    for line, o in _read_jsonl(path, CLAUDE_TYPES):
        typ = o.get("type")
        if not conv.cwd and o.get("cwd") and not is_sub:
            conv.cwd = o["cwd"]
        if o.get("entrypoint") == "sdk-cli" and not is_sub:
            conv.headless = True
        ts = o.get("timestamp")
        if not ts:
            continue
        try:
            t = to_local_naive(ts)
        except ValueError:
            continue

        if typ == "attachment":
            att = o.get("attachment") if isinstance(o.get("attachment"), dict) else {}
            # instructions re-read on a session (re)start, after you had already prompted: a resume
            if att.get("type") == "instructions" and seen_prompt and (RESUME_PHRASE in line or att.get("reason") == "session_start"):
                conv.kills.append((t, "restart"))
            continue
        if typ not in ("user", "assistant"):
            continue
        if bool(o.get("isSidechain")) != is_sub:
            continue
        content = (o.get("message") or {}).get("content")

        if typ == "assistant":
            if clock is not None:
                add_work(clock, t)
            if o.get("isApiErrorMessage") and any(s in line for s in NETWORK_ERRORS):
                conv.kills.append((t, "network"))
            for call in blocks(content, "tool_use"):
                call_id, name = call.get("id"), call.get("name", "")
                open_calls[call_id] = t
                tool_names[call_id] = name
                if name == "AskUserQuestion":
                    questions.add(call_id)
                args = call.get("input") if isinstance(call.get("input"), dict) else {}
                if args.get("run_in_background") and name not in BACKGROUND_SKIP_TOOLS:
                    bg_requested[call_id] = t
            last_out = t
            clock = t
            continue

        # user-role record
        results = blocks(content, "tool_result")
        if results:
            waited_for_you = False
            by_person = decided_by_human(o)
            for res in results:
                call_id = res.get("tool_use_id")
                request_at = open_calls.pop(call_id, None)
                if call_id in questions:
                    conv.inputs.append(Input(t, "answer", request_at or last_out,
                                             chars=len(_text_of(res.get("content")) or ""), label="question"))
                    waited_for_you = True
                elif by_person:
                    conv.inputs.append(Input(t, "approval", request_at or last_out, label=tool_names.get(call_id) or "tool"))
                    waited_for_you = True
                outcome = o.get("toolUseResult")
                if call_id in bg_requested and isinstance(outcome, dict) and outcome.get("backgroundTaskId"):
                    bg_running[call_id] = bg_requested.pop(call_id)
            if not waited_for_you and clock is not None:
                add_work(clock, t)
            clock = t
            continue

        if "promptSource" in o:
            sources_seen = True
        kind = classify_claude_user(o, sources_seen)
        text = _text_of(content)
        if not marker_checked and kind != "compaction" and _could_carry_marker(o, text):
            marker_checked = True
            if routine_marker and routine_marker in text and not is_sub:
                conv.routine = True
        if kind == "compaction":
            conv.compaction_times.append(t)
            trigger = None
            clock = t
            continue
        if text.lstrip().startswith("<task-notification"):
            if MEMORY_KILL in text:
                conv.kills.append((t, "memory"))
            found = _NOTIF_TOOL.search(text)
            if found and found.group(1) in bg_running:
                began = bg_running.pop(found.group(1))
                conv.work.append(Work(began, min(t, began + BACKGROUND_CAP), f"background:{found.group(1)}", None,
                                      capped=t - began > BACKGROUND_CAP))
        if kind == "yours" and not is_sub:
            if open_calls and clock is not None and t - clock >= RESUME_GAP:
                conv.kills.append((clock, "died"))  # the session died with tool calls in flight
                open_calls.clear()
            prompt = Input(t, "prompt", last_out, chars=len(text))
            conv.inputs.append(prompt)
            trigger = prompt
            seen_prompt = True
        else:
            trigger = None
        clock = t


def _claude_headless(path: str) -> bool:
    for i, (_, o) in enumerate(_read_jsonl(path, CLAUDE_TYPES)):
        if o.get("entrypoint"):
            return o["entrypoint"] == "sdk-cli"
        if i > 60:
            break
    return False


def subagent_files(main_path: str) -> list[str]:
    base = main_path[:-len(".jsonl")]
    return sorted(f for f in glob.glob(os.path.join(base, "subagents", "**", "*.jsonl"), recursive=True)
                  if os.path.basename(f).startswith("agent"))


def load_claude_file(path: str, include_headless=False, routine_marker=DEFAULT_ROUTINE_MARKER) -> Conversation | None:
    conv = Conversation(file=path, tool="claude")
    if not include_headless and _claude_headless(path):
        return None
    parse_claude(path, conv, routine_marker=routine_marker)
    if conv.routine or (conv.headless and not include_headless):
        return None
    for sub in subagent_files(path):
        parse_claude(sub, conv, worker="subagent:" + os.path.basename(sub)[:-6], is_sub=True)
    if conv.headless:  # included on request: agent hours only, nobody typed these prompts
        conv.inputs = []
    apply_discounts(conv)
    return conv


# ---------------------------------------------------------------------------------------------
# Codex CLI transcripts
# ---------------------------------------------------------------------------------------------
def _codex_text(content) -> str:
    if not isinstance(content, list):
        return ""
    return " ".join(filter(None, (b.get("text") for b in content if isinstance(b, dict))))


def load_codex_file(path: str, include_headless=False, routine_marker=DEFAULT_ROUTINE_MARKER) -> Conversation | None:
    conv = Conversation(file=path, tool="codex")
    prev_t = last_out = approval_req = compacted_at = None
    trigger = None
    seen_prompt = False
    marker_checked = False
    is_sub = False
    timestamped = False

    for line, o in _read_jsonl(path):
        typ = o.get("type")
        p = o.get("payload") if isinstance(o.get("payload"), dict) else {}
        if typ == "session_meta":
            conv.cwd = p.get("cwd") or conv.cwd
            src = p.get("source")
            if p.get("originator") == "codex_exec" or src == "exec":
                conv.headless = True
            if isinstance(src, dict) and "subagent" in src:
                is_sub = True
            if conv.headless and not include_headless:
                return None  # a script ran it: stop reading here
            continue
        if typ == "turn_context":
            conv.cwd = conv.cwd or p.get("cwd") or ""
        ts = o.get("timestamp")
        if not ts:
            continue
        try:
            t = to_local_naive(ts)
        except ValueError:
            continue
        timestamped = True
        ptype = p.get("type")

        if typ == "compacted" or ptype in ("compacted", "compaction", "context_compacted"):
            conv.compaction_times.append(t)
            compacted_at = t
            trigger = None
            prev_t = t
            continue
        if typ == "event_msg" and ptype and ptype.endswith("approval_request"):
            approval_req = t
            if prev_t is not None:
                conv.work.append(Work(prev_t, min(t, prev_t + STEP_CAP), "main", trigger))
            prev_t = t
            continue
        if typ == "event_msg" and ptype in ("error", "stream_error") and any(s in line for s in NETWORK_ERRORS):
            conv.kills.append((t, "network"))
            continue

        if typ == "response_item" and ptype == "message" and p.get("role") == "user":
            text = _codex_text(p.get("content"))
            if text.lstrip().startswith(CODEX_INJECTED_PREFIXES):
                continue  # environment context, AGENTS.md, instructions: not a turn
            if not marker_checked and text.strip():
                marker_checked = True
                if routine_marker and routine_marker in text:
                    conv.routine = True
            if compacted_at and t - compacted_at <= timedelta(seconds=5):
                trigger = None  # the summary Codex re-injects after compacting: not yours
            elif conv.headless or is_sub:
                trigger = None
            else:
                inp = Input(t, "prompt", last_out, chars=len(text))
                conv.inputs.append(inp)
                trigger = inp
                seen_prompt = True
            prev_t = t
            continue

        is_work = (typ == "response_item" and ptype in CODEX_WORK_ITEMS and p.get("role") not in ("user", "developer", "system")) \
            or (typ == "event_msg" and ptype in CODEX_WORK_EVENTS)
        if not is_work:
            continue
        if approval_req is not None:
            conv.inputs.append(Input(t, "approval", approval_req, label="exec"))
            approval_req = None
        elif prev_t is not None:
            conv.work.append(Work(prev_t, min(t, prev_t + STEP_CAP), "main", trigger))
        last_out = t
        prev_t = t

    if not timestamped or conv.routine or (conv.headless and not include_headless):
        return None
    if is_sub:
        for w in conv.work:
            w.worker = "subagent:" + os.path.basename(path)
            w.trigger = None
    apply_discounts(conv)
    return conv


# ---------------------------------------------------------------------------------------------
# Discounts
# ---------------------------------------------------------------------------------------------
def apply_discounts(conv: Conversation) -> None:
    """Drop the prompts that only restart work cut off by the machine.

    A prompt of yours is a restart when at least one cut-off marker (memory kill, network error,
    session resume, session died mid tool call) happened after your previous prompt, within
    KILL_WINDOW before it. Several markers of the same cut still discount one prompt. The agent work
    that follows is kept: only your input is not counted as attention.
    """
    if not conv.kills:
        return
    kills = sorted(conv.kills)
    prompts = sorted((x for x in conv.inputs if x.kind == "prompt"), key=lambda x: x.t)
    drop = set()
    prev = None
    for x in prompts:
        if prev is not None:  # the first prompt of a conversation is never a restart
            hit = [(k, why) for k, why in kills if prev.t < k <= x.t and x.t - k <= KILL_WINDOW]
            if hit:
                drop.add(id(x))
                conv.discounted.append((x, hit[0][1]))
        prev = x
    if drop:
        conv.inputs = [x for x in conv.inputs if id(x) not in drop]
        for w in conv.work:
            if w.trigger is not None and id(w.trigger) in drop:
                w.trigger = None


# ---------------------------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------------------------
def claude_main_files(root: str) -> list[str]:
    return sorted(glob.glob(os.path.join(root, "*", "*.jsonl")))


def codex_files(root: str) -> list[str]:
    return sorted(glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True))


def _recent(path: str, since: datetime | None) -> bool:
    if since is None:
        return True
    try:
        newest = os.path.getmtime(path)
        base = path[:-len(".jsonl")]
        if os.path.isdir(base):
            for f in glob.glob(os.path.join(base, "subagents", "**", "*.jsonl"), recursive=True):
                newest = max(newest, os.path.getmtime(f))
        return datetime.fromtimestamp(newest) >= since
    except OSError:
        return False


def load_all(claude_root: str | None, codex_root: str | None, since: datetime | None = None,
             include_headless=False, routine_marker=DEFAULT_ROUTINE_MARKER, exclude_dirs=()) -> list[Conversation]:
    convs = []
    if claude_root and os.path.isdir(claude_root):
        for f in claude_main_files(claude_root):
            if _recent(f, since):
                c = load_claude_file(f, include_headless, routine_marker)
                if c:
                    convs.append(c)
    if codex_root and os.path.isdir(codex_root):
        for f in codex_files(codex_root):
            if _recent(f, since):
                c = load_codex_file(f, include_headless, routine_marker)
                if c:
                    convs.append(c)
    norm = lambda p: (p or "").replace("\\", "/").rstrip("/").lower()
    ex = [norm(os.path.expanduser(d)) for d in exclude_dirs if d]
    return [c for c in convs if not any(norm(c.cwd) == e or norm(c.cwd).startswith(e + "/") for e in ex)]


# ---------------------------------------------------------------------------------------------
# Categories, meetings, remote work
# ---------------------------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "categories": [],
    "coordination": {"name": "Coordination", "dir_suffix": "", "definition": "Sessions opened at the root of your work, with no repo."},
    "meeting": {"name": "Questions during meetings", "definition": "Every input written during a calendar meeting with other attendees."},
    "other": {"name": "Other", "definition": "Everything else."},
    "routine_marker": DEFAULT_ROUTINE_MARKER,
}


def load_config(path: str | None) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            user = json.load(fh)
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    return cfg


def category_of(cwd: str, cfg: dict) -> str:
    """First category whose match fragment appears in the working directory; then the coordination
    folder; then Other. Case-insensitive, forward slashes."""
    p = (cwd or "").replace("\\", "/").lower().rstrip("/")
    for c in cfg.get("categories", []):
        if any(m.lower().replace("\\", "/") in p for m in c.get("match", []) if m):
            return c["name"]
    suffix = (cfg.get("coordination", {}).get("dir_suffix") or "").lower().rstrip("/")
    if suffix and p.endswith(suffix):
        return cfg["coordination"]["name"]
    return cfg["other"]["name"]


def meetings_from(path: str) -> list[tuple[datetime, datetime]]:
    """Real meetings from a Google Calendar events-list JSON: timed (not all-day), not cancelled, busy
    (not transparent), you did not decline, at least two attendees, 3 hours or less."""
    with open(path, encoding="utf-8") as fh:
        items = json.load(fh).get("items", [])
    out = []
    for e in items:
        s, t = e.get("start") or {}, e.get("end") or {}
        att = e.get("attendees") or []
        if "dateTime" not in s or "dateTime" not in t:
            continue
        if e.get("status") == "cancelled" or e.get("transparency") == "transparent" or len(att) < 2:
            continue
        if any(x.get("self") and x.get("responseStatus") == "declined" for x in att):
            continue
        a, b = to_local_naive(s["dateTime"]), to_local_naive(t["dateTime"])
        if timedelta(0) < b - a <= MEETING_MAX:
            out.append((a, b))
    return sorted(out)


class MeetingIndex:
    def __init__(self, meetings):
        self.m = union(meetings)
        self.starts = [a for a, _ in self.m]

    def __contains__(self, t: datetime) -> bool:
        i = bisect.bisect_right(self.starts, t) - 1
        return i >= 0 and self.m[i][0] <= t <= self.m[i][1]


def load_remote(paths: Iterable[str]) -> list[tuple[str, datetime, datetime, str]]:
    """Remote agent work: JSON lines ["<category>", "<start ISO>", "<end ISO>", "<source>"].
    Identical lines (the same run listed in two files) count once."""
    seen, out = set(), []
    for path in paths:
        try:
            fh = open(path, encoding="utf-8")
        except OSError:
            continue
        with fh:
            for line in fh:
                s = line.strip()
                if not s or s in seen:
                    continue
                seen.add(s)
                try:
                    name, a, b, src = json.loads(s)
                    a, b = to_local_naive(a), to_local_naive(b)
                except (ValueError, TypeError):
                    continue
                if b > a:
                    out.append((name, a, b, src))
    return out


# ---------------------------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------------------------
def fair_split(windows_by_cat: dict[str, list]) -> dict[str, float]:
    """Hours of attention per category. Where windows of several categories overlap, that time is
    split evenly between them, so the categories add up to your total attention."""
    ev = []
    for c, iv in windows_by_cat.items():
        for a, b in union(iv):
            ev += [(a, 1, c), (b, -1, c)]
    ev.sort(key=lambda x: (x[0], x[1]))
    out: dict[str, float] = collections.defaultdict(float)
    active: collections.Counter = collections.Counter()
    last = None
    for t, d, c in ev:
        if last is not None:
            live = [k for k, v in active.items() if v > 0]
            for k in live:
                out[k] += (t - last).total_seconds() / 3600 / len(live)
        active[c] += d
        last = t
    return dict(out)


def sittings(times: list[datetime], gap=SITTING_BREAK) -> list[tuple[datetime, datetime]]:
    out = []
    for t in sorted(times):
        if out and t - out[-1][1] <= gap:
            out[-1][1] = t
        else:
            out.append([t, t])
    return [(a, b) for a, b in out]


def ratio(agent: float, attention: float):
    return round(agent / attention, 2) if attention >= 0.05 else None


def compute(convs: list[Conversation], cfg: dict, days: int = DEFAULT_DAYS, today: date | None = None,
            meetings=(), remote=(), recommendations: dict | None = None) -> dict:
    today = today or work_date(datetime.now())
    cut = today - timedelta(days=days - 1)
    lo, hi = day_bounds(cut)[0], day_bounds(today)[1]
    mi = MeetingIndex(meetings)
    meeting_name = cfg["meeting"]["name"]

    inputs: list[Input] = []
    work: list[tuple[str, str, Work]] = []
    disc = collections.Counter()
    compactions = 0
    per_session = []
    for conv in convs:
        conv.category = category_of(conv.cwd, cfg)
        for x in conv.inputs:
            x.category = meeting_name if x.t in mi else conv.category
        for w in conv.work:
            cat = w.trigger.category if w.trigger is not None and w.trigger.category else conv.category
            work.append((cat, conv.file, w))
        ins = [x for x in conv.inputs if lo <= x.t < hi]
        inputs += ins
        disc.update(why for x, why in conv.discounted if lo <= x.t < hi)
        compactions += sum(1 for c in conv.compaction_times if lo <= c < hi)
        if ins:
            per_session.append((conv, ins))
    for name, a, b, src in remote:
        work.append((name, "remote", Work(a, b, "remote:" + src)))

    # attention
    win_by_cat: dict[str, list] = collections.defaultdict(list)
    for x in inputs:
        win_by_cat[x.category].append(x.window())
    win_by_cat = {k: clip(v, lo, hi) for k, v in win_by_cat.items()}
    all_windows = union([w for v in win_by_cat.values() for w in v])
    total_att = hours(all_windows)
    att_by_cat = fair_split(win_by_cat)

    # agent time: merged per worker, summed over workers (parallel work counts fully)
    by_worker: dict[tuple[str, str, str], list] = collections.defaultdict(list)
    capped_h, capped_tasks = 0.0, 0
    for cat, conv_file, w in work:
        by_worker[(cat, conv_file, w.worker)].append((w.start, w.end))
        if w.capped:
            inside = clip([(w.start, w.end)], lo, hi)
            if inside:
                capped_tasks += 1
                capped_h += hours(inside)
    agent_iv_by_cat: dict[str, list] = collections.defaultdict(list)
    agent_by_cat: dict[str, float] = collections.defaultdict(float)
    agent_days: dict[date, float] = collections.defaultdict(float)
    remote_by_cat: dict[str, float] = collections.defaultdict(float)
    by_kind: dict[str, float] = collections.defaultdict(float)
    for (cat, _, worker), iv in by_worker.items():
        m = clip(union(iv), lo, hi)
        h = hours(m)
        agent_by_cat[cat] += h
        by_kind[worker.split(":")[0]] += h
        if worker.startswith("remote:"):
            remote_by_cat[cat] += h
        agent_iv_by_cat[cat] += m
        for d, v in split_by_day(m).items():
            agent_days[d] += v
    total_agent = sum(agent_by_cat.values())

    att_days = split_by_day(all_windows)
    daily = []
    for i in range(days):
        d = cut + timedelta(days=i)
        a, g = att_days.get(d, 0.0), agent_days.get(d, 0.0)
        daily.append({"date": d.isoformat(), "attention": round(a, 2), "agent": round(g, 2), "ratio": ratio(g, a)})

    defs = {c["name"]: c.get("definition", "") for c in cfg.get("categories", [])}
    kinds = {c["name"]: c.get("kind", "delegable") for c in cfg.get("categories", [])}
    for k, kind in (("coordination", "coordination"), ("meeting", "meeting"), ("other", "delegable")):
        defs[cfg[k]["name"]] = cfg[k].get("definition", "")
        kinds[cfg[k]["name"]] = kind

    folders: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    sessions_by_cat: dict[str, list] = collections.defaultdict(list)
    for conv, ins in per_session:
        folder = (conv.cwd or "?").replace("\\", "/").rstrip("/").split("/")[-1] or "?"
        for cat in {x.category for x in ins}:
            mine = [x for x in ins if x.category == cat]
            h = hours(union(x.window() for x in mine))
            folders[cat][folder] += h
            sessions_by_cat[cat].append({"file": conv.file, "tool": conv.tool, "folder": folder,
                                         "from": mine[0].t.isoformat(timespec="minutes"),
                                         "to": mine[-1].t.isoformat(timespec="minutes"),
                                         "attention_h": round(h, 2), "inputs": len(mine),
                                         "approvals": sum(1 for x in mine if x.kind == "approval")})

    rows = []
    for cat in sorted(set(att_by_cat) | set(agent_by_cat)):
        mine = sorted((x for x in inputs if x.category == cat), key=lambda x: x.t)
        att, ag = att_by_cat.get(cat, 0.0), agent_by_cat.get(cat, 0.0)
        sit = sittings([x.t for x in mine])
        sit_len = sorted(((b - a) + AFTER_INPUT + MIN_PROMPT_LEAD).total_seconds() / 60 for a, b in sit)
        active = hours(union([x.window() for x in mine] + agent_iv_by_cat.get(cat, [])))
        approvals = sum(1 for x in mine if x.kind == "approval")
        rows.append({
            "category": cat, "kind": kinds.get(cat, "delegable"), "definition": defs.get(cat, ""),
            "attention": round(att, 2), "agent": round(ag, 2), "ratio": ratio(ag, att),
            "remote": round(remote_by_cat.get(cat, 0.0), 2),
            "inputs": len(mine), "approvals": approvals,
            "approval_share": round(approvals / len(mine), 2) if mine else None,
            "inputs_per_hour": round(len(mine) / active, 1) if active >= 0.05 else None,
            "active_hours": round(active, 2),
            "sittings": len(sit), "median_sitting_min": round(sit_len[len(sit_len) // 2]) if sit_len else None,
            "folders": {k: round(v, 2) for k, v in folders[cat].most_common(10)},
            "approved_tools": dict(collections.Counter(x.label for x in mine if x.kind == "approval").most_common(5)),
        })
    rows.sort(key=lambda r: -r["attention"])

    approvals = sum(1 for x in inputs if x.kind == "approval")
    return {
        "since": cut.isoformat(), "until": today.isoformat(), "days": days, "attention_profile": attention_profile,
        "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": {"attention": round(total_att, 2), "agent": round(total_agent, 2), "ratio": ratio(total_agent, total_att),
                  "inputs": len(inputs), "prompts": sum(1 for x in inputs if x.kind == "prompt"),
                  "approvals": approvals, "answers": sum(1 for x in inputs if x.kind == "answer"),
                  "sittings": len(sittings([x.t for x in inputs])), "conversations": len(per_session),
                  "agent_by_worker": {**{k: round(by_kind.get(k, 0.0), 2) for k in ("main", "subagent", "background", "remote")},
                                      "background_capped_h": round(capped_h, 2), "background_capped_tasks": capped_tasks,
                                      "background_cap_h": BACKGROUND_CAP.total_seconds() / 3600}},
        "discounts": {"restart_prompts": dict(disc), "compactions": compactions},
        "meetings": len(meetings),
        "daily": daily,
        "rows": rows,
        "recommendations": recommendations or {},
        "_sessions": {k: sorted(v, key=lambda s: -s["attention_h"]) for k, v in sessions_by_cat.items()},
    }

