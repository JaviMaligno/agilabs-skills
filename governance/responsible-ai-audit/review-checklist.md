# Review checklist (Phase 4)

Run this protocol for **every** agent that returns a PR. Parameterised by `{{STACK}}` detected in Phase 0.5.

## Inputs

- `<branch>`: the agent's branch name (e.g. `gap-10-response-provenance`)
- `<worktree>`: `.claude/worktrees/agent-<id>`
- `<test_command>`, `<typecheck_command>`, `<install_command>`: from Phase 0.5
- `<baseline>`: `<n_failed_suites>/<n_failed_tests>` (or stack-equivalent counters) captured at Phase 0 on `main`

Install command per stack:

| `{{STACK}}` | install |
|---|---|
| node | `npm ci --no-audit --no-fund` |
| laravel | `composer install --no-interaction --prefer-dist` |
| python | `pip install -r requirements.txt` (or `uv sync` / `poetry install` if those manifests exist) |
| go | `go mod download` |
| rust | `cargo fetch` |
| ruby | `bundle install` |

## Step 1 — Setup the worktree

```bash
# Copy env file if the repo has one and the stack needs it (most do).
[ -f <repo_root>/.env ] && cp <repo_root>/.env <worktree>/.env
cd <worktree>
<install_command>
```

`.env` is essential whenever the stack initialises services at import/boot time. Missing `.env` was the cause of the false "regression" in our first audit run; the agent saw spurious test failures that disappeared once `.env` was present.

## Step 2 — Typecheck / static analysis

```bash
<typecheck_command>
```

Must complete with no introduced errors. If it does, message the agent.

## Step 3 — New test passes in isolation

Identify the new test file(s) from the agent's PR body. Run them in isolation using the stack's runner:

| `{{STACK}}` | command |
|---|---|
| node | `npx jest <path>` |
| laravel | `vendor/bin/phpunit <path>` |
| python | `pytest <path>` |
| go | `go test <package>` |

Must pass. If not, message the agent.

## Step 4 — Full regression

```bash
<test_command>
```

Compare to the recorded baseline counter.

- **Equal failures** → proceed.
- **More failures**:
  1. Identify the new failing tests. Re-run them in main worktree vs agent worktree to confirm causation.
  2. Correlated with the agent's diff → message the agent with the diagnostic.
  3. Correlated with `.env` or install differences → fix the env issue and re-run.
  4. Otherwise → request agent to debug.

## Step 5 — Inspect the diff

```bash
git diff main..HEAD --stat
```

- Diff matches the prompt scope? Out-of-scope edits → message the agent.
- Lockfile change proportional to new deps? (Lockfile bloat from new deps is fine; 100% reshuffle is a red flag.)
- Any `.env`, secrets, or credentials committed? Hard stop if yes.

## Step 6 — Merge

```bash
cd <repo_root>
git fetch origin
git merge --no-ff origin/<branch> -m "Merge PR #<n>: gap-<id> <short title>"
```

### Conflict resolution

- **`docs/RESPONSIBLE_AI_COMPLIANCE.md`** — almost guaranteed to conflict. Resolve by **union**: both Done sub-items remain.
- **Lockfile** (`package-lock.json`, `composer.lock`, `poetry.lock`, `Gemfile.lock`, `go.sum`) — keep both new deps. Prefer the newer version if both touched the same dep. After merging, re-run install to regenerate.
- **Source files** — usually patches in different lines; standard 3-way merge. If real conflict, escalate.

After resolving, verify before pushing:

```bash
<typecheck_command>
<test_command>
git push origin main
```

## Step 7 — Mark the agent's task complete

`TaskUpdate(taskId=<gap-task-id>, status=completed)`.

If you had to message the agent and it fixed the PR, repeat from Step 1 with the new commit.
