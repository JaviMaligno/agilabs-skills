---
name: spec-driven-development
description: Use when work starts from a reference document that the deliverable must comply with — client feedback Word docs, PRDs, requirements specs, design briefs, regulatory requirements, ticket acceptance criteria, QA walkthroughs / acceptance-test documents, or any external document whose points must be satisfied. Covers the full loop: extract spec points with stable IDs, gate plans and tests against those IDs, flag gaps that need client/stakeholder input, and produce a point-by-point manual-review document (especially for UI work) before declaring done. Invoke proactively whenever the user mentions words like "spec", "PRD", "feedback del cliente", "requirements", "QA walkthrough", "casos de QA del cliente", "este documento/Word", "lo que pide el cliente", "cumplir con X doc", or references a file that contains the acceptance criteria or test cases for the task — even if they don't explicitly say "spec-driven". Also use whenever verifying completed work against a previously supplied reference document.
---

# Spec-Driven Development

## When this skill applies

The deliverable is bounded by a document that someone else wrote: a client Word with feedback points, a PRD, a requirements spec, regulatory constraints, an engineering brief, ticket acceptance criteria, a design doc. The user expects the work to satisfy *that document*, not a more elaborate interpretation of it.

Examples of triggering contexts:
- "Nos ha llegado este Word de Acme Corp con feedback, vamos a resolverlo."
- "Implementa lo que pide el PRD."
- "Verifica que lo que hemos hecho cumple con los puntos del documento."
- The user drops a path or describes a reference document as the source of truth.
- Re-entering a project where a previous spec doc was established — revisit it before planning new work.

If the user is doing free-form exploration or there is no anchoring document, this skill is not the right fit — use `superpowers:brainstorming` directly instead.

## Core principle

**The spec document is the contract.** Every plan step, every test, every implementation change, and every verification gate must be traceable to a numbered point from the spec. Two things follow:

1. **Traceability** — give every spec point a stable ID (e.g. `SPEC-1`, `SPEC-2`). That ID threads through the plan, test names, commit messages, and the final review doc. This is what lets the user see at a glance that each point was addressed.
2. **No scope creep** — if something isn't in the spec, it doesn't get built under this task. Ideas worth pursuing go to a `deferred.md` for later, not silently into the PR.

Both are load-bearing. Weak traceability turns the review doc into fiction; scope creep forces the client to review changes they never asked for.

## Workflow (6 phases)

This skill orchestrates the existing superpowers. It adds a spec-traceability layer on top, not a replacement workflow. Invoke the named superpowers at the indicated phases — don't reinvent their content.

### Phase 1 — Ingest & inventory the spec

1. Locate the spec document. The user will usually give a path or describe it ("el Word de feedback del cliente que mandé ayer"). If the reference is ambiguous, ask for the exact path before proceeding — guessing risks working off the wrong version.
2. Read the document in full. For `.docx` files, use a conversion tool (e.g. `pandoc <file.docx> -o <file.md>`) or let the user export it; do not skim a summary.
3. Build `docs/spec-review/<feature>-inventory.md` with one row per atomic requirement. Each row has:
   - **ID** — `SPEC-1`, `SPEC-2`, ... (stable, don't renumber later)
   - **Verbatim quote** — the exact text from the document (short quote or reference if long)
   - **Interpretation** — your one-sentence rephrasing of what this requires
   - **Surface** — `UI` / `backend` / `infra` / `docs` / `process` (drives review doc depth later)
   - **Status** — `pending` / `gap-blocked` / `out-of-scope` / `resolved`
   - **Source** — document name and heading/page where the point lives

See `references/spec-inventory-template.md` for the exact template.

4. Share the inventory with the user before moving on. This is the alignment checkpoint — if your interpretation of a point is off, catching it here saves a full planning pass.

### Phase 2 — Gap & external-input check

Go through the inventory and flag every point where the information is insufficient to plan or implement. Typical gaps:
- Ambiguous acceptance criteria ("debe ser rápido" — rápido how?)
- Missing data that only the client has (example files, credentials, business rules, ID mappings)
- Conflicts between two points in the same document
- Dependencies on external systems whose behavior isn't documented

Present the gap list to the user as a set of concrete questions. When the user confirms that a question needs the client (or any external party) to answer, annotate the inventory row with `gap-blocked` and add a `Pending external input:` line with who owns the answer and what's needed.

**Do not proceed past this phase for any `gap-blocked` point.** Work around it — plan the other points — but mark the gap-blocked ones as deferred. This is non-negotiable: implementing on an assumption that contradicts the eventual client answer is rework with a side of trust damage.

See `references/gap-log-template.md` for how to format the gap log and the "pending external input" annotations.

### Phase 3 — Plan

Invoke `superpowers:writing-plans`. The plan this skill produces differs from a standard plan in three ways:

1. **Every plan step cites the spec IDs it addresses** — e.g. `Step 3: implement pricing rule engine (SPEC-2, SPEC-5)`.
2. **The plan has a mandatory "Out of scope" section** that lists anything the user or you considered but that isn't in the spec, with a one-line reason. This section exists on every plan, even if empty.
3. **Coverage gate before the plan is finalized** — walk the inventory and verify that each non-`gap-blocked`, non-`out-of-scope` SPEC-N has at least one plan step. Missing coverage means the plan is incomplete.

One plan per checkpoint is preferred over a single giant plan covering the whole spec. The user's global guidance is explicit about this: small plans with checkpoints between them. Split along natural boundaries (e.g. "backend rules first, UI next").

### Phase 4 — Implement

Invoke `superpowers:test-driven-development`. The spec-traceability additions:

1. **Test names reference spec IDs** — e.g. `describe('SPEC-2: pricing rule applies when customer is platinum')`. This is how the test suite itself becomes a compliance artifact.
2. **Commit messages reference spec IDs** — e.g. `feat(pricing): implement platinum discount rule (SPEC-2)`.
3. **Anti-scope-creep gate at every edit** — before adding a feature, a helper, a config option, or a refactor, ask: *which SPEC-N does this serve?* If the answer is "none, but it would be cleaner", it goes in `deferred.md`, not into this PR.

For non-trivial UI work or changes across independent surfaces, consider `superpowers:dispatching-parallel-agents` or `superpowers:subagent-driven-development` for parallel execution — but each subagent gets the inventory IDs it owns and is told explicitly not to touch anything outside them.

See `references/anti-scope-creep.md` for the decision checklist when the "but while I'm here..." urge strikes.

### Phase 5 — Verify against the spec (the re-read)

Before claiming the work is done, re-read the original spec document. Not the inventory, not your notes — the original. This catches drift that accumulated during implementation: interpretations that softened, points that got collapsed, gaps that got silently assumed.

Invoke `superpowers:verification-before-completion`. On top of its standard checks:

1. For each `pending` SPEC-N, gather the evidence that proves it's satisfied: test names, PR file paths, screenshots (UI), log outputs, manual steps. If you can't produce evidence, the point isn't done — mark it and flag it.
2. For UI points, actually drive the UI (browser or the user's testing setup). Type-checking does not verify UI. **Capturing a screenshot is mandatory evidence for every UI-surface point** — the screenshot is to a UI point what a passing test is to a backend point. Drive the UI against the real deployment (not just local), capture the screenshot(s), and save them under `docs/qa-evidence/<YYYY-MM-DD>/screenshots/` named by SPEC-ID (e.g. `spec-2a.png`). When the point depends on role or state, capture the relevant contrast (e.g. the two roles, or before/after). If the skill is running headless and can't open a browser, say so explicitly in the review doc rather than faking it or claiming success.
3. Update the inventory: status moves from `pending` → `resolved` only when evidence exists.

### Phase 6 — Produce the manual-review document

Write `docs/spec-review/<feature>.md`. This is the artifact the user (and possibly the client) will read to sign off. It has two layers, both required:

**Summary table** — one row per SPEC-N:
| ID | Description | Surface | Action taken | Expected outcome | Evidence | Status |

**Per-point detail section** — for each row, an expandable section with:
- Verbatim quote from the spec
- Your interpretation
- What was changed (files, functions, migrations — links, not prose dumps)
- Tests that cover it (names or paths)
- For `UI` points: the captured screenshot path(s) under `docs/qa-evidence/<date>/screenshots/` as the evidence the point is met — not just "steps to run later". The screenshot proves the point the way tests prove a backend point. Include the manual verification steps too, but the captured evidence is what closes the point.
- For `backend`/`infra` points: a short "how to verify" that references logs, curl commands, or test runs
- Any caveats, deferred follow-ups, or external inputs still pending

The review doc must contain (or link) a visual-evidence index mapping each UI SPEC-ID to its capture(s) — see `docs/qa-evidence/<date>/visual-qa.md` below.

The depth split matters: backend points are usually verifiable by tests and CI, so their detail section can be tight. UI points need step-by-step because the user has to look at the screen — a green test suite doesn't prove the button is in the right place.

See `references/spec-review-template.md` for the exact template with examples.

At the end of the review doc, include a `Deferred / out of scope` section listing everything that surfaced during implementation but was deliberately not included. This makes the anti-scope-creep discipline visible — the user sees what you *didn't* do and why.

## Integration with existing superpowers

This skill doesn't replace the superpowers loop; it layers spec-traceability on top.

| Phase | Invoke |
|---|---|
| 1 — Ingest | (just read + inventory, no superpower needed) |
| 2 — Gap check | (user conversation, no superpower needed) |
| 3 — Plan | `superpowers:brainstorming` (if design decisions are open) → `superpowers:writing-plans` |
| 4 — Implement | `superpowers:test-driven-development`, optionally `superpowers:dispatching-parallel-agents` or `superpowers:subagent-driven-development` |
| 5 — Verify | `superpowers:verification-before-completion` |
| 6 — Handoff | (produce the review doc, no superpower needed) |

If the user has given explicit feedback overriding one of those workflows (e.g. "skip TDD for this one"), honor the user's instruction — this skill is a scaffold, not a religion.

## Directory layout conventions

Default paths (adjust if the project has a different convention):

```
docs/spec-review/
├── <feature>-inventory.md   # Phase 1 output (living doc, updated through the run)
├── <feature>-gaps.md        # Phase 2 output (questions + pending external inputs)
├── <feature>-deferred.md    # Running list of things kicked to later
└── <feature>.md             # Phase 6 output — the final manual-review doc

docs/qa-evidence/<YYYY-MM-DD>/
├── screenshots/             # Phase 5 captures, named by SPEC-ID (spec-2a.png, ...)
└── visual-qa.md             # index mapping each capture → the SPEC-ID it proves
```

For monorepos (like Acme's), put the docs inside the specific package/app that owns the feature when possible. If the work spans packages, `docs/spec-review/` at the repo root is fine.

## Red flags that should stop you

- You're about to start implementation and the inventory hasn't been shared with the user → stop, share it first.
- A plan step doesn't cite any SPEC-N → either the step is scope creep or the inventory is missing a point.
- You're tempted to soften a requirement because it's hard ("well, *mostly* deterministic...") → that's a gap; ask the client, don't paper over it.
- The review doc is missing the "Deferred / out of scope" section → the anti-scope-creep loop hasn't been closed.
- A UI SPEC-N is marked `resolved` with no screenshot under `docs/qa-evidence/<date>/screenshots/` → the visual evidence is missing; the point isn't proven.
- Implementation happened before the plan coverage gate ran → the plan wasn't actually finalized.

## Reference files

- `references/spec-inventory-template.md` — Phase 1 inventory format with examples
- `references/gap-log-template.md` — Phase 2 gap list and external-input annotations
- `references/spec-review-template.md` — Phase 6 final review doc template
- `references/anti-scope-creep.md` — Decision checklist for "should I build this too?"
