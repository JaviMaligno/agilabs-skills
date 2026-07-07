---
name: deployment-verification
description: Verify a freshly deployed service end-to-end - infrastructure health, platform/config wiring, and a browser-driven UI smoke test - then troubleshoot systematically if anything fails. Profile-driven (orchestrator, health check, UI tool asked once and reused). Use right after a deployment finishes, before declaring it good.
---

# Deployment Verification

A thin, tool-agnostic framework for verifying that something you just deployed
actually works — from infrastructure up through a real UI interaction — and for
troubleshooting it methodically when it doesn't.

This skill does not know your stack. It asks you once, up front, and reuses the
answers on every later run.

## Profile (ask once, reuse forever)

**Profile location:** `~/.claude/deployment-verification/profile.md`

**Step 0 — load or create the profile:**

1. Read `~/.claude/deployment-verification/profile.md`.
2. If it does not exist, or a REQUIRED field is blank/placeholder, ask the user for
   the missing fields in one concise batch, then write them to the profile file.
   Do not guess a health-check URL or CLI name — ask.
3. On later runs, reuse the profile silently. Re-confirm only if a command from it
   fails outright (wrong CLI, endpoint 404s) — that's a signal the profile is stale.

**Required fields:**

- **Orchestrator / platform** — what runs the service (Kubernetes, Docker Swarm,
  ECS/Fargate, Nomad, a PaaS, systemd on a VM, serverless...).
- **CLI** — the command used to inspect it (`kubectl`, `docker`, `aws ecs`, `nomad`,
  `ssh <host> systemctl`, a platform-specific CLI...), plus how to select the right
  cluster/context/namespace/environment.
- **Health check** — the command or endpoint that proves the process is alive
  (`GET /health`, `GET /healthz`, a CLI status command...) and what a healthy
  response looks like.
- **UI tool** — how to drive the browser for the smoke test. Default to the
  `playwright-cli` skill (see Phase 3) unless the user names another tool.
- **Base URL(s) per environment** — dev / staging / prod, however the user names them.

**Optional fields (fill in if the service has them, skip otherwise):**

- **Data store** — type (SQL, KV, object storage, queue...) and a read-only
  connectivity check for it.
- **Service registry / discovery** — anything downstream that needs to see the
  service (an API gateway, a discovery index, a config-driven UI) before it's
  reachable from the outside.
- **Evidence directory convention** — where screenshots/traces from Phase 3 should
  be saved, e.g. `docs/verification/{service}/{date}/`.

**Profile file template** (`~/.claude/deployment-verification/profile.md`):

```markdown
# Deployment Verification Profile

## Platform
- Orchestrator: <e.g. Kubernetes / ECS / Nomad / systemd>
- CLI: <e.g. kubectl / docker / aws ecs / nomad>
- Context selection: <command to check/set cluster, namespace, or environment>

## Health check
- Command or endpoint: <e.g. `curl {base_url}/health`, or a CLI status command>
- Healthy response: <e.g. HTTP 200 + `{"status":"UP"}`>

## Data store (optional)
- Type: <e.g. Postgres / Redis / S3 / none>
- Connectivity check: <read-only command>

## Registry / discovery (optional)
- What needs to see this service before it's reachable: <e.g. API gateway, service mesh, admin UI toggle>
- How to check it's registered: <command or UI path>

## UI tool
- Driver: playwright-cli (default) — see the `playwright-cli` skill for commands
- Base URLs: dev=<url> staging=<url> prod=<url>
- Auth approach: <e.g. saved storage-state file path, SSO redirect, service account>

## Evidence
- Output directory: <e.g. docs/verification/{service}/{date}/>
```

## Arguments

`$ARGUMENTS`: the service/deployment name, and optionally the target environment
(default to whichever environment the user just deployed to).

## Cross-references

- **Pre-requisite:** the deployment itself. This skill verifies; it doesn't deploy.
- **Browser automation:** the `playwright-cli` skill — use it for all of Phase 3
  rather than re-deriving browser commands here.
- **Deep root-causing:** if Phase T's diagnostic tree runs out of leads, hand off to
  a systematic-debugging skill/process rather than guessing further.
- **Before declaring done:** re-check with a verification-before-completion habit —
  evidence before the "it works" claim.

---

## Phase 0: Prerequisites & Detection

### 0.1 Access check

Confirm you can actually reach the target environment with the profile's CLI
(VPN/SSO/cluster credentials as applicable). If not, stop and tell the user what's
missing rather than guessing at commands that will time out later and look like a
service failure.

### 0.2 Detect what this service needs

Before running checks, work out which of them apply:

- **Has a data store?** (check its config/env for connection settings)
- **Has a registry/discovery step?** (check whether anything needs to "see" it
  before traffic reaches it)
- **Has a UI surface at all?**, or is it API/worker-only (skip Phase 3 if so)

Record these — they gate which Phase 1/2/3 sub-checks run.

### 0.3 Confirm the target

State explicitly: service name, environment, and the base URL/host you're about to
hit. Cheap to get wrong, expensive to debug later when you've been checking the
wrong environment the whole time.

---

## Phase 1: Infrastructure Checklist

Generic, tool-agnostic — swap in the profile's CLI for each check. Run all of them,
then present a single pass/fail summary before moving on.

### 1.1 Process/instance status

Is the thing actually running? (pod/task/container/process listed and in a ready
state, not crash-looping or pending).

### 1.2 Health check

Run the profile's health command/endpoint. Prefer checking from as close to the
service as the platform allows (e.g. from inside the cluster/network) before
falling back to an external check — external checks fail for routing/VPN reasons
that have nothing to do with the deployment, and that false signal wastes the most
time in this whole process.

### 1.3 Connectivity to dependencies

If the service depends on other services, confirm it can reach them (not that they
work — just that the network path and credentials are there).

### 1.4 Data store (only if applicable, from 0.2)

A read-only check: can the service authenticate to its data store and see the
expected shape (tables/keys/buckets exist)? Do not run destructive checks.

### 1.5 Summary

```
Infrastructure check for {service} ({env}):
  [PASS] Process running
  [PASS] Health check responds
  [PASS] Dependency connectivity
  [PASS] Data store reachable (if applicable)
```

**Any FAIL → go to Phase T before continuing.**

---

## Phase 2: Platform / Config Check

Distinct from Phase 1: infra can be perfectly healthy while the platform still
doesn't know the service exists, or has it configured wrong.

### 2.1 Is it registered / discoverable?

If the profile has a registry/discovery step, confirm the service actually shows up
there. Watch for pagination or caching in the discovery mechanism itself — "not
found" from a paginated listing can mean "exists, but past the page limit," which
is a very different fix than "not deployed." Don't assume the first negative result
is the whole truth; check with a wider page/limit or a direct lookup before
concluding it's missing.

### 2.2 Is the config correct, not just present?

Check the specific fields that commonly get left as template defaults after a
copy-paste deploy (display name, routing path, environment identifiers, feature
flags). A service that's "configured" with placeholder values is functionally
unconfigured — validate values, not just presence.

### 2.3 Propagation delay

Many of these checks (registry refresh, cache invalidation, config sync) have a
lag. If something looks wrong immediately after deploying, note the expected
propagation window from the profile (or ask once and record it) before treating it
as a real failure.

---

## Phase 3: Browser-Driven UI Smoke Test

Use the `playwright-cli` skill for every command in this phase — it already covers
sessions, snapshots, fill/click, tracing, and screenshots. This phase only adds the
*sequence* and *what to capture as evidence*; it does not re-document Playwright
usage.

### 3.1 Start evidence capture

Start a trace (or screen recording) before doing anything else in the browser, per
the `playwright-cli` skill's tracing commands. Stop it at the end of 3.4, not
before — a trace that misses the failure is useless.

### 3.2 Reach the feature under test

Navigate to the base URL from the profile, authenticate if needed (reuse a saved
auth/storage state where the profile provides one), and get to the specific
screen/flow that exercises the deployed change.

### 3.3 Exercise the flow

Drive the minimum interaction that proves the deployment works end-to-end —
usually: trigger the action, observe the result render, and (if the service has
a detail/report view) open it too. Prefer real interaction over just loading a
page — a smoke test that never clicks anything doesn't verify much.

### 3.4 Capture evidence

Take a screenshot of the passing state, then stop the trace/recording. Save both
to the profile's evidence directory convention, e.g.
`{evidence_dir}/{service}/{date}/`.

### 3.5 Pass/fail

```
UI smoke test for {service} ({env}):
  [PASS] Reached target screen
  [PASS] Flow executed without error
  [PASS] Result rendered as expected
  Evidence: {evidence_dir}/{service}/{date}/
```

Any FAIL here → Phase T.

---

## Phase T: Troubleshooting & Fix Cycle

Entered from any phase failure. The loop is always the same shape:

```
Symptom → most-probable cause first → fix → wait for propagation → re-run
the ONE check that failed → resolved?
  yes → resume at the phase that failed
  no  → next most-probable cause
  all exhausted → stop, report the action log, ask the user
```

### Build a diagnostic tree per symptom, not per fix

For each recurring symptom in your stack, keep an ordered list of causes by
observed frequency, with a one-line diagnosis command and a one-line fix. Example
shape (fill with your platform's real causes/commands):

| # | Cause (most likely first) | Diagnosis | Fix |
|---|---|---|---|
| 1 | Most common cause | How you'd confirm it | Smallest fix that addresses it |
| 2 | Second most common | ... | ... |
| 3 | Less common | ... | ... |

Keep separate trees for distinct symptoms (e.g. "process won't start" vs "health
check fails" vs "not discoverable" vs "UI shows no data") — a single tree covering
everything gets unusable fast.

### Fix cycle protocol

For every fix attempt:

1. **Explain** what will change and why, before doing it.
2. **Confirm** before anything destructive (restarts, config overwrites, cache
   clears that affect other consumers).
3. **Apply** the smallest fix that addresses the diagnosed cause.
4. **Wait** for the fix to actually take effect — sync/propagation delay from the
   profile or platform docs, not a guess. Re-checking too early produces false
   negatives that send you down the wrong branch of the tree.
5. **Re-run** only the specific check that failed, not the whole verification.
6. **If still failing**, move to the next cause in the tree.
7. **If the tree is exhausted**, stop. Report what you tried and why each attempt
   didn't resolve it, and ask the user rather than continuing to guess.

### Action log

Keep a running log while troubleshooting — it's the artifact that lets someone else
pick this up, and it's usually the fastest way to notice you're repeating a step:

```
Troubleshooting log for {service} ({env}):
  [10:01] Symptom: health check fails
  [10:01] Try 1: checked process status → running, ruled out
  [10:02] Try 2: checked dependency connectivity → refused
  [10:02] Fix: corrected connection config
  [10:03] Wait: 30s for restart
  [10:03] Re-check: health check → PASS
```

---

## Common Mistakes

| Mistake | Consequence | Prevention |
|---|---|---|
| Checking health from outside the network before checking from inside | A routing/VPN timeout looks like a broken deployment | Check as close to the service as the platform allows first |
| Trusting a paginated/cached discovery listing's first negative result | "Not found" reported when the service exists but is past a limit or stale cache | Retry with a wider page/limit or a direct (non-listing) lookup before concluding it's missing |
| Re-running the full verification after every fix attempt | Slow feedback loop, unclear which fix actually worked | Re-run only the specific check that failed |
| Not waiting for the platform's real propagation delay | False "still broken" reading right after a fix that hadn't taken effect yet | Wait the profile's documented delay, or measure it once and record it |
| Reusing a stale UI session/state from a previous deployment | Smoke test passes/fails against cached config, not the new deployment | Start fresh where the platform caches config per session/application |
| Treating "present" config as "correct" config | Template/placeholder values pass an existence check but are functionally broken | Validate actual values, not just that a field is non-empty |
| Skipping evidence capture until after something breaks | No trace/screenshot of the actual failure state | Start tracing/recording before Phase 3.2, stop after 3.4 |
| Guessing at the health-check command instead of using the profile | Wasted round-trips on a wrong endpoint/CLI | Ask once, save to the profile, reuse |
| Declaring success without a real interaction in Phase 3 | A page that loads is not the same as a flow that works | Exercise the actual feature, not just navigation |
