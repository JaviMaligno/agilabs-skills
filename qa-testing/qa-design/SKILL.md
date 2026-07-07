---
name: qa-design
description: Use to design a QA plan document — translate a spec inventory or reference doc (client feedback document, PRD, requirements, acceptance criteria) into a structured, executable verification document with per-SPEC-ID sections, pre-conditions, step-by-step instructions, expected functional results, UX checks, and named screenshots to capture. The output is a plan that a human or `qa-execution` can follow against a live deployment. Invoke when the user says "design the QA plan", "prepare the document for QA", "turn this feedback into verification steps", "what do we need to check in production for this", or when a `spec-driven-development` inventory exists and we need the next layer before running QA. Tool-agnostic — the plan describes what to verify and what evidence to capture, not which tool captures it.
---

# QA Design (from spec → executable plan)

## When this skill applies

You have a source of truth (a spec inventory from `spec-driven-development`, a client feedback document, a PRD, a list of acceptance criteria) and need to translate it into a **verification plan** — the document a tester (human or `qa-execution`) follows to walk through the deployment and confirm each point is delivered.

Trigger examples:
- "Turn this feedback into a QA plan I can follow."
- "Design the QA doc with steps and screenshots per point."
- "What would we need to check in prod to close this out?"
- "Prepare the document so we can run manual QA tomorrow."

If the spec hasn't been ingested into an inventory yet, run `spec-driven-development` first.

## What this skill produces (and what it does NOT)

**Produces** — a markdown plan at `docs/qa-evidence/<YYYY-MM-DD>/<feature>-qa-plan.md` with:
- Per-SPEC-ID sections (one per point).
- Pre-conditions, steps, expected functional outcome, UX observation checks, named screenshots.
- A coverage table at the end ready for `qa-execution` to fill in statuses.

**Does NOT**:
- Execute anything. No screenshots are captured here. The plan is the artifact.
- Re-extract the spec verbatim — that's `spec-driven-development`'s job. This skill consumes the inventory.
- Decide which tool runs the QA (playwright-cli, MCP browser, manual). That's `qa-execution`'s call when it runs.

## Core principles

1. **Each section is independently reproducible.** A tester walking in cold should be able to do that section without asking questions. If a step says "navigate to the project", the section names which project — or the pre-condition explains how to find one.
2. **Functional vs UX checks are separate.** "The button saves" is functional. "The button is visible without scrolling" is UX. Both belong in the plan but in their own sub-section, because they fail differently and report differently.
3. **Screenshots are named and purposeful.** Each named screenshot answers a specific question. Random fullPage captures with vague names age badly. Convention: `<spec-id>-<n>-<description>.png`.
4. **Cross-cutting conventions go at the top, not in every section.** Language, design system, error message tone, legends/tooltips — declare them once in a "Conventions" header. A tester then applies them everywhere without re-reading.

## Workflow

### Phase 0 — Inputs

You need:
- A spec inventory (file like `docs/spec-review/<feature>-inventory.md` from `spec-driven-development`) **or** the original reference doc + a clear mapping you can do in your head.
- The target deployment URL.
- The list of user roles needed (admin, buyer, etc.) — sometimes a SPEC-ID is only visible/valid for one role.

If any of these is missing, ask the user before drafting. A QA plan against the wrong URL or missing a role is worse than no plan.

### Phase 1 — Decide the doc skeleton

Create `docs/qa-evidence/<YYYY-MM-DD>/<feature>-qa-plan.md` with this top matter:

```markdown
# QA Plan — <feature> (<spec doc reference>)

**Date:** <YYYY-MM-DD>
**Source spec:** <path to inventory / feedback doc / PRD>
**Target deployment:** <URL>
**Test account(s):** <role + email + login method>
**Screenshots root:** docs/qa-evidence/<YYYY-MM-DD>/screenshots/

**Notation**:
- ✅ passes functional + UX OK
- ⚠️ passes functional, UX observation
- ❌ fails
- 🔄 pending execution
```

Then a **Cross-cutting conventions** section. These are checks that apply to every SPEC and would clutter the per-section if repeated. Examples:

```markdown
## Cross-cutting conventions (apply to every section)
1. Labels/columns don't get truncated or overlap — check for horizontal overflow.
2. Consistent default language (e.g. EN). If the client tests in another locale, repeat the checks.
3. Loading states don't hang or flicker.
4. Error messages are understandable (not raw codes like `REVISION_HAS_SENT_RFQ`).
5. Disabled buttons have a tooltip or visible hint explaining why.
6. Destructive confirmations (delete, send) use a dialog with unambiguous text.
7. Any new dot/badge/icon: has an explanatory tooltip, not just a raw value.
```

Use whatever conventions matter for the project. The list above is a starting point.

### Phase 2 — Draft a section per SPEC-ID

For each row in the inventory, write a section using this template:

```markdown
## <SPEC-ID> — <One-line title>

**Client verbatim / spec**:
> <Exact quote from the source. Keep the language of the original.>

**Delivered**: <PR / commit / feature flag — pointer to what shipped>.

**Pre-conditions**:
- <What state the data must be in. Be concrete: "Project with ≥ 2 revisions, no SENT email drafts.">
- <Which role the tester logs in as.>

**Steps** (instructions for a human):
1. <Action> → <observable consequence>.
2. **[screenshot 1]** <what's in the frame and why>.
3. ...

**Expected result (functional)**:
- <Bullet per functional outcome. One bullet = one assertion that can fail.>

**UX checks**:
- <Bullets that the tester observes in the screenshot — visibility, spacing, tooltip text, color distinguishability.>

**Screenshots to capture**:
- `<spec-id>-01-<description>.png`
- `<spec-id>-02-<description>.png`

**Status**: 🔄
```

Guidance for filling each part:

- **Verbatim**: don't paraphrase. The whole point of stable IDs is that the reader can trace back. Keep the original language of the source quote.
- **Delivered**: name the artifact that delivered this point. Helps later when triaging a failure: was the PR even merged?
- **Pre-conditions**: should answer "what data state does this need?" — not the trivial state (you can assume Project exists), but the specific shape (you need ≥ 2 revisions, no SENT drafts, country populated). If creating fixtures is unavoidable, name the cleanup tag (e.g. `QA-FB2-*`).
- **Steps**: write them as a human would speak them, not as Playwright code. The tester is going to read these out loud. Each step ends with the consequence you'd see. Number screenshots in line, not at the end.
- **Expected result (functional)**: one bullet per assertion. "The line is saved" → that's one. "The page redirects" → that's another. Splitting helps `qa-execution` mark partial failures.
- **UX checks**: this is where the QA earns its keep over an E2E test. Spacing, color, tooltip explicitness, error message tone. **Crucial heuristic**: if you added something colour-coded, force a check that the user knows what the colour means.
- **Screenshots to capture**: name them. Each name is a hypothesis ("the popup edits all fields", "the bulk-delete dialog says 'X revisions'"). Vague names produce useless evidence.

### Phase 3 — Add a "Cross-cutting smoke test" section if cross-cutting risks exist

Some checks aren't per-SPEC — they're invariants the whole feature should preserve. For example, "the customer name never leaks into a supplier-facing email body". Add a final section to the plan:

```markdown
## Cross-cutting smoke test — <invariant>

**Why**: <one-line rationale + spec reference if any>

**Steps**:
1. ...
2. ...

**Expected result**: <invariant>

**Screenshots**:
- `smoke-XX-<description>.png`
```

These are the checks that catch regressions when one of the per-SPEC fixes drifts.

### Phase 4 — Coverage table placeholder

At the very end of the doc, drop a coverage table for `qa-execution` to fill:

```markdown
## Final summary placeholder (to fill in after execution)

| ID | Status | Observation |
|----|--------|-------------|
| SPEC-1 | 🔄 |  |
| SPEC-2 | 🔄 |  |
| ...
```

This is what the user reads first when reviewing the QA. Leaving it pre-populated makes execution boring (a good thing).

### Phase 5 — Self-review before handing off

Before declaring the plan complete:

- Does **every** SPEC-ID in the inventory have a section?
- Could a tester who's never seen the project execute each section without DM'ing you?
- Did you mention specific named screenshots, or did you just say "screenshot of the page"?
- Are the conventions at the top covering things you didn't repeat per section?
- For UI points, did you write at least one UX check (not just functional)? If not, ask yourself "what would a designer notice that I'm missing?"
- Are there pre-conditions that require data not in prod? If yes, name the fixture pattern + cleanup tag.

If any answer is no, fix it now — once `qa-execution` runs, gaps in the plan turn into gaps in the report.

## Heuristics for designing good UX checks

When the spec says "show a green/yellow dot" or "add a button", the QA design must answer: **how would someone who didn't read the spec know what this means?** Examples:

- New coloured indicator (dot, badge, icon) → require check: tooltip explains color + action ("Click to change", "Review and confirm").
- New action button → require check: disabled state has tooltip/affordance explaining why.
- New auto-applied field → require check: user can see something was auto-applied AND has a way to override.
- New table column → require check: header is readable in the smallest supported viewport and aligned correctly for the data type (numeric right-aligned, etc.).
- New error path → require check: error message uses words the user would understand, not internal codes.

These belong in the section's "UX checks" list. Without them the QA confirms the feature exists but misses whether anyone outside the team can use it.

## Conventions

- **Doc path**: `docs/qa-evidence/<YYYY-MM-DD>/<feature>-qa-plan.md`.
- **Screenshots dir**: `docs/qa-evidence/<YYYY-MM-DD>/screenshots/`.
- **Naming**: `<spec-id>-<n>-<short-kebab-description>.png`.
- **Status emojis**: ✅ ⚠️ ❌ 🔄 (don't invent new ones).

## When NOT to use this skill

- A test plan for engineers running automated tests — that's `test-driven-development` + Playwright/Vitest spec files.
- A code review checklist — that's `code-review`.
- An ad-hoc smoke test for a single bug fix — overkill; just run the steps.

## Related skills

- **spec-driven-development** — produces the inventory this skill consumes (Phase 1 specifically).
- **qa-execution** — runs the plan this skill produces.
- **playwright-cli** — one of the tools `qa-execution` may use to walk through the plan and capture the named screenshots.
- **writing-skills** — meta, if you're designing a project-specific QA skill on top.
