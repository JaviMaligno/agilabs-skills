# Gap 10 — Model + prompt provenance in responses

[Preamble must be prepended at invocation.]

## Objective

Expose `model_id`, `model_version`, `prompt_version`, `prompt_hash` in the service's API response so downstream consumers can persist lineage. Persist the same fields in any cache so a cache HIT replays the original provenance.

## "Done" criteria (stack-agnostic)

1. The public response DTO (or its equivalent) for any AI-backed endpoint exposes the four fields, all optional for back-compat.
2. The orchestrator (the function that calls the model) populates them from the runtime model/prompt configuration.
3. Any cache layer that stores the AI response is extended to persist the four fields; existing cache entries pre-change pass through as undefined.
4. API documentation (OpenAPI / Swagger / Postman) lists the four fields.
5. If the response includes a structured cross-boundary payload (e.g. a shared data-contract object), the four fields are grouped under a `provenance` object that is omitted entirely when all four are unset.
6. Test covers cache MISS (populated), cache HIT with persisted provenance (echoed), cache HIT without provenance (undefined).

## Stack hints

### node

Touch points: `src/services/ClassificationService.ts` (or orchestrator), `src/services/CacheService.ts`, `src/services/MongoDBClient.ts` (`CacheDocument` extension), `src/api/controllers/*Controller.ts`, `src/api/swagger.yaml`. New test: `src/__tests__/unit/ResponseProvenance.test.ts`.

Add `computePromptHash` helper (if missing — Gap 5 may have already added it):

```ts
import { createHash } from 'crypto';
import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
const promptHashCache = new Map<string, string>();
export function computePromptHash(promptVersion: string): string | undefined { /* read template, sha256, slice(12) */ }
```

### laravel

Touch points: the response resource (`app/Http/Resources/*`) gains four optional fields. The service that builds the response (often `app/Services/Ai/*Service.php`) populates them from `config('ai')`. Cache layer (often `Illuminate\Support\Facades\Cache` with a Redis or DB store) needs `tags` or `keys` updated to include provenance — extend the cached payload shape.

Tests in `tests/Feature/ProvenanceTest.php` using `Http::fake()` and asserting JSON path.

### python

If the service has an HTTP response model (FastAPI / Flask + pydantic / dataclass), add an optional `ProvenanceFields` block:

```python
from pydantic import BaseModel

class ProvenanceFields(BaseModel):
    model_id: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    prompt_hash: str | None = None

class ResponseModel(BaseModel):
    # ...existing fields...
    provenance: ProvenanceFields | None = None
```

If the service is a chat bot / agent with no HTTP API, the four fields go into the **audit event payload** and any user-facing trailer the bot emits (e.g. "model=<id> prompt=v1@abc123"). The audit-event schema is shared with gap-5; coordinate so both gaps land in one PR.

Cache layer: extend the cached dataclass with the four fields. Older cache entries pass through as `None`. Tests with `pytest` + parametrised cache MISS / HIT / HIT-without-provenance.

### go

Add the four fields to the response struct, json-tagged optional. Orchestrator populates from config. Cache (e.g. `bigcache`, redis client) extended. Table-driven test in the orchestrator's `_test.go`.

## Out of scope

- Adding `search_provider_version` or other extended provenance — optional follow-up.
- Refactoring caches not used for AI.
