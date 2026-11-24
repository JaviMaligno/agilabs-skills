# agent-multiplier

How many hours did your coding agents work for each hour of your attention? `agent-multiplier`
answers that from the transcripts Claude Code and Codex CLI already keep on your machine, splits the
figure by kind of work (clients, writing, coordination, questions asked during meetings), and writes a
single-file HTML page with the global figure, a daily trend and a per-category table.

Python 3.10+, standard library only. Local and read-only: it never prints or stores what you typed
(only lengths, tool names and timestamps) and never sends anything.

## Quick start

```bash
cp -R productivity/agent-multiplier ~/.claude/skills/agent-multiplier
cd ~/.claude/skills/agent-multiplier

# 1. the figure for the last 28 days, and the page (output folders are created if missing)
python3 -I scripts/agent_multiplier.py --html ~/.agent-multiplier/out/latest.html
open ~/.agent-multiplier/out/latest.html

# 2. categories: draft them from your repos, edit, save as config.json
python3 -I scripts/draft_config.py            # -> ~/.agent-multiplier/config.draft.json
cp config.example.json ~/.agent-multiplier/config.json   # or start from the template

# 3. look inside one session (no prompt text unless you add --show-text)
python3 -I scripts/session_timeline.py ~/.claude/projects/<project>/<session>.jsonl

# tests
python3 -m unittest discover -s ~/.claude/skills/agent-multiplier
```

Or just ask Claude Code "what's my multiplier?" once the skill is installed.

Optional inputs, all in `~/.agent-multiplier/` (or `AGENT_MULTIPLIER_HOME`):

| File | Format | Effect |
|---|---|---|
| `config.json` | see `config.example.json` | categories by working directory, coordination folder, routine marker, excluded folders |
| `calendar.json` | Google Calendar `events.list` JSON | inputs written during real meetings go to "Questions during meetings" |
| `remote/*.jsonl` | `["<category>", "<start ISO>", "<end ISO>", "<source>"]` per line | agent hours with no local transcript (cloud routines, CI agents); never attention |
| `recommendations/*.json` | see below | a "What to change" section on the page |

`scripts/install-routine-macos.sh [HH:MM]` installs an opt-in launchd job that recomputes the page
daily (`--uninstall` removes it).

## How it is measured

The figure is **agent hours ÷ attention hours** over a window (28 days by default; days start at
04:00 so late nights count for the day before). Every parameter below is a named constant at the top
of `scripts/measure.py`.

### What counts as an input of yours

| Counted as yours | Not yours |
|---|---|
| A prompt you typed, queued or accepted from a suggestion | Task notifications, teammate/peer messages, messages from another agent session, scheduled prompts, hook and command output |
| A permission you granted or denied by hand (`permissionDecision.source` = `user…`) | Tool calls auto-approved by rules, modes or classifiers |
| Your answer to a question the agent asked (`AskUserQuestion`) | Context-compaction summaries (the tool writes them as a user message) |
| Codex: a user message that is not injected context; an approval after an `…approval_request` | Headless runs (`claude -p`, `codex exec`): a script typed those prompts |

Recent Claude Code versions write `promptSource` on every prompt a person sends, except shell (`!cmd`)
and slash commands. Once a transcript has shown the field, any other user message without it (for
example "Another Claude session sent …") is not yours. Older transcripts that never carry it fall
back to: a user text message that is not meta, not a compaction and does not start with tool or
system markup. Codex: injected context (environment, `# AGENTS.md instructions …`) is never a prompt,
and the routine marker is looked for in the first message you actually wrote.

### Attention windows

Each input opens a window that ends `AFTER_INPUT` (30 s) after it, the time to see the agent pick it
up, and starts earlier by:

- **prompt**: reading the agent's last output (time since that output, at most `READ_CAP` = 2 min)
  plus typing (length ÷ `TYPING_CHARS_PER_SEC` = 5 chars/s, at most `TYPING_CAP` = 3 min), at least
  `MIN_PROMPT_LEAD` = 10 s;
- **approval**: time since the request, at most `APPROVAL_READ_CAP` = 30 s;
- **answer**: time since the question, at most `ANSWER_READ_CAP` = 60 s, plus typing up to 60 s.

No window is longer than `WINDOW_CAP` = 5 min. Overlapping windows are merged, across all
conversations, so attention is wall-clock time: two sessions you juggle in the same minute cost one
minute. Time you spend thinking away from the keyboard is not measured; the figure is a lower bound
on attention, consistently.

#### Attention profiles

The values above are the `conservative` profile, the default: only reading the last output and
typing. Pass `--attention generous` to also count reviewing what the agent produced and thinking
before you reply, which fits work where you read long drafts, diffs or videos before answering:

| Parameter | conservative | generous |
|---|---|---|
| `READ_CAP` | 2 min | 8 min |
| `TYPING_CHARS_PER_SEC` | 5 | 3 |
| `TYPING_CAP` | 3 min | 5 min |
| `APPROVAL_READ_CAP` | 30 s | 60 s |
| `ANSWER_READ_CAP` | 60 s | 3 min |
| `AFTER_INPUT` | 30 s | 90 s |
| `WINDOW_CAP` | 5 min | 12 min |

On the same transcripts the generous profile gives a lower multiplier. Neither is the true figure:
pick the one that matches how you work, keep it, and compare yourself over time with the same
profile. The page and the JSON say which profile was used.

### Agent working time

A transcript is a sequence of records. The gap before each agent record (a model message or a tool
result) is agent work, capped at `STEP_CAP` = 30 min per step; the gap before one of your inputs or a
notification is idle (the agent was waiting). Waiting for a permission or an answer from you is not
work either. Workers:

- **main agent**: its turns in the main transcript;
- **subagents**: each `subagents/**/agent-*.jsonl` file of the conversation, same rule;
- **background tasks**: a shell command launched in the background runs from its launch to the
  notification that it finished, at most `BACKGROUND_CAP` = 2 h (background *agents* are already
  counted through their own subagent transcript). Tasks that hit the cap are reported apart
  (`background_capped_h`, `background_capped_tasks`, printed and shown on the page): they are often
  watch or poll loops waiting on something, and can inflate the figure;
- **remote**: the runs in `remote/*.jsonl`.

Each worker's intervals are merged, then **workers are summed**: three subagents working in parallel
for an hour are three agent hours. That is the point of the measure: parallel work multiplies. The
page shows the split by worker so you can see what drives the figure.

### Discounts

Some prompts only restart work the machine cut off; they are not part of working with agents. A
prompt of yours is dropped from your inputs when, since your previous prompt and within `KILL_WINDOW`
= 12 h before it, one of these happened (several markers of the same cut drop one prompt; the first
prompt of a conversation is never dropped):

- **memory**: a task notification saying a task was stopped because the system was running low on memory;
- **network**: an API error saying the server could not be reached (`NETWORK_ERRORS`);
- **restart**: the session re-read its instructions on (re)start after you had already prompted, as on resume;
- **died**: tool calls with no result, then your prompt `RESUME_GAP` = 2 min or more later.

Also left out: context compactions (never yours), whole conversations whose first prompt carries the
routine marker (`routine_marker`, default `[agent-multiplier-routine]`, for your own scheduled
automation), folders in `exclude_dirs`, and headless runs unless `--include-headless` (then their
agent hours count, with no attention).

### Breakdown by kind of work

- Each conversation gets the **category** of its working directory: the first category in
  `config.json` with a `match` fragment contained in the path (case-insensitive), else the
  coordination folder (`dir_suffix`), else Other.
- An input written during a **meeting** goes to "Questions during meetings", whatever the
  conversation. Real meetings: timed (not all-day), not cancelled, busy, not declined by you, at least
  two attendees, 3 h or less. The agent turn that input started goes there too.
- Where windows of several categories overlap, that **attention is split evenly**, so categories add
  up to your total.
- Per category: attention h, agent h, multiplier, inputs per active hour (active = your windows or an
  agent working), share of inputs that were approvals, sittings (runs of inputs with no gap over
  `SITTING_BREAK` = 30 min) and their median length.
- `--evidence` writes, per category, the sessions with most attention, for investigating.

### Recommendations format

`recommendations/<anything>.json`, one per category, written after reading real sessions (see
`examples/recommendations/writing.json`, fictional):

```json
{"category": "Writing", "summary": "...",
 "recommendations": [{"title": "", "evidence": "", "change": "", "fits": "", "saving": "",
                      "effort": "", "who": "", "measure": ""}],
 "not_worth": [{"what": "", "why": ""}],
 "sessions_read": []}
```

## Limits

- Attention is inferred from inputs; reading a long diff without typing anything is invisible.
- Transcript formats change between tool versions; unknown records are ignored, so a format change
  shows up as missing inputs or work rather than a crash. Codex transcripts without timestamps
  (2025 format) are skipped.
- Reading a few GB of transcripts takes a minute or two.

## Credits

Original idea and methodology: Juan Iglesias. This implementation was written from scratch by Javier
Aguilar ([AGILabs](https://javieraguilar.ai)); the discounts, the breakdown by kind of work and the
recommendations layer are Javier's.
