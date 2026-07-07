# Gap 11a — Cross-tenant isolation regression test

[Preamble must be prepended at invocation.]

## Objective

Add an automated regression test that **fails loudly** if any persistence operation drops the tenant filter.

## "Done" criteria (stack-agnostic)

A new test file covers, at minimum:

1. **Read isolation** — tenantA and tenantB own documents with the same primary key in the same collection/table; reading as tenantB returns only tenantB's row.
2. **Write isolation** — writing as tenantA does not modify or destroy tenantB's row with the same key.
3. **Aggregation isolation** — sums / counts / aggregations scoped to tenantA exclude tenantB's data.
4. **History/listing isolation** — listing the tenant's records (feedback, audit log, etc.) excludes other tenants.
5. **Token / credential isolation** — looking up by a partial credential (e.g. token prefix) returns only the caller-tenant's row, even when collisions exist.

Tests must be deterministic, fast (<10s), and exercise the **real** persistence-client code paths. Mock the underlying storage with an in-memory implementation that respects the same filter semantics as the real backend.

## Regression-detection clause

If during implementation you discover a write/read method whose filter does **NOT** include the tenant field:

- **Do NOT silently fix it.** Document in the PR body with file:line and a minimal cross-tenant exploitation scenario.
- Add a test that pins the regression via a signature/code assertion + an assertion that demonstrates the leak. The test should PASS by documenting the gap.
- The fix is owned by a separate follow-up PR — out of scope for this prompt.

Making the gap visible is more valuable than a stealth fix that a future refactor can re-introduce.

## Stack hints

### node

Test file: `src/__tests__/unit/CrossTenantIsolation.test.ts`. Use `jest.mock('mongodb', …)` (or whichever client) with an in-memory implementation of `findOne`, `find`, `insertOne`, `replaceOne`, `updateOne`, `deleteOne`, `countDocuments`, `aggregate` (with `$match`, `$group`, `$sort`, `$limit`).

### laravel

Test file: `tests/Feature/CrossTenantIsolationTest.php` using `Tests\TestCase` + `RefreshDatabase`. Seed two tenants. Exercise the service / repository / Eloquent model methods. Assert via `$this->assertDatabaseMissing(...)` and direct query assertions. Beware of global scopes (`BelongsToTenant` trait, middleware-set scope) — the test must hit the model directly, simulating what happens when a developer forgets to apply the scope.

### python

Test file: `tests/test_cross_tenant_isolation.py`. Use the project's test DB fixture (often `pytest-django` or `tortoise-orm` test mode). Seed two tenants, hit the repository functions, assert isolation.

### go

Test file: `internal/<pkg>/cross_tenant_test.go`. Use an interface mock or `testcontainers` for a real DB. Table-driven.

## Out of scope

- Fixing any regression found. Document only.
- Tests against a real production database.
