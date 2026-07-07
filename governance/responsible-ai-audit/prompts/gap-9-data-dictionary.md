# Gap 9 — Canonical data dictionary

[Preamble must be prepended at invocation.]

## Objective

Declare the service's API contract artifacts as the canonical data dictionary, with priority order and a change-control gate. Stack-agnostic — the deliverable is documentation, not code.

## "Done" criteria (stack-agnostic)

The repo's Responsible-AI controls document gains a section "Canonical Data Dictionary" containing:

1. Priority-ordered list of canonical artifacts. Item #1 wins on disagreement.
2. The cross-boundary contract artifact (shared/exchange schema, OpenAPI / Swagger, gRPC `.proto`, GraphQL schema, etc.) is ranked #1.
3. A `catalogue id` of the form `<repo-name>/schema/v<n>` (or service-equivalent) and a placeholder "Catalogue link: *placeholder — the data-catalog / governance owner to populate when the catalogue is live*".
4. A change-control gate: list every artifact that must be co-updated when a field is added (API spec + type/model + cache mapping + tracker entry if RA-driven).

Update `docs/RESPONSIBLE_AI_COMPLIANCE.md` item 9 to ✅ with a note that the catalogue link is the only follow-up.

## Discovery (stack-agnostic)

```bash
find . -name 'swagger.yaml' -o -name 'openapi.yaml' -o -name 'openapi.json' 2>/dev/null | head -3
find . -name '*.proto' 2>/dev/null | head -3
find . -name 'schema.graphql' -o -name 'schema.gql' 2>/dev/null | head -3
find . -path '*schemas*' -name '*.json' 2>/dev/null | head -10
```

List the actual artifact set found. Do not invent layers that don't exist.

## Stack hints

### node
Often `src/api/swagger.yaml` + `src/types/*.ts` + `src/data/standard-schemas/*.json`.

### laravel
Often `routes/api.php` + form-request validators + JSON resources + a separate OpenAPI generated via `darkaonline/l5-swagger` (`storage/api-docs/api-docs.json`).

### python
Often FastAPI auto-OpenAPI (`/openapi.json`) + Pydantic models in `app/schemas/`.

### go
Often `.proto` files for gRPC + handwritten OpenAPI YAML.

## Out of scope

- Registering with any external catalogue tool.
- Schema refactor.
