# Gap 11b — Per-tenant cost rate-limit

[Preamble must be prepended at invocation.]

## Objective

Add middleware that rejects AI calls when a tenant exceeds a rolling cost ceiling within a window. Mitigates the "denial of wallet" threat.

## "Done" criteria (stack-agnostic)

A middleware / filter / interceptor exists with these properties:

- Resolves `tenant_id` from the auth context (JWT claim, session, header) with a documented fallback chain.
- Reads cumulative cost for the tenant over a rolling window from existing persistence (does **not** introduce a new counter store).
- Configurable via env: `ENABLED` (default false), `WINDOW_SECONDS` (default 3600), `MAX_USD` (default 5.00).
- Returns `HTTP 429` with body `{error, tenant_id, window_seconds, limit_usd, current_usd}` and header `Retry-After: <seconds>` when over the limit.
- **Fail-open** on storage error: if the cost lookup throws, log a warning and let the request through. A storage outage must not cause a service outage.
- Applied only to AI-cost endpoints. NOT to health, feedback, schema, auth, admin.
- Disabled by default (opt-in).

Tests cover at minimum: disabled → pass-through; enabled below limit → pass-through; enabled at/above limit → 429 with body + Retry-After header; window correctly bounded; tenant resolution from primary claim with fallback.

## Stack hints

### node

File: `src/api/middleware/CostRateLimit.ts`. Factory `createCostRateLimit(options)` returning an Express `RequestHandler`. Default instance `costRateLimit` exported. Wire from `src/api/routes/index.ts` only on AI endpoints.

The cost-lookup function (`getCumulativeCost(tenantId, sinceIso)`) may need extending to accept the window parameter. Update both the implementation and the re-export.

Tests in `src/__tests__/unit/CostRateLimit.test.ts`.

### laravel

File: `app/Http/Middleware/AiCostRateLimit.php`. Register in `app/Http/Kernel.php` as a route middleware. Apply via route groups only on AI endpoints.

```php
public function handle($request, Closure $next) { /* resolve tenant, compute cost, 429 or next */ }
```

Cost lookup: a service class `app/Services/AiCostMetrics.php` with `cumulativeCost(tenantId, sinceIso)`.

Tests in `tests/Feature/AiCostRateLimitTest.php` using `withMiddleware` and `assertStatus(429)`.

### python

Three shapes depending on the service:

**HTTP service (FastAPI)** — dependency function:

```python
from fastapi import HTTPException, Depends

async def cost_rate_limit(tenant: str = Depends(get_tenant_id)) -> None:
    current = await get_cumulative_cost(tenant, since=window_start())
    if current >= LIMIT_USD:
        raise HTTPException(429, detail={"error": "rate_limit_exceeded", "tenant": tenant, ...},
                            headers={"Retry-After": str(WINDOW_SECONDS)})
```

Wire via `Depends(cost_rate_limit)` only on AI endpoints.

**HTTP service (Django)** — middleware class in `middleware/cost_rate_limit.py` with `__call__` returning `JsonResponse({...}, status=429)`.

**Chat bot / agent (no HTTP API)** — Add the check at the **entry** of the agent loop (e.g. `Agent.run`). Tenant resolution uses Slack `user` or `channel`. Per-day USD cap is the natural unit; per-hour can be added later. Tracked via the existing cost-metrics object (e.g. `RequestMetrics.estimated_cost_usd` aggregated by `user`).

Env vars regardless of shape: `AI_COST_LIMIT_ENABLED` (default false), `AI_COST_WINDOW_SECONDS` (default 86400 for daily caps), `AI_COST_MAX_USD` (default 1.00 for daily, 5.00 if hourly).

Tests with `pytest` + `freezegun` for the window.

### go

A middleware handler `func CostRateLimit(next http.Handler) http.Handler`. Read `tenantID` from context. Use a config struct. Tests in `_test.go` with `httptest`.

## Out of scope

- Persisting a separate counter store (Redis, etc.). Reuse existing cost telemetry.
- Soft-limit warnings.
- Enabling by default in any environment.
