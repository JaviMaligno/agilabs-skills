---
name: release-tag
description: Cut a release for the current repo — pre-flight git checks, compute the next semver tag from the last tag, push code, create and push the tag, and report the released version. Use after committing changes that are ready to ship, when the user asks to "tag a release", "cut a release", or "bump the version".
argument-hint: "[patch|minor|major]"
---

# Release Tag

Cut a release for the current repository: verify the working tree is clean, compute
the next semver tag from the last one, push code and tag, and report what was
released. This is the GitOps release step, deliberately scoped to one repo and
one job — it does not know anything about how (or whether) your infrastructure
picks the new tag up.

An optional, profile-driven **post-tag hook** can call out to your own deploy
tooling after the tag is pushed. If you don't configure one, the skill simply
tags, pushes, and reports — that's a complete and useful run on its own.

## Arguments

- `$ARGUMENTS` sets the semver bump type: `patch`, `minor`, or `major`. Defaults
  to `minor` if not specified.

## Context

- Current branch: !`git rev-parse --abbrev-ref HEAD`
- Latest tag: !`git tag --sort=-v:refname | head -1`
- Unpushed commits: !`git log --oneline @{u}..HEAD 2>/dev/null || echo "(no upstream or not pushed)"`
- Uncommitted changes: !`git status --porcelain`
- Repo root name: !`basename "$(git rev-parse --show-toplevel)"`

## Steps

### 1. Pre-flight checks

- **STOP if there are uncommitted changes.** Tell the user to commit or stash first.
- **STOP if not on the repo's main/default branch** (`main`, `master`, or whatever
  `git symbolic-ref refs/remotes/origin/HEAD` resolves to) unless the user explicitly
  confirms releasing from the current branch.
- Check for unpushed commits. If there are none, ask the user whether they still
  want to tag and release the current `HEAD` (e.g. a re-tag or a tag-only fix).

### 2. Calculate next version

Read the latest git tag (format `vMAJOR.MINOR.PATCH`; if there is no tag yet, treat
the current version as `v0.0.0`). Bump according to the argument:

- `patch`: bump PATCH
- `minor` (default if no argument is given): bump MINOR, reset PATCH to 0
- `major`: bump MAJOR, reset MINOR and PATCH to 0

Show the user: **"Releasing: v{current} -> v{next}"** and proceed.

### 3. Push and tag

```bash
git push origin <branch>
git tag -a v{next} -m "Release v{next}"
git push origin v{next}
```

### 4. Post-tag hook (optional, profile-driven)

This step lets the skill trigger whatever comes after "tag exists" in your own
setup — a secondary config/deploy repo, a CI/CD pipeline, a webhook, an asset
sync — without hardcoding any particular vendor or convention.

**Profile location:** `~/.claude/release-tag/profiles/<repo-name>.md`, where
`<repo-name>` is the basename of the repo root (from the Context section above).

**Step 0 — load or create the profile:**

1. Read the profile file for this repo.
2. If it does not exist, this is the first run for this repo: ask the user
   (one concise batch of questions) whether any of the following apply, and
   save the answers — including explicit "none" answers, so the skill never
   asks again unless the user requests an update:
   - **Secondary repo/config update** — is there another repo or file (e.g. a
     deploy-config repo, a manifest, an env file) that needs to be updated to
     point at the new tag? If yes, ask for a path template (it may include a
     `{repo}` placeholder for the repo name and a `{tag}` placeholder for the
     new tag) and a one-line description of what to change there (e.g. "set
     the image tag field to `{tag}`").
   - **CI/CD trigger** — does releasing need to fire a pipeline, webhook, or
     API call? If yes, ask for the exact command or HTTP call to make, with
     `{tag}` substituted in, and any required variables. Otherwise "none".
   - **Post-deploy asset sync** — is there a step that needs to run after
     tagging, unrelated to the two above (e.g. syncing a generated artifact
     somewhere)? If yes, ask for the command template. Otherwise "none".
3. On later runs, load the profile silently and execute whatever is
   configured. If everything is "none", skip straight to the summary — do not
   mention this step to the user.

**Profile file template:**

```markdown
# Release profile: <repo-name>

## Secondary repo/config update
- Pattern: none | <path template, may use {repo} and {tag}>
- Change: <what to update there, e.g. "set the pinned version field to {tag}">

## CI/CD trigger
- Type: none | command | webhook
- Details: <exact command or HTTP call, with {tag} substituted>

## Post-deploy asset sync
- Type: none | command
- Command: <shell command template, may use {tag}>
```

Run each configured hook in order (secondary repo update, then CI/CD trigger,
then asset sync), substituting `{repo}` and `{tag}` as defined. If a hook
fails, report the failure clearly but do not undo the tag/push from step 3 —
the release itself already happened; only the follow-up automation failed.

### 5. Summary

Report:
- Tag created and pushed: `v{next}`
- Branch pushed: `<branch>`
- Any post-tag hooks that ran (or "no post-tag hooks configured for this repo")
- Anything that failed and needs manual follow-up
