---
name: agent-multiplier
description: >
  Measures your agent multiplier: hours your coding agents (Claude Code and Codex CLI) worked per hour
  of your attention, from the local transcripts, with a breakdown by kind of work, a daily trend and a
  self-contained HTML page. Use when the user asks about "my multiplier", "agent hours vs my hours",
  "how much do my agents work for me", "where do I lose time with agents", "which kind of work gives
  me the most leverage", wants to recompute or publish the multiplier page, investigate a category,
  write recommendations, add remote agent work, or set up the daily routine.
---

# Agent multiplier

How many hours did your agents work for each hour of your attention? This skill answers that from the
transcripts Claude Code (`~/.claude/projects`) and Codex CLI (`~/.codex/sessions`) already keep on
disk. Python 3.10+, standard library only. The model is explained in `README.md` ("How it is
measured"); read it before interpreting a figure for the user.

**Privacy.** Everything runs locally and read-only. The scripts read only the transcripts and the
optional files below, never print or store prompt text (only lengths, tool names and timestamps),
and never send anything anywhere. `session_timeline.py --show-text` is the only way to see text, and
only when the user asks for it.

## Files

| Path | What |
|---|---|
| `scripts/agent_multiplier.py` | The report: global figure, daily trend, per-category table; `--html`, `--json`, `--evidence` |
| `scripts/measure.py` | Parsing and the model (all parameters are named constants at the top) |
| `scripts/session_timeline.py` | Compact timeline of one transcript, for investigating a category |
| `scripts/draft_config.py` | Draft of `config.json` from your transcripts (categories by git remote owner) |
| `scripts/page.html` | Page template (single file, no external assets, light/dark) |
| `scripts/routine-macos.sh`, `scripts/install-routine-macos.sh` | Optional daily run with launchd |
| `config.example.json` | Category template |
| `examples/` | Fictional recommendation and remote-work files showing the formats |

User data lives in `~/.agent-multiplier/` (override with `AGENT_MULTIPLIER_HOME`): `config.json`,
`calendar.json`, `remote/*.jsonl`, `recommendations/*.json`, `out/`, `snapshots/`.

## Steps

Every command below is relative to this skill's folder (the one holding this SKILL.md). Run them as
`cd "${CLAUDE_SKILL_DIR:-$HOME/.claude/skills/agent-multiplier}" && python3 -I scripts/...`, or put
that folder in front of `scripts/`: the agent's working directory is usually the user's project, not
the skill.

1. **Compute.** `python3 -I scripts/agent_multiplier.py --html ~/.agent-multiplier/out/latest.html --json ~/.agent-multiplier/out/latest.json`
   (default window 28 days, `--days N` to change; missing output folders such as
   `~/.agent-multiplier/out` are created). It takes one to two minutes on a few GB of
   transcripts. Report the first lines it prints: the multiplier, agent hours, your attention hours,
   the split of agent hours by worker and what was discounted. Open the page for the user if they want it.
2. **Categories (first time).** Without a config everything lands in "Other". Run
   `python3 -I scripts/draft_config.py`, show the user the draft (`~/.agent-multiplier/config.draft.json`),
   let them rename, merge or split, and save it as `~/.agent-multiplier/config.json`. Or copy
   `config.example.json` and edit it. Never overwrite an existing `config.json` without asking.
3. **Meetings (optional).** Save a Google Calendar events-list JSON as `~/.agent-multiplier/calendar.json`
   (`items` with `start`, `end`, `status`, `transparency`, `attendees(self, responseStatus)`), for example
   with `gws calendar events list --params '{"calendarId":"primary","timeMin":"<ISO>","timeMax":"<ISO>","singleEvents":true,"maxResults":2500}'`.
   Inputs written during real meetings go to "Questions during meetings".
4. **Remote agent work (optional).** Agents that ran with no local transcript (cloud routines, CI jobs
   that run an agent) go in `~/.agent-multiplier/remote/<source>.jsonl`, one line per run:
   `["<category>", "<start ISO>", "<end ISO>", "<source>"]` (see `examples/remote.example.jsonl`).
   They add agent hours, never attention. Identical lines count once.
5. **Investigate and recommend (optional).** Run step 1 with `--evidence ~/.agent-multiplier/out/evidence.json`:
   it lists, per category, the sessions with the most attention. For the categories that matter, read
   a few of those sessions with `python3 -I scripts/session_timeline.py <file> --from <ISO> --to <ISO>`
   (gaps, your inputs, tools, cut-offs; add `--show-text` only if the user agrees) and the repo itself,
   then write `~/.agent-multiplier/recommendations/<category>.json` in the format of
   `examples/recommendations/writing.json`. Nothing generic: each recommendation comes from a case you
   read, says the exact change and whether it fits that kind of work. Re-run step 1 so the page shows them.
   Use read-only subagents for this if the work is large; no tests, builds or commits.
6. **Daily routine (optional, macOS).** `scripts/install-routine-macos.sh [HH:MM]` installs a launchd job
   that recomputes the page every day (`--uninstall` removes it). Set `AGENT_MULTIPLIER_CALENDAR_CMD` to
   refresh the calendar first. If an agent session is part of the routine (for example to publish the
   page), start its first prompt with the routine marker (`routine_marker` in config, default
   `[agent-multiplier-routine]`) so it does not count as your work.

## Interpreting

- The attention profile (`--attention conservative|generous`, default conservative) changes the figure a lot: generous counts reviewing and thinking time, so it gives a lower multiplier. Say which profile the figure uses and only compare figures computed with the same one. If the person reviews long outputs (drafts, diffs, videos) before replying, offer the generous profile.

- Compare figures only with the same script version and the same window length.
- A low multiplier is expected in interactive work (writing, meetings, coordination); say so rather
  than recommending to raise it there. The lever is usually what runs elsewhere meanwhile.
- A high approvals share means permission prompts are eating attention: look at which tools get
  approved by hand in the evidence before suggesting rules.
- Background shell tasks count as agent time up to 2 h each. The report prints how many hit that cap
  and how many hours they add (`background_capped_h`); when that is a large share of agent hours,
  say so and give the figure without them too (watch and poll loops count as work otherwise).
- Messages from other agent sessions, injected context (AGENTS.md) and compaction summaries are never
  counted as your inputs.
