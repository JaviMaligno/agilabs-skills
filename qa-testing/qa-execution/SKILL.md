---
name: qa-execution
description: Use to execute a QA plan against a live deployment — walk each SPEC-ID, capture evidence (screenshots, DB queries, logs), detect bugs **not in the spec** that surface during verification (i18n placeholders unresolved, async pipelines stuck, broken HTML markers, opaque tooltips, queue/worker mismatches), and produce a report with per-SPEC status plus a separate bugs list. Invoke when the user says "run QA against prod", "verify the spec on prod", "execute the QA walkthrough", "capture the evidence for the QA plan", or once a QA plan doc (from `qa-design`) exists and it is time to verify. Tool-agnostic — visual evidence may come from playwright-cli, MCP browser, manual nav, screenshots; DB / log evidence from ad-hoc scripts. The reporting and bug-hunt discipline are the same regardless of the capture tool.
---

# QA Execution

## When this skill applies

You have a QA plan document — produced by `qa-design` or written by hand — and need to verify, against a live deployment, that each point is actually delivered. The deliverable is a **report** (not code, not tests). Bugs encountered along the way are surfaced and tracked separately from the spec coverage.

Trigger examples:
- "Run QA against prod for the feedback we delivered."
- "Execute the QA plan we put together."
- "Capture screenshots per SPEC-ID from the QA document."
- "Confirm what we built matches what the client asked for, with evidence."

If there is no QA plan yet, stop and run `qa-design` first. If there is no spec inventory, run `spec-driven-development` even earlier.

## Core principles

1. **Verify what the spec asked for. Report bugs that show up while verifying.** Spec coverage and bug-hunt are different outputs; don't mix them.
2. **Evidence before assertions.** "It works" without a screenshot, a DB query, or a log excerpt isn't QA — it's optimism. Every ✅ in the final report carries one piece of evidence.
3. **Production data may not match the spec setup.** Fixtures, masters, or pipelines that the spec assumes may have drifted. Detect drift; don't fabricate it.
4. **Cleanup is part of QA.** Test projects, drafts, customers seeded for the run must be deleted at the end. Tag them with a prefix so cleanup is mechanical.

## Workflow

### Phase 0 — Prerequisites check

Before opening a browser or running a script:

- **Is there a QA plan?** A file like `docs/qa-evidence/<date>/<feature>-qa-plan.md` with one section per SPEC-ID, pre-conditions, steps, expected outcome, screenshots to capture. If missing, run `qa-design` first.
- **Live deployment URL?** Production vs staging vs local build — different URLs may mean different data and different bugs.
- **Auth method?** Storage state, SSO, credentials helper. Capture this once.
- **Cleanup owner?** You are responsible for deleting fixtures you create. Plan cleanup before you create.

### Phase 1 — Pick capture tools per SPEC-ID

Read the QA plan and decide, for each SPEC-ID, **how** evidence will be captured.

#### Default visual tool: whatever the user/project uses

If a project-specific skill (e.g. `<project>-qa`, such as `acme-checkout-qa`) pins a tool, **use that one** — don't second-guess by reaching for a programmatic Playwright wrapper or a custom `.mjs` script. The pinned tool is usually `playwright-cli` (interactive, ad-hoc) because it leaves a reproducible history, doesn't accumulate bespoke harness code, and matches the workflow the user already knows. Honour the pin even if a script-style approach would feel faster.

If no project-specific skill pins anything, ask: "Which capture tool do you usually run for QA on this codebase?" before assuming. Absent any project convention, default to a **reusable CLI over a bespoke one-off script**: a CLI invocation is a command the user can re-run and share, while a throwaway `.ts`/`.mjs` Playwright wrapper is harness code that rots the moment the flow changes. Reach for a custom script only when the CLI genuinely can't express the check (e.g. DB-side assertions, fixture seeding/cleanup, auth bootstrap) — see `playwright-cli`.

#### Decision tree — which tool for which SPEC-ID

For each SPEC-ID, ask in this order; stop at the first match:

1. **Is the assertion about an async side-effect (worker ran, queue drained, row created, status flipped)?** → **DB query** (ad-hoc script under `scripts/qa/`). UI may lie or lag; the row in the DB is ground truth.
2. **Is the assertion about a queue / pipeline / cron timing or failure?** → **Logs** (hosted log/metrics surface, e.g. cloud provider log explorer or platform execution history). Pick the log surface closest to the suspected failure.
3. **Does the check need hover, focus ring, tooltip text, animation, or a multi-step interactive flow that's awkward to script?** → **MCP browser / interactive driver**. Slower but you see what a human sees.
4. **Is it a visual / layout / textual UI check on a page that's straightforward to reach?** → **Project's pinned visual tool** (usually `playwright-cli`). Snap, label, move on.
5. **Combined (UI says X, but DB must say Y to back it up)?** → Both. Snap the UI, then run the DB script. Reference both pieces of evidence in the report.

Don't reach for log-tailing when a DB query answers the question. Don't reach for a screenshot when the assertion is "this row exists" — a screenshot of a table cell is weaker evidence than a direct query result.

#### Anti-patterns to avoid

- Writing a one-off `.mjs` / `.ts` script that wraps Playwright programmatically when the project's pinned tool is `playwright-cli` (or another reusable CLI). The CLI is the source of truth for visual QA and stays reproducible; bespoke scripts duplicate it badly and don't survive the next person picking up the QA run.
- Asserting visual fixes from code review alone ("I read the diff, it must work"). Capture the evidence.
- Using logs to confirm a UI bug. Logs confirm pipelines; the UI confirms UI.

Document the chosen tool per SPEC-ID in the plan as you decide.

### Phase 2 — Execute, capture, log findings

For each SPEC-ID, in order:

1. Establish the pre-condition (seed fixture if needed; tag with a `QA-…` prefix you can match for cleanup).
2. Run the steps (manual or scripted).
3. Capture evidence (screenshot, query result, log excerpt) at the named path.
4. Compare against expected outcome.
5. Update the plan doc: ✅ / ⚠️ / ❌ + one-line observation pointing at the evidence file.

**Honesty rules:**
- If you can't capture a piece of evidence (browser crash, fixture data missing), say so explicitly. Don't write ✅ on a section you only verified in code.
- If a screenshot shows a different state than expected, the spec is NOT verified. Find out why before moving on — that's how the most valuable bugs surface.

### Phase 3 — Bug-hunt during execution (separate output)

Verification is also a discovery surface. As you click through, watch for patterns NOT mentioned in the spec but visibly wrong:

| Pattern | What it looks like | Where to look |
|---|---|---|
| **i18n placeholder unresolved** | UI shows literal `{count}`, `{name}`, `{x}` | Anywhere the locale was just switched or the call site is recent |
| **Hardcoded string in localised UI** | One locale is active but a string is in another language (or vice-versa) | Buttons, badges, tooltips, error messages, empty states |
| **Broken HTML markers** | Rendered HTML shows literal `<!-foo-->` or `<!--foo->` | Sanitizers / strip-field / regex `--`-collapsing |
| **Async pipeline stuck** | Status field stuck at `PENDING_…`, queue with stale messages, worker job never executes | Status fields, queue counts (`active`/`dead`), worker execution history |
| **Opaque tooltip / badge** | Coloured dot, badge, icon with no `title` or with a bare value (`"95%"`) — no indication of what colour means or what to do | Any new dot / badge / icon next to data |
| **Queue/worker mismatch** | App enqueues to `foo-jobs`, scaler/worker reads from `foo`. Both queues exist but no one talks — a queue producer/consumer name mismatch | Message queue config + scaler + worker env vars |
| **Auto-apply gap** | Backend creates the suggestion correctly but never writes the FK column → UI keeps showing the row under "Uncategorized" / "Pending" | UI says "no data" but DB has rows |
| **Master-data / PII leak** | A record, name, or note meant to stay internal ends up in a message or document sent to an external party — records/notifications leaking to unintended recipients | Outbound emails, exported documents, drafts sent to third parties |
| **Tab / section default hides results** | After a fix, the UI defaults to a tab ("Pending") that's now empty → user thinks nothing was processed | Step pages with multiple tabs |

When you find one, log it in a **separate** "Bugs found during QA" section of the report. Each bug gets:
- File / line / route where observed.
- Severity (blocks-merge / important / minor).
- Suggested fix or PR link.

These bugs are **not** failures of the spec coverage — they're extra value the QA produced. Treat as a separate output.

### Phase 4 — Cleanup

Before declaring the QA done:

- Delete every fixture you created (matched by your `QA-…` prefix).
- Delete uploaded files, drafts, emails that were part of the test.
- Verify deletion (a query filtered on `startsWith: "QA-"` should return 0 rows).
- Reset any toggles / settings you flipped to enable a test.

Prefixing every QA fixture with `QA-` (or a per-run variant like `QA-<spec>-<date>-…`) is what makes this cleanup mechanical — cleanup should always be a single bulk delete matched by prefix, never a manual hunt through the data. If a fixture can't be tagged with the prefix (e.g. it's a config toggle, not a row), track it separately and reset it explicitly.

The deployment should look like the QA run never happened — unless the user explicitly asked to keep some fixtures for review.

### Phase 5 — Report

Final output is the QA plan doc with statuses filled in + a bugs section. At the top, a coverage table:

```markdown
| ID | Status | Observation |
|---|---|---|
| FB2-1a | ✅ | trash/bin visible in list + detail view (fb2-1a-01.png) |
| FB2-2  | ⚠️ | dot works but tooltip is opaque (bug 4) |
| ...
```

And underneath, the bugs found:

```markdown
## Bugs found during QA
### Bug 1 — …
- File: `…:N`
- Severity: …
- Fix: PR #… / suggestion
```

The user reads the table first, the bug section second. Both must be honest.

## Conventions

- **Doc location**: `docs/qa-evidence/<YYYY-MM-DD>/<spec-name>-qa-plan.md` (created by `qa-design`, updated by this skill).
- **Screenshots**: `docs/qa-evidence/<YYYY-MM-DD>/screenshots/<spec-id>-<n>-<description>.png`.
- **Scripts**: `scripts/qa/*` — seed, cleanup, navigate, query. Reusable across QA runs; prefer extending an existing script over writing a new one.
- **Fixture prefix**: `QA-<spec>-<timestamp>-…` so cleanup can match by `startsWith`.

## When NOT to use this skill

- Writing automated E2E tests as part of the implementation — that's `test-driven-development` + Playwright spec files.
- Code review of a PR — that's `code-review`.
- Debugging a specific failing test — that's `systematic-debugging`.
- Free-form smoke checks — those don't need this much structure.

## Project-specific layers

This skill is tool- and project-agnostic. A project-specific QA skill (e.g. `<project>-qa`, such as `acme-checkout-qa`) extends this one with:
- Concrete URLs, auth helpers, route map.
- Existing fixture / cleanup scripts and their conventions.
- A list of bug patterns previously found in *that project* — proactive hints for future runs.

If a project-specific QA skill exists, invoke it on top of this one; if not, this skill alone is enough.

## Related skills

- **qa-design** — produces the QA plan doc this skill consumes.
- **spec-driven-development** — produces the spec inventory `qa-design` builds on.
- **playwright-cli** — the default reusable CLI for visual capture when no project-specific tool is pinned.
- **systematic-debugging** — for diving into a specific bug uncovered during QA.
- **finishing-a-development-branch** — for closing the loop once bugs are fixed.
