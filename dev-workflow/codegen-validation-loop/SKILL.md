---
name: codegen-validation-loop
description: Validate AI/agent-generated code (or structured agent output) against a source-of-truth spec, classify failures, decide whether to fix in place or regenerate upstream, and iterate to green with a bounded number of cycles. Also covers benchmarking agent output against a ground-truth document (agent-correct / doc-correct / both-partial / irrelevant). Use whenever a codegen agent, extraction agent, or structuring agent produces output that needs to be checked against tests or against a reference doc before it's trusted.
allowed-tools: Read, Bash, Grep, Glob, Edit, Write
---

# Codegen Validation Loop

A methodology for validating output produced by an AI agent — generated code, or a
structured extraction/analysis — against a source-of-truth spec, and iterating until
it's actually correct instead of just "looks plausible."

It covers two related situations:

1. **Test-fix loop** — a generation agent produced code; run it through checks, classify
   any failures, and decide whether to patch the code directly or regenerate it from an
   improved input/template.
2. **Agent-vs-ground-truth validation** — an extraction or structuring agent produced a
   structured output (a spec, a schema, a plan) that needs to be compared against an
   existing reference document to find and classify discrepancies.

Both share the same discipline: never eyeball a diff and call it done. Run the checks,
classify every discrepancy into one of a small number of buckets, and let the bucket
decide the action.

---

## Part 1 — Test-fix loop (generated code)

### 1. Run the checks, in order, and collect *all* failures before classifying anything

The concrete commands depend on the stack. Typical layers, roughly in the order that
catches problems cheapest-first:

| Layer | Purpose | Example (Node/TypeScript) | Example (Python) | Example (Go) |
|---|---|---|---|---|
| Compile / typecheck | catches structural errors first | `npx tsc --noEmit` | `mypy .` / `python -m py_compile` | `go build ./...` |
| Lint | style + common bug patterns | `npx eslint src/ --ext .ts` | `ruff check .` | `go vet ./...` |
| Unit tests | behavior correctness | `npx jest --coverage` | `pytest --cov` | `go test ./...` |
| Build / package | it actually assembles | `npm run build` | `python -m build` | `go build -o bin/app` |
| Container build (if applicable) | deployability | `docker build -t <name>:test .` | same | same |

TypeScript/npm above is one illustrative stack, not an assumption — swap in whatever the
target project actually uses. The point is the *order* (fail fast on structure before
spending time on behavior) and the discipline of collecting every failure before you
start fixing, so you can spot patterns instead of whack-a-moling one error at a time.

### 2. Classify every failure into exactly one category

| Category | What it looks like | Typical fix | Usually systemic? |
|---|---|---|---|
| **Syntax / compilation error** | Code doesn't compile/parse — bad imports, wrong types, missing modules | Fix directly in the generated code | Rarely — unless the generation agent keeps misusing the same pattern |
| **Logic error** | Code runs but behaves incorrectly — wrong mapping, bad filtering, wrong response shape | Fix directly if isolated; treat as a pattern if it repeats across multiple files | Sometimes — repeated instances mean the input spec or generation prompt needs work |
| **Spec / input error** | The generation agent was given wrong or incomplete input — the upstream transformation into its input format was wrong | Fix the input artifact, then **regenerate** | Yes — fix the mapping/transformation rules that produced the input, not just this one run |
| **Scaffolding error** | The project structure itself is wrong — missing directories, broken test config, wrong base image | Improve the scaffolding template/skill, then regenerate | Almost always — these are template-level, not instance-level |
| **Test-quality error** | The test itself is wrong, not the code under test — bad assertions, mismatched mocks | Fix the test directly | Sometimes — repeated bad test patterns mean the testing template needs work |

### 3. Decide: fix directly vs. regenerate

```
                      ┌─ Syntax error ────────────→ Fix directly
                      ├─ Logic error (isolated) ───→ Fix directly
Failure classified as ├─ Logic error (pattern) ────→ Improve system + regenerate
                      ├─ Spec/input error ─────────→ Fix input + regenerate
                      ├─ Scaffolding error ────────→ Improve templates + regenerate
                      └─ Test-quality error ───────→ Fix test directly
```

**Threshold for regeneration**: 3+ failures of the same systemic type, or one failure
that's structural (affects the whole project, not one file) → improve the system and
regenerate rather than patching failure-by-failure. Patching around a systemic problem
just re-hides it for the next generation run.

**When in doubt**: surface the failure, your classification, and your recommendation to
the user rather than guessing.

### 4. Cycle limits — don't loop forever

- **Max fix cycles per run**: 5. If the code still doesn't pass after 5 rounds of direct
  fixes, stop and reassess the input or the generation approach — don't keep patching.
- **Max regeneration attempts**: 3. If it still fails fundamentally after 3 full
  regenerations (each with a real improvement applied), escalate to manual review.

At each pause point, report:
- current pass/fail status
- number of remaining failures, by category
- recommendation: keep fixing, regenerate, or accept with known issues (and why)

### 5. Generation log format

Track every run in a log next to the generated artifact (e.g.
`docs/<component>/generation-log.md`):

```markdown
# Generation Log: {component-name}

## Run 1 — {date}

### Generation
- Input: {input artifact} (commit/version reference)
- Duration: ~X minutes
- Fix iterations: N

### Test Results
- Compile/typecheck: PASS/FAIL
- Lint: PASS/FAIL (N warnings, M errors)
- Unit tests: X/Y passed, Z% coverage
- Build: PASS/FAIL
- Container build: PASS/FAIL

### Failures

#### Failure 1: {short description}
- **Category**: Syntax / Logic / Spec / Scaffolding / Test Quality
- **Details**: {what went wrong}
- **File(s)**: {affected files}
- **Action taken**: Fix directly / Regenerate / Improve system
- **Resolution**: {what was done}
- **Systemic improvement**: {if applicable, what changed upstream}

### Outcome
- Status: PASSED / NEEDS MORE FIXES / REGENERATED
- Next action: {what happens next}

---

## Run 2 — {date}
...
```

---

## Part 2 — Validating agent output against a ground-truth document

Use this when an extraction agent (analyzes a source and proposes an approach) or a
structuring agent (turns findings into a structured schema/spec) has produced output
that overlaps with an existing reference document, and you need to know which one to
trust before it feeds the generation agent (or any downstream step).

### 1. Define comparison dimensions up front

Before comparing, lay out a table of what each side represents for each dimension —
this keeps the comparison mechanical instead of vibes-based. Example shape:

| Dimension | Source-of-truth doc field | Agent output field | Discrepancy significance |
|---|---|---|---|
| Access/connection method | e.g. "Connection Method" (API / scrape / both) | e.g. `recommended_strategy` enum | HIGH — wrong method means wrong implementation approach |
| Data fields/entities | e.g. free-text "fields to extract" list | e.g. `entities[].attributes[]` | HIGH — missing fields means an incomplete result |
| Endpoints/URLs | e.g. documented URL(s) | e.g. `tested_endpoints[]` | MEDIUM — agents finding *more* endpoints is usually a positive signal |
| Input/search parameters | e.g. prose description of query params | e.g. structured `parameters[]` | HIGH — wrong parameters break the consuming logic |
| Limitations/constraints | e.g. notes on frequency, rate limits, auth | e.g. `limitations`, `cost_structure`, `freshness` | MEDIUM — docs often omit these; an agent surfacing them is valuable |
| Config that only exists on one side | fields with no agent equivalent (or vice versa) | — | N/A for this comparison — flag as out of scope, not a discrepancy |

Adapt the rows to whatever the actual doc and agent schemas are — the table's job is to
force an explicit mapping before you start eyeballing differences.

### 2. Classify every discrepancy into exactly one bucket

| Classification | Meaning | Action |
|---|---|---|
| **Agent correct** | The agent's output is more accurate/complete than the doc | Propose a doc update — don't apply it without approval |
| **Doc correct** | The doc has information the agent failed to capture | Log as an improvement candidate for that agent (which one, what it missed, a hypothesis for why) |
| **Both partial** | Each side has part of the truth, neither is complete | Merge into a combined understanding; note what each side contributed |
| **Irrelevant** | The difference is only formatting/naming/style, not content (e.g. `"Business Name"` vs `business_name`, `"Canada"` vs `CA`) | Ignore — don't report it |

### 3. Verify ambiguous cases before classifying

For anything not obviously in one bucket:

1. Check the live source directly (hit the URL, call the API, inspect the page/UI)
2. Check how comparable/sibling cases handle the same field or method
3. Check any downstream schema/template that consumes this data, to see which value it actually expects
4. Ask the user for domain knowledge that can't be verified technically

Present ambiguous cases with your proposed classification and evidence; let the user
confirm or override rather than deciding silently.

### 4. Comparison report format

```markdown
# Ground Truth Comparison: {component-name}

**Date**: {date}
**Reference**: {ticket/issue number or N/A}
**Source-of-truth doc**: {link(s) to the reference document(s)}
**Agent output**: {artifact(s) being compared, e.g. `extraction-output.json`}

## Summary

| Dimension | Discrepancies | Agent Correct | Doc Correct | Both Partial |
|-----------|---------------|---------------|--------------|---------------|
| Access/connection method | N | ... | ... | ... |
| Data fields | N | ... | ... | ... |
| Endpoints/URLs | N | ... | ... | ... |
| Input/search parameters | N | ... | ... | ... |
| Limitations | N | ... | ... | ... |

**Overall assessment**: {brief narrative}

## Detailed Discrepancies

### 1. {Short description}
- **Dimension**: {which dimension}
- **Doc says**: {value from the reference document}
- **Agent says**: {value from agent output}
- **Classification**: Agent Correct / Doc Correct / Both Partial
- **Justification**: {why this classification}
- **Verification**: {how it was verified — checked live source, tested the API, etc.}
- **Recommended action**: {what to do about it}

### 2. ...

## Action Items

### Agent improvements (from "Doc Correct" items)
- [ ] {which agent, what it missed, suggested fix}

### Documentation updates (from "Agent Correct" items)
- [ ] {proposed update — not executed}

### Merged insights (from "Both Partial" items)
- [ ] {combined understanding to apply going forward}
```

---

## Why both halves belong together

The two halves close a loop, not just share a template. If the generation agent
consistently produces spec-mismatch failures (Part 1, category 3), the fix isn't just
"regenerate" — it's tracing the input back through Part 2's classification to find
whether the *upstream* extraction/structuring agent is systematically missing something
the source-of-truth doc had right. Treat "doc correct" findings from Part 2 as leading
indicators of "spec/input error" failures you'll otherwise only discover after
generation.
