# Spec Inventory Template

The inventory is the source of truth for every subsequent phase. Keep it in `docs/spec-review/<feature>-inventory.md` and update statuses as work progresses.

## Format

```markdown
# Spec inventory — <feature name>

**Source document:** <path to Word / PRD / etc.>
**Version / date:** <version string or "received 2026-04-17">
**Last updated:** <date>

## Points

| ID | Verbatim quote | Interpretation | Surface | Source location | Status |
|----|----------------|----------------|---------|-----------------|--------|
| SPEC-1 | "El listado de widgets debe filtrarse por cliente activo" | The widget catalog screen shows only widgets belonging to the currently selected active client | UI | p.2, point 1.a | pending |
| SPEC-2 | "Los precios se recalculan cuando cambia la tarifa vigente" | Pricing engine reruns on tariff-effective-date changes | backend | p.2, point 1.b | pending |
| SPEC-3 | "[long paragraph about export format...]" | Export produces XLSX matching the sample file the client provided | backend | p.4, point 3 | gap-blocked |
| SPEC-4 | "Mejorar la UX" | [too vague to interpret] | UI | p.5, intro | gap-blocked |
```

## Rules for writing entries

**Quote verbatim.** If the original says "debe filtrarse por cliente activo", the quote column has exactly that. This is what makes the inventory auditable — the user can compare side-by-side with the original document.

**Keep interpretations to one sentence.** If you need a paragraph to interpret a point, it's probably two points — split it.

**One atomic requirement per row.** A bullet in the Word that says "Añadir filtro por cliente y por fecha" is two rows (`SPEC-Na` and `SPEC-Nb`), not one.

**Stable IDs.** Once assigned, never renumber. If a point turns out to be redundant, mark it `out-of-scope` with a reason rather than deleting it. Plans and commits may already reference the ID.

**Surface field drives review depth:**
- `UI` — user will need to eyeball the screen to verify; review doc needs step-by-step manual verification
- `backend` — verifiable by tests/logs; review doc detail can be terse
- `infra` — deployment/config; review doc points to dashboards or healthchecks
- `docs` — documentation changes; review doc points to the doc diff
- `process` — non-code changes (workflows, handoffs); review doc describes the new process

**Status values:**
- `pending` — in scope, not yet done
- `gap-blocked` — needs external input (client / stakeholder) before work can start
- `out-of-scope` — explicitly deferred; include a one-line reason
- `resolved` — done, evidence captured in the review doc

## Example — Acme Corp widget catalog feedback Word

Input (excerpt from hypothetical Word):
> 1. La pantalla principal del catálogo de widgets está muy cargada, simplificar.
> 2. Añadir filtro por cliente activo y por estado (activo/archivado).
> 3. Los PDFs exportados deben llevar el logo de Acme Corp.

Inventory:

| ID | Verbatim | Interpretation | Surface | Location | Status |
|----|----------|----------------|---------|----------|--------|
| SPEC-1 | "La pantalla principal del catálogo de widgets está muy cargada, simplificar" | Reduce information density on the widget catalog page (needs concrete criteria) | UI | p.1, point 1 | gap-blocked |
| SPEC-2a | "Añadir filtro por cliente activo" | Add a client-filter dropdown to the widget catalog page | UI | p.1, point 2 | pending |
| SPEC-2b | "Añadir filtro por estado (activo/archivado)" | Add a status filter (active/archived) to the widget catalog page | UI | p.1, point 2 | pending |
| SPEC-3 | "Los PDFs exportados deben llevar el logo de Acme Corp" | PDF export includes Acme Corp logo (need logo asset from client) | backend | p.1, point 3 | gap-blocked |

Notes on this example:
- `SPEC-1` is vague ("simplificar") — gap-blocked until the client says what "simpler" means (fewer columns? collapsed rows? different default sort?).
- `SPEC-2` splits into two rows because filters are independent requirements.
- `SPEC-3` is gap-blocked on an asset, not a decision.
