# Gap 5 — AI decision audit logging

[Preamble must be prepended at invocation.]

## Objective

Persist a full AI-decision audit record per AI call, written from the orchestration entry point on the success path **and** on the cached-result path. Surface enough provenance that an incident can be replayed deterministically.

## "Done" criteria (stack-agnostic)

For every AI inference path the service exposes, a persistent record is written containing **at minimum**:

- `request_id` (UUID per call)
- `tenant_id`, `token_prefix` (or whatever identifies the caller in this repo)
- `subject` — the input fields the AI saw (e.g. company_name, identifiers, country)
- `parameters` — runtime knobs that affect output (cache flag, model selector, classifier system)
- `model.id`, `model.version` — deployment identifier + API version
- `prompt.version`, `prompt.hash` — version selector + sha256(template) truncated to 12 chars
- `output` — codes/predictions/risk level returned
- `sources[]` — URLs, registries, retrieval hits that fed the call
- `guardrails_triggered[]` — at minimum: `cache_hit`, `blacklist_hit`, `no_web_presence`, plus repo-specific flags discovered during work
- `human_override?` — set later by the feedback flow when applicable
- `latency_ms`, plus cost fields if the repo tracks them

Persistence must be **best-effort**: a write failure must NOT break the user-facing call. Wrap with try/catch and log.

A unit/integration test confirms: a cache MISS writes a record with `model.id` and `prompt.version`; a cache HIT writes a record with `cache_hit` in `guardrails_triggered`.

## Stack hints

### node

Likely files: `src/services/MongoDBClient.ts` (or persistence client), `src/services/CacheService.ts`, `src/services/ClassificationService.ts` (orchestrator), `src/api/controllers/*Controller.ts`. New: `src/__tests__/unit/AuditLogging.test.ts`. The existing `storeMetadata` may be defined but never invoked — grep its call sites before editing.

Helpers to add if missing:

```ts
import { createHash, randomUUID } from 'crypto';
import { readFileSync, existsSync } from 'fs';
export function generateRequestId(): string { return randomUUID(); }
const promptHashCache = new Map<string, string>();
export function computePromptHash(version: string): string | undefined { /* read template, sha256, slice(12) */ }
```

### laravel

Likely files: `app/Services/AiAuditLogger.php` (new or existing), `app/Models/AiAuditRecord.php` (Eloquent model + migration), `database/migrations/*_create_ai_audit_records_table.php`, the AI orchestration class (often `app/Services/Ai/*`). Tests in `tests/Feature/AiAuditLoggingTest.php` using `Tests\TestCase` + `RefreshDatabase`.

Use the existing logging or database layer; do not introduce a new persistence engine. `Str::uuid()` for `request_id`, `hash('sha256', ...)` for `prompt.hash`. Wrap the write in `rescue(fn () => …, null)` or a try/catch so failures don't propagate.

### python

Look for an existing audit/telemetry module first — many Python services already have one (e.g. `src/<pkg>/telemetry.py` with `_emit_audit(event, payload)` and a dedicated `<pkg>.audit` logger). If it exists, the work is a **schema delta**: add `model_id`, `prompt_version`, `prompt_hash` to every `_emit_audit` call site.

Helper additions (typical):

```python
# in src/<pkg>/prompt.py (or wherever the system prompt is defined)
import hashlib
SYSTEM_PROMPT = """..."""
PROMPT_VERSION = "v1"
PROMPT_HASH = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:12]

# in src/<pkg>/telemetry.py
def _emit_audit(event: str, payload: dict) -> None:
    payload.setdefault("model_id", _MODEL_ID)            # from config
    payload.setdefault("prompt_version", PROMPT_VERSION)
    payload.setdefault("prompt_hash", PROMPT_HASH)
    try:
        audit_logger.info(event, extra={"payload": payload})
    except Exception as e:
        logger.warning("audit emission failed: %s", e)
```

Tests in `tests/unit/test_audit.py` (or wherever the audit suite lives) must assert every event carries `model_id` + `prompt_version`. If the repo uses `pytest-mock`, monkey-patch `audit_logger` and inspect calls.

If no audit module exists, add one (`src/<pkg>/audit.py`) and wire it from the orchestrator/agent entry point. Use `uuid.uuid4()` for `request_id`. Best-effort persistence: never let an audit-write failure propagate.

### go

Likely files: `internal/audit/audit.go`, `internal/audit/audit_test.go`. Use `github.com/google/uuid`, `crypto/sha256`. Persistence interface should be small; mock in tests. Pass the audit record by value to keep allocation predictable.

## Out of scope

- Plumbing guardrail flags that need new signals from the model/risk engine (e.g., `keyword_disambig_filter`, `code_validator_corrected`). List them as TODO; a follow-up PR can add them.
- Retention policy changes.
- Modifying the AI cache schema (separate gap).
