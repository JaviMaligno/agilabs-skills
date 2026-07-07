## Context (common to every gap-* prompt)

You work on **{{REPO_NAME}}** (root: `{{REPO_ROOT}}`). You are one of several parallel agents closing a specific item of your organization's Responsible Use of AI policy (**{{POLICY_NAME}}**, resolved from `{{POLICY_URL}}` — see the operator's profile). The compliance tracker is at `docs/RESPONSIBLE_AI_COMPLIANCE.md`. The Responsible AI controls document is at `docs/RESPONSIBLE_AI_CONTROLS.md` (or the repo's named equivalent — check the tracker for the link).

Your scope is the **single gap** described in the gap-specific section below. **Do not** address other gaps — other agents own them. Do **not** broaden the scope.

## Stack

This repo's stack is **`{{STACK}}`**. Use the stack-specific section of the gap prompt; ignore sections labelled for other stacks.

| Variable | Value |
|---|---|
| `{{STACK}}` | one of `node`, `laravel`, `python`, `go`, `rust`, `ruby`, `unknown` |
| `{{TEST_COMMAND}}` | e.g. `npm run test:ci`, `vendor/bin/phpunit`, `pytest`, `go test ./...` |
| `{{TYPECHECK_COMMAND}}` | e.g. `npx tsc --noEmit`, `vendor/bin/phpstan analyse`, `mypy .`, `go vet ./...` |
| `{{SOURCE_DIR}}` | typical source path — `src/`, `app/`, `internal/`, etc. |
| `{{TEST_DIR}}` | typical test path — `src/__tests__/`, `tests/Feature/`, `tests/`, etc. |

Discover the exact testing convention for this repo before writing tests: read existing test files in `{{TEST_DIR}}` and mirror their style (test framework, file naming, mocking pattern). Do not impose a foreign convention.

## Environment

- Branch base: the repo's base branch (HEAD before any parallel work).
- Tag convention used by this repo: `{{TAG_FORMAT}}` (informational — do not tag yourself).
- Sibling deploy/infra repo: `{{SIBLING_DEPLOY}}` (informational — do not touch it).
- The worktree you are operating in is isolated; the base branch is untouched.

## Verification protocol (mandatory before opening the PR)

1. `{{TYPECHECK_COMMAND}}` — must complete clean (no static-analysis errors introduced).
2. Run the new test(s) you added in isolation. They must pass.
3. `{{TEST_COMMAND}}` — record `<n_failed_suites>/<n_failed_tests>`. The baseline is provided to you at invocation time. **Your worktree must not introduce new failures** vs the baseline. If it does, your PR is not ready.
4. If your work touches dependencies, run any licence/SBOM scripts the repo has; all must exit 0.

## Worktree hygiene

- If the stack needs an env file (`.env`) and the worktree lacks one, copy it from the main repo root: `cp ../../../.env .env`. The worktree path is `<repo>/.claude/worktrees/agent-<id>` — adjust relative path accordingly.
- Lockfile changes from added dependencies are expected. Do not minimise them manually.

## PR rules

- Branch name: `gap-<id>-<slug>` matching the prompt file name.
- PR title: `gap-<id>: <short title from the prompt>`.
- PR body must include: summary, files touched, verification output (the three commands above), and any **regression you find but do not fix**. Do not silent-fix bugs outside your scope — document them in the PR body and emit a `TODO` comment in the code where appropriate.
- Co-author trailer: use whatever `Co-Authored-By:` convention your own Claude Code setup already applies to commits (e.g. `Co-Authored-By: Claude <model> <noreply@anthropic.com>`).

## Don'ts

- Do not merge your own PR.
- Do not push to the base branch.
- Do not introduce a different stack/language to solve the gap. Stay in `{{STACK}}`.
- Do not modify CI YAML in ways that mix incompatible syntax (e.g. mixing custom steps with imported templates in Bitbucket Pipelines produces zero-duration failures — verified in prior runs).
- Do not add comments that describe WHAT the code does. Only WHY when non-obvious.
- Do not generate documentation files beyond what the gap explicitly requires.

## When you finish

Return a summary ≤ 200 words with: tool/approach chosen, files touched, regression findings (if any), PR URL.
