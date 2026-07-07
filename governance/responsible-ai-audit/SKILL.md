---
name: responsible-ai-audit
description: Audit the current repo against your organization's Responsible AI policy (a 16-item checklist, configurable per-org via a profile file), spawn parallel agents in worktrees to close every code-actionable gap, review each PR with the verification protocol (typecheck + tests + baseline diff), merge what passes, update the compliance tracker, and trigger deploy only if the repo already has a deploy convention (or the profile pins one). Stack-agnostic — detects node/laravel/python/go/rust/ruby and parametrises commands. Base branch detected from `git symbolic-ref refs/remotes/origin/HEAD` (override with `--base-branch` or `--use-current-branch`). Use when the user asks to audit a service against a Responsible AI checklist, close policy gaps in bulk across a codebase, or replicate a prior audit run on another repo.
argument-hint: "[--repo=PATH] [--dry-run] [--no-deploy] [--concurrency=N] [--base-branch=BRANCH | --use-current-branch] [--reset-profile]"
---

# Responsible AI audit

End-to-end workflow for auditing a repo against a Responsible-AI policy and closing gaps in bulk. Optimised for repos with a standard git remote and CI; degrades gracefully when extra infra (a sibling deploy repo, a specific CI provider, etc.) isn't present.

This skill is **policy-agnostic**: it doesn't hardcode any organization's policy text, URL, or internal doc IDs. The first time it runs against a machine, it asks the operator where the policy lives and how deploys are triggered, then remembers the answer.

## Arguments

- `--repo=PATH` — Absolute path to the target repo. Defaults to the current working directory. **Every subsequent shell command must be prefixed with `cd <repo_root> && ` or use absolute paths**, because the harness resets cwd between calls.
- `--dry-run` — Read the policy, run detectors, produce `gap-report.md` only. Do not spawn agents, do not write code, do not push, do not deploy.
- `--no-deploy` — Run full remediation and merge to base, but skip the tag/deploy step even if a convention exists.
- `--concurrency=N` — Max parallel agents (default 4).
- `--base-branch=BRANCH` — Override the base branch for merges. Default: the repo's default branch from `git symbolic-ref refs/remotes/origin/HEAD`. Use this when the convention is non-standard.
- `--use-current-branch` — Use the **currently checked-out branch** as the merge base instead of the default branch. Useful for feature-branch workflows where work lands on a long-lived integration branch (e.g. `develop`, `integration`). The skill records this choice and never tries to push to `main`/`master` when this flag is set.
- `--reset-profile` — Re-ask the profile questions (Phase -1) even if a profile file already exists.

## Context (must be gathered at start)

- Repo root: !`git rev-parse --show-toplevel`
- Current branch: !`git rev-parse --abbrev-ref HEAD`
- Remote: !`git remote get-url origin`
- Latest tag: !`git tag --sort=-v:refname | head -1`
- Sibling infra/deploy repo (generic glob, only relevant if the profile's deploy convention needs one): !`ls -d ../*deploy* ../*infra* 2>/dev/null | head -1`
- .env present: !`test -f .env && echo yes || echo no`
- Stack signal files: (detected in Phase 0.5; the skill body checks each known manifest filename one at a time using `test -f`)

## Phase -1 — Profile (first run only, or when `--reset-profile` is passed)

The skill stores per-operator configuration in a single profile file: `~/.claude/responsible-ai-audit.profile.json`.

1. If the file exists and `--reset-profile` was not passed, read it and skip to Phase 0.
2. Otherwise, ask the operator (one concise batch of questions):
   - **Policy source** — "Where does the Responsible AI policy live? Give me a URL (Confluence/Notion/wiki/Google Doc) or an absolute path to a local document." Store as `{{POLICY_URL}}` (or `{{POLICY_PATH}}` if local) plus a short `{{POLICY_NAME}}` (e.g. "Acme Corp — Responsible Use of AI Policy").
   - **Deploy convention** — "After merging compliance fixes, should I trigger a deploy? Options: (a) auto-detect only [default — the skill inspects the repo and infers]; (b) semver tag + CI workflow; (c) a package-manager/Makefile deploy script; (d) a sibling infra-as-code repo (Helm/Kustomize `values.yaml` bumped on tag push, watched by ArgoCD/Flux/etc.); (e) none — I'll deploy manually." If (b)/(c)/(d), ask any convention-specific detail needed (e.g. tag format example, sibling-repo glob, health-check URL template). Store as `deploy_convention` plus the extra fields.
3. Write the profile:

```json
{
  "policy_name": "{{POLICY_NAME}}",
  "policy_source": "{{POLICY_URL_OR_PATH}}",
  "policy_source_kind": "confluence | notion | url | local_path",
  "deploy_convention": "auto | semver-tag | package-script | sibling-infra-repo | none",
  "tag_format_example": "vX.Y.Z",
  "sibling_repo_glob": "../*-deploy*",
  "health_check_url_template": ""
}
```

4. Reuse this file on every subsequent run. Never re-ask unless `--reset-profile` is passed or the file is missing.

## The checklist (canonical)

Read `checklist.json` from the skill directory. It is the source of truth for the 16 items and their owners (service / org-level / parked). `checklist.json`'s `policy_source` block contains `{{POLICY_NAME}}` / `{{POLICY_URL}}` placeholders — substitute them from the profile at runtime. The resolved policy document is the **upstream** source — if its wording diverges from the JSON, surface a warning and proceed with the JSON, **never edit code based on a wording change without operator review**.

The owners break down as:

- **Service-scoped, code-actionable** (skill remediates with agents): 5, 6, 9, 10, 11a, 11b, 16
- **Service-scoped, doc-only** (skill remediates with one agent or writes directly): 3, 12, 14, 15
- **Parked low-priority** (skill records but does not act): 7, 13
- **Org-level** (skill records and notes): 1, 2, 4, 8

## Workflow

### Phase 0 — Preflight (always)

Run **every** check. If any fails, stop and report. **In `--dry-run` mode, all preflight failures degrade to warnings**: the audit proceeds because nothing is written.

1. **Resolve the base branch**:
   - If `--base-branch=BRANCH` was passed, use it.
   - Else if `--use-current-branch` was passed, use `git rev-parse --abbrev-ref HEAD`.
   - Else read the repo default: `git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'`. If empty (rare), fall back to scanning for `main`, then `master`, then `develop` — and warn if none of those exist.
   Record this as `{{BASE_BRANCH}}`.
2. `git status --porcelain` must be empty except for `.claude/`, `docs/*.png`, build artifacts (`dist/`, `vendor/` etc).
3. Current branch must equal `{{BASE_BRANCH}}` **unless** `--use-current-branch` was passed (then the check is a no-op).
4. `git fetch origin && git log --oneline origin/{{BASE_BRANCH}}..HEAD` — must be empty. No unpushed commits.
5. If the profile's `policy_source_kind` is `confluence` (or another Atlassian resource), confirm the relevant MCP tool responds before Phase 1. If it errors, or the policy source is a plain URL/local path, fall back to detectors-only (skip the live drift check) and warn.

### Phase 0.5 — Stack detection (always)

Detect the primary stack and record `{{STACK}}`. Use the first match:

| Signal file | `{{STACK}}` | `{{TEST_COMMAND}}` candidate | `{{TYPECHECK_COMMAND}}` candidate | `{{LINT_COMMAND}}` candidate |
|---|---|---|---|---|
| `package.json` | `node` | `npm run test:ci` → `npm test` → `npm run test` | `npx tsc --noEmit` (only if `tsconfig.json` exists) | `npm run lint` |
| `composer.json` | `laravel` (if `artisan` present) else `php` | `vendor/bin/phpunit` → `php artisan test` → `vendor/bin/codecept run` | `vendor/bin/phpstan analyse` → `vendor/bin/psalm` | `vendor/bin/pint` → `vendor/bin/php-cs-fixer` |
| `pyproject.toml` or `requirements.txt` | `python` | `pytest` → `python -m pytest` | `mypy .` → `pyright` | `ruff check` |
| `go.mod` | `go` | `go test ./...` | `go vet ./...` | `golangci-lint run` |
| `Cargo.toml` | `rust` | `cargo test` | `cargo check` | `cargo clippy` |
| `Gemfile` | `ruby` | `bundle exec rspec` → `bundle exec rake test` | `bundle exec sorbet tc` (if Sorbet) | `bundle exec rubocop` |
| none | `unknown` | manual | manual | manual |

Detect actual commands by reading the manifest file (e.g. `package.json` `scripts`, `composer.json` `scripts`, `Makefile` targets). Prefer the explicit `test:ci` / `test` variant over the canonical runner. Record `<test_command>`, `<typecheck_command>`, `<lint_command>` for Phase 4.

Detect framework-specific paths and record:

| `{{STACK}}` | Source dir | Test dir | Config dir |
|---|---|---|---|
| `node` | `src/` | `src/__tests__/`, `tests/` | `src/config.ts`, `.env` |
| `laravel` | `app/` | `tests/Feature/`, `tests/Unit/` | `config/`, `.env` |
| `python` | `src/`, `<pkg>/`, `app/` | `tests/`, `test/` | `.env`, `config/` |
| `go` | `internal/`, `pkg/`, `cmd/` | `*_test.go` co-located | `config/`, env vars |

Also detect: env file (`.env` / `.env.local` / `.env.example`) and whether it exists. If the stack needs env vars at test time and the file is missing, stop and ask the operator.

5. Detect test/typecheck/lint commands using the table above. Record them.
6. Detect env file. If missing and required, stop.

### Phase 1 — Read policy & detect drift

1. Resolve the policy source from the profile. If it's a Confluence/Notion/Google-Doc URL and the corresponding MCP tool is available, fetch it that way; otherwise `WebFetch` the URL or `Read` the local path.
2. Extract the 16 implementation-checklist items. Compare item titles to `checklist.json[*].title`. Any mismatch → emit a warning row in the report (`policy_drift: true`) but proceed.

### Phase 2 — Audit (run detectors)

Detectors run in **two passes**.

#### Pass 1 — Signal sweep (cheap, mechanical)

For each item, evaluate `detector.signals[]`. A signal can be:

- `{ "kind": "file_exists", "paths": [...] }` — at least one path exists.
- `{ "kind": "grep", "patterns": [...], "paths": [...] }` — at least one pattern matches in at least one path.
- `{ "kind": "manual" }` — skill cannot detect; goes to Pass 2 / operator prompt.
- `{ "kind": "manual_prompt", "question": "..." }` — skill **must ask the operator** during the audit pause; the answer becomes the status.

`detector.require` is `"any"` (default) or `"all"`. The signal set hits when any/all signals match.

#### Pass 2 — Deep inspect (only for items hit by Pass 1 with partial confidence)

When an item is hit in Pass 1 but the signal is weak (e.g. a directory exists but its contents are unclear), upgrade the verdict by **reading the candidate files** with the Read tool and judging whether the control is implemented to the spec in the gap prompt. Output one of: ✅ Done · 🟡 Partial · ❌ Gap. Record the file paths inspected as evidence.

Heuristic for "weak signal":
- A grep hits in `docs/` only and the item requires code → likely 🟡 Partial (doc exists, code missing).
- A grep hits in `app/` / `src/` for a marker but no test exists → likely 🟡 Partial.
- A directory like `app/Services/*AiAssistant*/Audit/` exists with files → **read those files** before declaring ✅ or 🟡.

The aim is to avoid the false-Gap problem: a sophisticated repo already has the control under a non-obvious file name, and a coarse grep misses it.

#### Verdict-precision rules (apply during deep_inspect)

These rules tighten the Done/Partial/Gap boundary for items a coarse signal sweep is known to misjudge. **Apply them before writing the verdict to the Findings table.**

**Organisational convention (load-bearing, but a default — override it in your profile/checklist if your org's policy defines Done/Partial/Gap differently):**

- **Implementation alone counts as 🟡 Partial.** A control with working code, tests, or wired plumbing but no doc that names the item is **Partial, not Gap**.
- **✅ Done requires both implementation AND a doc that names the item** (in the controls doc, tracker, or equivalent).
- **❌ Gap means no evidence on either side** — no code AND no doc.

This is this skill's default convention; revisit only via your own governance channel that owns the policy.

- **Item 5 (Audit logging):**
  - ✅ Done **only** if every audit-event payload literally carries `model_id` (or `model` / `model_name`), `prompt_version`, and `prompt_hash` (or `sha256(prompt)`). Operational metrics (tokens, duration, latency) **do not count**. Also requires an IR runbook + rollback procedure documented.
  - 🟡 Partial when the audit emitter exists and is wired, but one or more of the three identity fields is missing **or** the IR/rollback runbooks are absent.
  - ❌ Gap when no audit emitter is invoked from the AI orchestrator, or the only logging is generic application logs.

- **Item 6a (SBOM + licence allowlist):**
  - ✅ Done **only** if the licence check runs automatically (CI gate, Dockerfile RUN, or a declared release-blocking script). A standalone manual script with no enforcement is 🟡 Partial.

- **Item 10 (Provenance):** ✅ Done requires the four fields (`model_id`, `model_version`, `prompt_version`, `prompt_hash`) **exposed in the API response** AND **persisted in any cache**. If only one of those layers carries them → 🟡 Partial.

- **Item 11a (Cross-tenant test):** Before declaring Gap, the applicability_check must consider **all** common tenant-axis names: `tenant_id`, `tenantId`, `BelongsToTenant`, `TenantScoped`, `group_id`/`groupId` (a common alternate naming), `org_id`/`orgId`, `workspace_id`, `account_id`, `customer_id`. A repo with any of these IS multi-tenant.

- **Item 11b (Cost rate-limit):** ✅ Done requires a middleware/filter applied to AI endpoints. A global concurrency semaphore (`MAX_CONCURRENT_REQUESTS` etc) is **not** cost rate-limiting — that is 🟡 at best.

- **Item 12 (Autonomy level):** Default to `infer_when_miss`. **Always** read the system prompt + agent entry + tool registry before falling back to manual_prompt. Rules of thumb:
  - No tool surface (chat-completions only) → **Advisor (read-only)**.
  - Write tools that require UI confirm flow / `actionConfirmRequired: true` / `[Confirm]` button → **Assistant (human sign-off)**.
  - Write tools that execute without per-action confirmation but inside hard-coded scope limits → **Autonomous (guardrailed)**.

#### Meta-findings (always check, append to report under "Meta-findings")

Independent of the 16 items, surface these signals when they appear — they affect Phase 4 verification and Phase 6 deploy and the operator should see them up-front:

1. **CI runs zero tests on the default branch.** If the CI config (`bitbucket-pipelines.yml` / `.github/workflows/*.yml` / `.gitlab-ci.yml`) only imports a build template with no test step, the Phase 4 baseline cannot rely on CI. Phase 0 baseline must run locally. Add a row to the report.
2. **Test-runner present but no typechecker configured.** Many Python and PHP repos ship without `mypy`/`phpstan`. Phase 4 `{{TYPECHECK_COMMAND}}` degrades to lint-only and warns. Record in the report.
3. **Tag-format vs. profile mismatch.** If the repo's recent `git tag` output disagrees with the `tag_format_example` recorded in the profile (or the sibling infra repo's tag pattern, if that convention applies), surface it. Phase 6 must not silently mismatch — the operator gets to choose the convention.
4. **No env file at all.** If the stack needs env vars at boot and neither `.env` nor `.env.example` exists, Phase 4 verification will fail spuriously and Phase 0 should have stopped (in dry-run, this is a warning).

#### Reporting

Produce `gap-report.md` in repo root:

```markdown
# Responsible AI audit — <date>

| # | Title | Status | Detector hit | Owner | Notes |
|---|---|---|---|---|---|
...
```

Status legend matches `RESPONSIBLE_AI_COMPLIANCE.md`: ✅ Done · 🟡 Partial · ❌ Gap · 🏢 Org · 🅿️ Parked.

**Show the report to the operator and pause.** Ask: "These N gaps will be remediated by parallel agents. Proceed? (yes/no/dry-run)". Do not skip the pause.

If `--dry-run`, stop here.

### Phase 3 — Spawn remediation agents

For each Gap or Partial item marked `code-actionable: true`:

1. Load the prompt template from `prompts/gap-<id>-<slug>.md` and `prompts/preamble.md`.
2. Substitute placeholders: `{{REPO_NAME}}`, `{{REPO_ROOT}}`, `{{TEST_COMMAND}}`, `{{TAG_FORMAT}}`, `{{SIBLING_DEPLOY}}`, `{{POLICY_NAME}}`, `{{POLICY_URL}}`.
3. Spawn an `Agent` with `subagent_type: general-purpose` and `isolation: worktree`. Each agent is `run_in_background: true`. Honor `--concurrency=N` — never spawn more than N at a time. Track via `TaskCreate` / `TaskUpdate`.

If a gap has no prompt file in `prompts/`, treat it as "skill cannot remediate" and add to the operator follow-up list.

### Phase 4 — Review each PR as agents finish

When an agent task notification arrives, run the verification protocol from `review-checklist.md`, parameterised by `{{STACK}}`. Brief version:

```bash
WT=.claude/worktrees/agent-<id>
[ -f .env ] && cp .env "$WT/.env"               # copy env if the stack needs it
cd "$WT"
# Install dependencies per stack:
#   node    → npm ci --no-audit --no-fund
#   laravel → composer install --no-interaction
#   python  → pip install -r requirements.txt   (or `uv sync`, `poetry install`)
#   go      → go mod download
{{TYPECHECK_COMMAND}}                           # MUST be clean (if applicable)
# Run the new test file added by the agent (path varies per stack).
{{TEST_COMMAND}}                                # diff vs base branch baseline
```

Baseline diff:

- Capture `{{BASE_BRANCH}}` baseline once at Phase 0: `<n_failed_suites>/<n_failed_tests>` (or the equivalent counter for the stack's runner).
- For the worktree: same metric.
- **Equal** → merge.
- **Worktree has more failures** → `SendMessage` to the agent with the diagnostic and the failing test names. Do NOT merge.

Merge (when verification passes):

```bash
cd <repo_root>
git merge --no-ff origin/<branch> -m "Merge PR #<n>: gap-<id> ..."
# Resolve compliance-doc conflicts by combining both sub-action blocks.
git push origin {{BASE_BRANCH}}
```

Resolve conflict files by category:

- **`docs/RESPONSIBLE_AI_COMPLIANCE.md`** → union both Done blocks.
- **Lockfile** (`package-lock.json`, `composer.lock`, `poetry.lock`, `Gemfile.lock`, `go.sum`) → prefer the side with the new dependency. If both sides added different deps, run the install command again after the merge to regenerate.

### Phase 5 — Consolidate

After all agents finished (or were dismissed):

1. If `docs/RESPONSIBLE_AI_COMPLIANCE.md` **does not exist**, create it from scratch with the canonical structure: header + service/branch/reviewer + status legend + one section per of the 16 items + summary table + review cadence. The skill knows the structure from the audit it just produced.
2. If it exists, re-run detectors and update it in place:
   - Status table at top
   - Change log entry with today's date and items closed
   - Summary counts
3. If a Responsible-AI controls document exists (`docs/RESPONSIBLE_AI_CONTROLS.md` or the repo's named equivalent), bump its version and append to its changelog. If none exists, create `docs/RESPONSIBLE_AI_CONTROLS.md` with at minimum sections covering: autonomy level, audit logging spec, rollback, IR runbook, partner table, data dictionary, lineage, threat model, and continuous-learning governance. Copy structure from any prior successful run you've recorded (see "Prior runs" below), or draft a fresh canonical structure if this is the first repo audited.
4. Commit + push `{{BASE_BRANCH}}`.

### Phase 6 — Deploy (conditional)

Skip entirely if `--no-deploy`, or if the profile's `deploy_convention` is `none`.

See `deploy-conventions.md` for the full detection/procedure table. Summary: the skill never invents a deploy strategy — it follows the profile's `deploy_convention` if pinned, or auto-detects (in order: semver tag + CI workflow → package-manager deploy script → sibling infra-as-code repo → none).

**Tag-convention disambiguation (always run before tagging):** compare the repo's recent `git tag` output against the profile's `tag_format_example` (and, if the sibling-infra-repo convention applies, against that repo's tag pattern). If they disagree, **stop and ask the operator** which convention applies. Do not invent a tag scheme.

### Phase 7 — Final report

Print to operator:

- Items closed this run (with PR numbers).
- Items still ❌ / 🟡 with reason.
- Deploy status (tag, build status, expected propagation window).
- Tracker delta: e.g. "Done 5→10".

## Failure modes the operator should know

- **Worktree missing `.env`**: handled in Phase 4 by always copying. If `.env` doesn't exist in the repo root, Phase 0 already stopped.
- **Lockfile bloat from new devDeps**: expected. We trust the stack's install-lock determinism.
- **CI pipeline YAML errors**: mixing custom steps with imported pipeline templates (common in Bitbucket Pipelines, but also possible elsewhere) can silently produce zero-duration failures. The skill's prompts explicitly forbid that pattern — read `prompts/gap-6-sbom.md` for the safe alternatives.
- **Cross-tenant test finds a real bug**: agent does NOT silent-fix; it documents in PR body. Skill schedules a follow-up agent to fix and re-runs review.

## Idempotency

The skill is safe to re-run. Detectors that find a gap already closed return ✅ and the corresponding agent is not spawned. Re-running on a fully-compliant repo only re-validates the tracker.

## Prior runs

Keep your own running log of repos this has been run against — it helps future runs short-circuit detection and gives you a "known-good" controls-doc structure to copy from. Suggested columns:

| Repo | Stack | Base branch | Deploy convention | First audit | Notes |
|---|---|---|---|---|---|
| Service A | node (TS) | `main` | semver tag + CI workflow | — | Full remediation end-to-end. |
| Service B | laravel (+ node FE) | `develop` | none (manual) | — | Strong pre-existing AI controls; detectors needed `deep_inspect`. |

Add a row here every time you onboard a new repo so future runs can short-circuit detection.
