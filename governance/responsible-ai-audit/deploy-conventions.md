# Deploy conventions (Phase 6)

The skill never invents a deploy strategy. It follows whatever the operator's profile pins (`deploy_convention` field in `~/.claude/responsible-ai-audit.profile.json`), or — if the profile says `auto` — detects what the repo already has. If nothing matches, the skill exits without deploying and tells the operator.

## Detection order (first match wins, unless the profile pins one explicitly)

### 1. Semver tag + CI-triggered deploy workflow

**Signal:** a CI workflow (`.github/workflows/deploy.yml` or equivalent) triggered by `on: push: tags: ['v*']`.

**Procedure:**

1. Compute next semver from `git tag --sort=-v:refname | head -1`. Default to MINOR bump. Ask the operator.
2. `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. Monitor the workflow (e.g. `gh run watch` for GitHub Actions, or the equivalent for your CI provider).
4. Verify the deploy target (look in the workflow for the deploy step's URL/host).

### 2. Package-manager / Makefile deploy script

**Signal:** the manifest has a `scripts.deploy` entry (or a `Makefile` `deploy` target) that is not just `echo` / `exit 0`.

**Procedure:**

1. Read the script content and **show it to the operator** before running. Some `deploy` scripts hit production directly.
2. If the operator approves, run it.
3. Verify health if a target host is implied.

### 3. Sibling infra-as-code repo bumped on tag push (GitOps pattern)

**Signal:** a sibling repo (glob from the profile's `sibling_repo_glob`, commonly something like `../*-deploy*` or `../infra-*`) contains a Helm `values.yaml` / Kustomize overlay with an `image.tag` (or equivalent) field, watched by a GitOps controller (ArgoCD, Flux, etc.).

**Procedure:**

1. Confirm the target repo's CI builds on tag push.
2. Compute the tag using the profile's `tag_format_example` as a guide (e.g. `vX.Y.Z`, or a ticket-based scheme like `PROJ-1234` if that's what the profile records — ask the operator once and save it).
3. Tag and push:
   ```bash
   git tag "$TAG"
   git push origin "$TAG"
   ```
4. Wait for the build to succeed via your CI provider's status API/CLI. If it fails immediately (zero-duration failure), the CI YAML is likely invalid — surface this to the operator and stop.
5. Bump the sibling infra repo:
   ```bash
   cd <sibling-infra-repo>
   git checkout <the branch the GitOps controller watches>   # ask the operator if unclear
   # Edit values.yaml: set image.tag: $TAG and any restart-annotation field to now (UTC ISO).
   git add values.yaml
   git commit -m "deploy: bump <repo> to $TAG"
   git push origin HEAD
   ```
6. Verify health using the profile's `health_check_url_template` (if set). Expect a short propagation window (typically 1-2 minutes) after the infra-repo push before the GitOps controller syncs.

### 4. None of the above, or profile says `none`

Skip deploy. Print:

> Deploy convention not detected (or explicitly set to "none" in your profile). The compliance changes are merged to the base branch but not deployed. Apply your repo's normal release process.

Do not improvise.

## What the skill never does

- Force-push tags.
- Tag against a dirty working tree.
- Push to a sibling infra repo's `main`/`master` branch when the repo uses a separate staging/production branch (read the existing branch the file came from — that's the target).
- Bump production tags. Only staging/non-prod by default. Production promotion is operator-only.
