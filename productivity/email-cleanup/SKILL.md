---
name: email-cleanup
description: >
  Intelligent Gmail inbox cleanup using GWS CLI. Use this skill whenever the user mentions
  cleaning email, inbox triage, email cleanup, unread emails, archiving emails, marking emails
  as read, Gmail maintenance, or wants to deal with notification noise from GitHub, Railway,
  Linear, or promotional emails. Also trigger when the user says "/email-cleanup" or asks to
  "clean my inbox", "triage my email", "deal with my notifications", or similar.
---

# Email Cleanup

Intelligent, rule-based Gmail inbox cleanup using GWS CLI locally.

## Configure these lists (edit before first use)

This skill only works well once you tell it what *your* inbox actually looks like. The
rules below reference generic placeholders (`myapp-prod`, `org/repo-a`, `yourcompany.com`,
etc.) — replace them with your own services, repos, and trusted domains. When the user
says things like "add X to my repos" or "I don't care about Y anymore", update this
section directly; it is the single source of truth for what the user cares about.

```yaml
# Deploy/notification platform (e.g. Railway, Render, Fly.io) — services you actually run
my_services:
  - myapp-prod          # subject contains "myapp-prod"
  - myapp-staging        # subject contains "myapp-staging"
  - api-backend / api-frontend   # subject contains these, under the "myapp" project

# GitHub repos you own/maintain — dependabot, CI, and PR notifications for these
# are real signal (keep most recent, or keep all, per rule below)
my_repos:
  - org/repo-a
  - org/repo-b
  - org/repo-c

# Domains whose senders are real people/clients — never touch automatically
trusted_domains:
  - yourcompany.com
  - client-a.com

# Known promotional senders to always auto-archive (grows over time)
known_promo_senders:
  - notifications@a.example-promo.com   # e.g. a SaaS trial/marketing sender
  - trials@example-saas.com
  - hello@example-newsletter.com
```

## Prerequisites

GWS CLI must be authenticated with Gmail scope. If auth fails (RAPT error), ask the user to run:
```bash
! gws auth login -s gmail
```

Verify auth works before proceeding:
```bash
gws gmail users getProfile --params '{"userId":"me"}'
```

## Core Operations

All modifications use the Gmail API via GWS CLI. The key operations:

```bash
# Mark as read + archive (the standard cleanup action)
gws gmail users messages batchModify --params '{"userId":"me"}' \
  --json '{"ids":["id1","id2",...],"removeLabelIds":["UNREAD","INBOX"]}'

# List messages matching a query
gws gmail users messages list --params '{"userId":"me","q":"<gmail-query>","maxResults":500}'

# Read a specific message
gws gmail users messages get --params '{"userId":"me","id":"<messageId>","format":"metadata"}'
```

`batchModify` returns empty on success (204). It supports up to 1000 IDs per call.
Redirect stderr with `2>/dev/null` when piping to node/scripts (GWS prints "Using keyring backend: keyring" to stderr).

## Cleanup Rules

These rules are ordered by priority. Process each category, show the user what you found, and act.
All rules reference the lists in "Configure these lists" above — keep that section in sync
with the user's real inbox.

### Rule 1: Promotional Spam (archive all)

Auto-archive without asking any sender in `known_promo_senders`, e.g.:

| Sender | Query filter |
|--------|-------------|
| Example promo sender | `from:notifications@a.example-promo.com` |
| Example SaaS trial | `from:trials@example-saas.com` |
| Example newsletter | `from:hello@example-newsletter.com` |

For other `category:promotions` emails: list them and ask the user before archiving. New senders may appear over time — if the user confirms one is always-junk, add it to `known_promo_senders`.

### Rule 2: Deploy/Notification Platform Alerts (smart filter)

Query: `from:<notification-sender-for-your-deploy-platform> is:unread`
(e.g. `from:hello@notify.railway.app is:unread` for Railway)

**Services in `my_services`** (keep most recent per service, archive the rest):
- For each service in the list, if there are multiple notifications (e.g. 5 "Build failed for myapp-prod"), keep the newest, archive the other 4.

**All other projects/services not in `my_services`**: archive everything.

**Logic**: For the user's services, only the most recent notification matters.

### Rule 3: GitHub Dependabot (smart filter)

Query: `from:notifications@github.com is:unread (subject:"Bump" OR subject:"chore(deps)")`

**Repos in `my_repos`** (keep most recent per repo, archive the rest).

**All other repos**: archive everything.

### Rule 4: GitHub CI Failures (smart filter)

Query: `from:notifications@github.com is:unread subject:"Run failed"`

Same repo filter as Rule 3. Use a negative query to find non-user repos, substituting
the repo names from `my_repos`:
```
from:notifications@github.com is:unread subject:"Run failed"
-subject:"repo-a" -subject:"repo-b" -subject:"repo-c"
```
Archive all results from that query. Keep the user's repos untouched.

### Rule 5: GitHub PRs and Other (smart filter)

Query (excluding Dependabot and CI):
```
from:notifications@github.com is:unread
-subject:"Bump" -subject:"chore(deps)" -subject:"Run failed"
```

Same repo filter — negative query using `my_repos` names to archive non-user repos.
Archive results. The user's own repo PRs are real signal — keep them all.

### Rule 6: Generic Newsletters (archive all)

Query pattern: `from:<known-newsletter-sender> is:unread`

Archive all without asking, once a sender is confirmed as a newsletter the user doesn't read.

### Rule 7: Linear Notifications (smart filter)

Query: `from:notifications@linear.app is:unread`

- **Keep**: emails where subject contains "mentioned you", "assigned the issue to you", or "assigned you"
- **Archive**: generic digest emails ("X unread notifications on <workspace>"), status changes by others

Present the list to the user for confirmation before acting, since Linear notifications can be nuanced.

### Rule 8: Product Marketing Emails (archive all)

Query pattern: `from:<known-product-marketing-sender> is:unread`

Archive all — pure marketing, no signal.

### Signal (DO NOT touch)

These categories are real signal. Never archive without explicit user request:
- Emails from actual people (senders on `trusted_domains`, clients)
- Meeting-note bots (e.g. `from:gemini-notes@google.com`, `from:notifications@mail.granola.ai`)
- GitHub security notifications (`from:noreply@github.com` with security-related subjects)
- Google Calendar / Google Meet notifications

## Workflow

When the user invokes this skill:

1. **Verify auth** - check GWS CLI is authenticated
2. **Scan inbox** - run searches for each rule category, count results
3. **Present summary** - show the user a table of what was found per category
4. **Process rules in order** - for auto-archive rules, proceed. For smart-filter rules, show what you'll keep vs archive
5. **Report results** - show total cleaned, total kept, what remains

Between categories, briefly report progress. At the end, show a summary table.

## Efficient Patterns

To collect IDs and filter in one step:
```bash
gws gmail users messages list --params '{"userId":"me","q":"...","maxResults":500}' 2>/dev/null | node -e "
const chunks = [];
process.stdin.on('data', c => chunks.push(c));
process.stdin.on('end', () => {
  const data = JSON.parse(chunks.join(''));
  const msgs = data.messages || [];
  const keep = new Set(['id1','id2']);
  const archive = msgs.filter(m => !keep.has(m.id)).map(m => m.id);
  console.log(JSON.stringify(archive));
});
"
```

## Updating Rules

The user's repo/service lists will change over time. When the user says things like "add X to my repos" or "I don't care about Y anymore", update the "Configure these lists" section at the top of this file directly. Those lists are the source of truth for what the user cares about.

## Gmail MCP Fallback

If GWS CLI is not available or auth fails, the Gmail MCP tools (`gmail_search_messages`, `gmail_read_message`, etc.) can be used for **analysis only** - they cannot modify, archive, or mark emails as read. In this case, present the analysis and tell the user what you would do if GWS CLI were available.
