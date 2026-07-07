---
name: authenticated-api-probe
description: Use when the user wants to connect to a web application given a base URL, username and password — authenticates via the app's login flow, extracts a bearer/session token, reports the deployed version/health, and stays available for follow-up authenticated API queries cross-checked against the app's route registrations and OpenAPI/spec, within the same conversation.
---

# authenticated-api-probe

Logs into a web application, extracts an authenticated token, reports the deployed
version/health, and holds the session open for follow-up authenticated API queries —
cross-checking whatever the app is actually running against its own spec, not just
trusting the spec.

This skill is **profile-driven**: every app wires up login, token exposure, health
reporting, and spec layout differently. The first time you run it against a given
project, ask the handful of structural questions below and save the answers to a
per-project profile. Every later run against that same project reuses the profile
silently — you only ask for fresh credentials.

## Project profile (ask once per project, reuse after)

**Profile location:** `~/.claude/authenticated-api-probe/profiles/<project-slug>.md`

Derive `<project-slug>` from something stable about the target, e.g. the git remote
of the current repo, or the hostname of `base_url` if there is no local repo:

```bash
SLUG=$(basename "$(git -C . rev-parse --show-toplevel 2>/dev/null || pwd)" \
  | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-' | sed -E 's/-+/-/g; s/^-|-$//g')
echo "profile=~/.claude/authenticated-api-probe/profiles/${SLUG}.md"
```

**Step 0 — load or create the profile:**

1. Read the profile file for this slug.
2. If it does not exist, or a required field is blank/placeholder, ask the user for
   the missing fields in one concise batch, then write them to the profile. Do not
   guess framework conventions — ask, or offer the examples below as multiple choice.
3. On later runs against the same project, reuse the profile silently. Only re-confirm
   if a run fails in a way that suggests the app's wiring changed (e.g. the login form
   no longer has the expected field, or the token pattern no longer matches).

**Required fields:**

| Field | Ask | Examples (present as options, not assumptions) |
|---|---|---|
| Login endpoint + method | Where does the login form/API post to? | `POST /login` (form), `POST /api/auth/login` (JSON) |
| Credential field names | What are the field names for the identifier and password? | `email`/`password`, `username`/`password` |
| CSRF/anti-forgery field | Does the login page embed a hidden anti-forgery token? Field name, or "none" | Laravel/Rails: hidden `_token`/`authenticity_token` input; Django: `csrfmiddlewaretoken`; many JSON APIs: none |
| Request format | Form-encoded or JSON body? | `application/x-www-form-urlencoded` vs `application/json` |
| Token exposure | Where does an authenticated session expose the API token? | (a) a field in the login response JSON — give the `jq` path, e.g. `.token` or `.data.access_token`; (b) a variable embedded in authenticated page HTML/JS — give the variable name/pattern, e.g. `window.API_TOKEN = "..."` or `Config.apiKey = "..."` |
| Version/health endpoint | What path reports the deployed version, build, or health? | `/health`, `/version`, `/about`, `/api/status` |
| Route registrations location | Where in the repo are API routes/handlers declared? | `routes/api.php` (Laravel), `urls.py` (Django), `config/routes.rb` (Rails), an Express/Fastify router file, decorated handlers in a FastAPI/NestJS app |
| API spec location | Where does the OpenAPI/Swagger/other spec live? | `openapi/*.yaml`, `swagger.json`, `docs/api-spec.yml` |

**Profile file template:**

```markdown
# Authenticated API Probe Profile — <project slug>

- Base URL pattern: <e.g. https://*.example.com, or leave blank if it varies freely>
- Login endpoint: <METHOD PATH>
- Credential fields: <identifier field name> / <password field name>
- CSRF field: <field name | none>
- Request format: <form-encoded | json>
- Token exposure: <json:<jq path> | js-var:<pattern>>
- Version/health endpoint: <PATH>
- Route registrations: <path(s) or glob>
- API spec location: <path(s) or glob>
- Notes: <anything project-specific worth remembering, e.g. "auth requires a role with X permission to see health">
```

Once the profile is loaded (or completed), announce the plan in one sentence
("conecto a `<base_url>` como `<user>`, hago login, extraigo el token y pido la
versión") and proceed.

## Per-run inputs (ask every invocation, never persist)

Ask the user for these three values **before doing anything else** — they are never
written to the profile:

| Field | Example | Notes |
|---|---|---|
| `base_url` | `https://staging.example.com` | No trailing slash. Abort if the scheme is `http://` unless the user explicitly overrides in this turn. |
| `username_or_email` | — | Whatever identifier the profile's login endpoint expects. |
| `password` | — | Never echoed back, never written to disk, never logged. |

## Credential handling rules

Apply these before Step A, and for the whole lifetime of the session.

**Bind inputs to shell-friendly names.** `LOGIN_USER` = the identifier, `LOGIN_PASS`
= the password, `BASE_URL` = the validated base URL.

**Preserve credentials byte-for-byte when parsing them from the chat.** When the user
pastes credentials inline (e.g. "URL user pass."), the value of each field is the
contiguous run of non-whitespace characters they typed — including trailing
punctuation like `.`, `!`, `?`, `:` and including any leading or final character that
looks like sentence punctuation. Do **not** trim those. Do **not** interpret a
trailing `.` as a sentence boundary. If the user wraps a value in backticks or quotes,
strip the wrapping quotes but keep the rest exactly. If you are unsure where one field
ends and the next begins, ask — do not guess.

**Confirm lengths immediately after binding (mandatory sanity check):**

```bash
echo "user_len=${#LOGIN_USER} pass_len=${#LOGIN_PASS}"
```

Print this line and pause for confirmation if anything looks suspicious (typical
password length is 8–32 chars; an identifier under 3 or above 64 chars is unusual).
This catches the most common credential-capture bug: a trailing character was dropped
during chat parsing. If the user says a length is wrong, ask them to re-send the
affected value and re-bind before running Step A. Never echo `LOGIN_USER` or
`LOGIN_PASS` themselves — lengths only.

**Avoid shell-reserved variable names.** Both bash and zsh treat names like
`USERNAME`, `USER`, `LOGNAME`, `HOSTNAME`, `HOME`, `PWD`, `PATH`, `path`, `IFS` and
similar as special parameters — setting them either fails silently, gets
re-assigned by the shell, or breaks `$PATH`. In particular, assigning
`USERNAME='someone@example.com'` can silently truncate back to the OS login name,
and using `path` as a loop variable (`for path in /a /b; do ...`) overwrites `$PATH`
mid-loop and makes `curl`, `head`, `rm` etc. disappear. That is why this skill uses
`LOGIN_USER` / `LOGIN_PASS` (never `USERNAME`, `USER`, or `PASSWORD`), and avoids
`path`, `i`, `home` etc. as loop variables.

**Never persist or echo credentials.** Not to the profile, not to a file, not in a
tool call's `description`, not in a text response — not even masked.

## Auth flow

Run the steps in order. Surface one short line per step to the user so progress is
visible. If any step fails, stop and report — do not continue to the next.

### Step A — generate a session id and pick a cookie jar path

```bash
SESS=$(openssl rand -hex 6)
JAR=/tmp/api-probe-${SESS}.cookies
echo "session=$SESS jar=$JAR"
```

Hold `SESS`, `JAR`, and `BASE_URL` in working memory; reuse across all subsequent
steps in this turn.

### Step B — validate the URL

```bash
curl -sS -o /dev/null -w "%{http_code} %{url_effective}\n" \
  -L --max-redirs 3 \
  "${BASE_URL}<login-page-path-from-profile>"
```

Expected: `200` on the login page/endpoint.

Failure modes:
- DNS / connection error: abort, ask the user to verify the host.
- `404` / `500`: the URL is not this app, or the instance is unhealthy. Report and stop.
- Redirect to an external identity provider (`adfs`, `okta`, `login.microsoftonline.com`,
  a third-party OAuth domain in `url_effective`): the environment requires SSO. Report
  — this skill covers direct username/password login, not SSO/OAuth redirects.

### Step C — fetch the anti-forgery token (skip if the profile's CSRF field is "none")

```bash
CSRF=$(curl -sS --cookie-jar "$JAR" "${BASE_URL}<login-page-path>" \
  | grep -oE 'name="<csrf-field-from-profile>"[^>]*value="[^"]+"' \
  | head -1 \
  | sed -E 's/.*value="([^"]+)".*/\1/')
echo "csrf_len=${#CSRF}"
```

Expected: a non-trivial length (commonly 20–64 chars). If `csrf_len=0`, the HTML did
not contain the expected hidden input — either the field name in the profile is
stale, or this isn't the login page. Report and stop rather than guessing a new name.

### Step D — submit the login

Build the request per the profile's request format. Form-encoded example:

```bash
curl -sS -o /dev/null -w "%{http_code} %{redirect_url}\n" \
  --cookie "$JAR" --cookie-jar "$JAR" \
  -X POST "${BASE_URL}<login-endpoint-path>" \
  --data-urlencode "<csrf-field>=${CSRF}" \
  --data-urlencode "<identifier-field>=${LOGIN_USER}" \
  --data-urlencode "<password-field>=${LOGIN_PASS}"
```

JSON example (used instead when the profile says the request format is JSON — omit
the CSRF field if the profile says "none"):

```bash
LOGIN_RESPONSE=$(curl -sS \
  --cookie "$JAR" --cookie-jar "$JAR" \
  -X POST "${BASE_URL}<login-endpoint-path>" \
  -H "Content-Type: application/json" \
  -d "{\"<identifier-field>\":\"${LOGIN_USER}\",\"<password-field>\":\"${LOGIN_PASS}\"}")
```

Expected: a `302`/`200` success signal that is **not** back to the login page, or (for
JSON APIs) a `2xx` with a token/user payload.

Failure modes:
- Redirect/response back to the login page: wrong credentials, or account locked. Report.
- `419`/`403` on a CSRF-protected form: CSRF mismatch — start over at Step C, do not
  retry blindly.
- `429`: rate limit. Report and stop.

If success, you have a valid session cookie in `$JAR` (and/or a token directly in the
JSON response, per the profile).

### Step E — extract the bearer/session token

Follow whichever mode the profile specifies as primary.

**Mode (a) — token in the login JSON response:**

```bash
TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '<jq-path-from-profile> // empty')
echo "token_len=${#TOKEN}"
```

**Mode (b) — token embedded as a JS variable in an authenticated page:**

```bash
TOKEN=$(curl -sS -L --cookie "$JAR" "${BASE_URL}/" \
  | grep -oE '<var-pattern-from-profile>[[:space:]]*=[[:space:]]*"[^"]+"' \
  | head -1 \
  | sed -E 's/.*"([^"]+)"$/\1/')
echo "token_len=${#TOKEN}"
```

Expected: a non-trivial length (commonly 20–64+ chars, framework-dependent).

Failure modes:
- `token_len=0`: the variable/field was not found. Try another authenticated page if
  mode (b) (a dashboard, settings, or profile route often carries the same footer/head
  script that a minimal-template landing page omits). If still empty, fall through to
  the fallback below.
- Token value looks like `none`/`null`/empty string literal: the page rendered as
  anonymous — the session cookie was not accepted. Re-check Step D.

#### Step E-fallback — try the other mode

If the primary mode produced an empty/invalid token, try whichever mode the profile
did **not** list as primary (JSON login response if primary was the JS-var mode, or
vice versa). If both fail, continue in **session-only mode**: the version/health query
still works via the cookie jar, but bearer-authenticated `/api/...` calls will not.
Say so explicitly.

At this point, hold `{ BASE_URL, JAR, TOKEN }` in working memory. `$TOKEN` may be
empty — that is the "session-only mode" state.

## Version/health query and optional repo alignment

### Step F — query the version/health endpoint from the profile

```bash
ABOUT=$(curl -sS --cookie "$JAR" \
  -H "X-Requested-With: XMLHttpRequest" \
  -H "Accept: application/json" \
  "${BASE_URL}<version-endpoint-from-profile>")
echo "$ABOUT" | jq . 2>/dev/null || echo "$ABOUT" | head -c 200
```

Pull out whatever version-ish fields are present — do not assume field names beyond
what the profile records; if unrecorded, try common candidates first and note which
one worked back into the profile for next time:

```bash
VERSION=$(echo "$ABOUT" | jq -r '.version // .commit // .sha // .build // .branch // empty')
echo "version=$VERSION"
```

Failure modes:
- `403`: the authenticated user lacks permission to view this endpoint. Report — the
  version cannot be read with this user.
- HTML response instead of JSON: cookie was rejected, or a proxy stripped
  `X-Requested-With`. Report, show the first 200 chars.
- Empty/missing version fields: the endpoint doesn't expose what the profile expects,
  or the deployed artifact lacks build metadata. Report — version not derivable this
  way for this environment.

If a commit SHA is present, normalise it (some frameworks return it quoted with a
trailing newline from a raw `git log` call):

```bash
COMMIT_CLEAN=$(echo "$COMMIT" | tr -d '"' | tr -d '\n' | tr -d ' ')
echo "commit_clean=$COMMIT_CLEAN length=${#COMMIT_CLEAN}"
```

A 40-char value is a full SHA; 7–12 chars is a short SHA. Anything else, show the raw
value and don't propose a checkout.

### Step G — report and optionally propose repo alignment

Report the fields to the user in one block, e.g.:

> Entorno: `${BASE_URL}`
> Versión/commit: `${VERSION}`
> (cualquier otro campo relevante devuelto)

If a commit SHA was found and the user is working in a local clone of the deployed
app, check whether the local repo has that commit:

```bash
git -C "$(git rev-parse --show-toplevel)" cat-file -e ${COMMIT_CLEAN} 2>&1 \
  && echo "have_commit=yes" \
  || echo "have_commit=no"
```

Propose one of these — **do not execute without explicit user approval**, since
`git checkout` is destructive if the worktree has uncommitted changes:

- `have_commit=yes`: "puedo hacer `git checkout ${COMMIT_CLEAN}` para alinear el repo. ¿procedo?"
- `have_commit=no`: "el commit no está local. Puedo `git fetch --all && git checkout ${COMMIT_CLEAN}`. ¿procedo?"

If the user approves, run `git status --porcelain` first; if it returns anything,
stop and warn before checking out.

## Follow-up queries — handler-vs-spec consistency check

After the version is reported, the user may ask for more data ("list the open items",
"show me the audit log for entity `<id>`", "what does the settings endpoint return").
Reuse the held `{ BASE_URL, JAR, TOKEN }` — never re-prompt for credentials.

**Choosing the right channel.** Check the route registrations location from the
profile first. If a bearer-authenticated route covers the case, fire a request with
`$TOKEN`. If only a session-authenticated (cookie) route exposes it, fire that URL
with `--cookie "$JAR"` and `-H "X-Requested-With: XMLHttpRequest"` so the app returns
JSON where possible. Many apps expose more through their web/session-authenticated
routes than through their token-authenticated API surface — falling back to the
cookie channel is expected and not a failure.

### Building the request — do this every time, the handler is authoritative, the spec is a hint

1. **Find the spec entry.** Search the API spec location(s) from the profile for the
   path in question, e.g. `grep -n "^  /<path>:" <spec-file>`.
2. **Find the route registration.** Search the route registrations location(s) from
   the profile for the path fragment. This gives you the handler/controller
   function or class and method.
3. **Open the handler.** Read the method body. Pay attention to:
   - The request fields actually read/validated.
   - Any middleware/guards on the route (auth requirements, rate limits, extra
     required headers or signed params).
   - The shape of the returned response (envelope, field names, nesting).
   - The actual HTTP method — specs drift from reality here more than anywhere else.
4. **Cross-check against the spec entry.** Compare method, path/query params,
   required vs optional body fields, response field names/casing, and any
   middleware-implied requirements the spec omits (e.g. a signing header).
5. **If everything matches, build and fire the request.**
6. **If there is a discrepancy, surface it before firing the request:**

   > ⚠️ Inconsistencia entre spec y handler en `<METHOD> <path>`:
   > - `<spec-file>:<line>` documenta `<X>`
   > - `<handler-file>:<line>` implementa `<Y>`
   > Voy a seguir la implementación del handler (que es lo que el entorno está
   > ejecutando). Si quieres, después del request actualizamos la spec.

   Then proceed using the handler's actual behaviour, not the spec's.
7. **Never silently "correct" the request to match a stale spec.** The warning is
   mandatory whenever they diverge.

### Firing the request — bearer-token example

```bash
curl -sS "${BASE_URL}<api-path>" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/json"
```

### Firing the request — session-cookie example

```bash
curl -sS --cookie "$JAR" \
  -H "X-Requested-With: XMLHttpRequest" \
  -H "Accept: application/json" \
  "${BASE_URL}<web-path>"
```

### Handling 401 mid-session

If a follow-up returns `401` and the user did not change credentials, try **one**
silent re-login (repeat Steps C, D, then re-extract via Step E). If the re-login also
fails, surface the error and stop — do not loop.

### Rendering the evidence

When showing a response to the user:
- Pretty-print JSON with `jq .` so it's readable.
- If the payload is large (> 50 lines), summarise the top-level shape first and show
  the full body only if asked.
- Always include the exact endpoint and HTTP status code so the operator can trace it back.
- If a discrepancy warning was raised, repeat it at the top of the evidence block so
  it does not get buried.

## Error matrix

| Symptom | Diagnosis | Action |
|---|---|---|
| `curl: (6) Could not resolve host` | DNS / typo in `base_url` | Stop. Ask the user to verify the host. |
| `curl: (7) Failed to connect` | Host is down or firewall blocks | Stop. Report. |
| Login page redirects to an external identity provider | SSO/OAuth enforced | Stop. Not supported by this skill. |
| Login page has no CSRF field where the profile expects one | Profile is stale, or maintenance page served | Stop. Show the first 200 chars of the response and ask the user to confirm the profile. |
| Login response redirects/renders back to the login page | Wrong credentials, locked account, IP filter | Stop. Before reporting, re-print `user_len` and `pass_len` and ask the user to confirm they match — the most common cause is a trailing character (often `.`, `!`, `?`) stripped from the password while parsing the chat message. If lengths look wrong, ask for a re-send and retry. Only if lengths are correct, report as genuine credential rejection. |
| CSRF/anti-forgery mismatch (`419`/`403` on submit) | Token expired or session mismatch | Retry once from Step C. If it fails again, stop. |
| `429` on login | Rate limit | Stop. Wait and retry only on user instruction. |
| Token not found in JSON response or JS var | Profile's path/pattern is stale, user has no token provisioned yet, or the page template used doesn't include it | Run Step E-fallback (the other mode). If that also fails, continue in session-only mode. |
| Version/health endpoint returns `403` | User lacks permission for that endpoint | Stop. Version cannot be read with this user. |
| Version/health endpoint returns HTML instead of JSON | Session cookie rejected, or a proxy stripped `X-Requested-With` | Stop. Show the first 200 chars. |
| Commit/version field empty | Deployed artifact has no build/version metadata | Report — version not derivable. Do not propose checkout. |
| Commit field length is neither ~40 nor ~7–12 chars | Unexpected format | Show the raw value. Do not propose checkout. |
| Follow-up `401` after a successful session | Token expired/rotated server-side | One silent retry of Steps C, D, E. If it fails, stop. |
| Follow-up `4xx` with a validation-errors body | Request body fails server-side validation | Show the errors, re-check the handler, do not retry blindly. |

## Cleanup

On user request, on a fresh invocation that supersedes the current one, or when the
user signals the session is done:

```bash
rm -f /tmp/api-probe-${SESS}.cookies
echo "cleaned"
```

Also discard `BASE_URL`, `LOGIN_USER`, `LOGIN_PASS`, `TOKEN`, `CSRF`, `JAR`, `SESS`
from your working notes for this turn. Do not echo them back later "for reference".
Cookie-jar files in `/tmp` rely on OS cleanup if the conversation ends without
explicit cleanup — acceptable since these are session cookies bound to the target
environment, but if you're the one wrapping up, run the cleanup snippet.

## Security notes

- **Never print the password** to the conversation, not even masked.
- **Never write the password to a file**, including the cookie jar (curl does not
  write request bodies to the cookie jar — verify by inspecting `$JAR` if in doubt).
- The bearer token can be echoed as `token_len=...` only — never as the literal value.
- If the user pastes a password into chat, do not repeat it in any tool call's
  `description` or in any text response.
- If the user is on plain `http://`, refuse unless they explicitly override in this turn.
- The per-project profile stores **structure** (endpoints, field names, spec paths),
  never credentials. If a draft profile ever ends up with a real password or token in
  it, strip it before saving.
