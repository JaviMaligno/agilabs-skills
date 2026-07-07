# Spec Review Doc Template (Phase 6)

This is the artifact that closes the loop. It's what the user reads to sign off, and — if appropriate — what they share with the client to demonstrate compliance.

Path: `docs/spec-review/<feature>.md`.

## Structure

```markdown
# Spec review — <feature name>

**Source spec:** <path to original document>
**Inventory:** [<feature>-inventory.md](./<feature>-inventory.md)
**Gap log:** [<feature>-gaps.md](./<feature>-gaps.md)
**PR / branch:** <link or name>
**Prepared:** <date>

## Summary

<one paragraph: what was delivered, what's still gap-blocked, what's deferred>

## Compliance table

The **Evidence (tests / screenshots)** column cites the proof for each point: test names/paths for backend, and screenshot path(s) under `docs/qa-evidence/<date>/screenshots/` for every UI point. A UI point with no screenshot is not proven.

| ID | Description | Surface | Action taken | Expected outcome | Evidence (tests / screenshots) | Status |
|----|-------------|---------|--------------|------------------|--------------------------------|--------|
| SPEC-1 | Reduce density on widget catalog page | UI | Collapsed low-priority columns into expandable row | Default view shows 5 columns, expand reveals rest | [screenshot](../qa-evidence/2026-04-18/screenshots/spec-1-before-after.png) · `catalog-list.spec.ts` | resolved |
| SPEC-2a | Client filter on widget catalog | UI | Added dropdown bound to active-client context | Dropdown filters list; persists across navigation | [screenshot](../qa-evidence/2026-04-18/screenshots/spec-2a.png) · `catalog-filter.spec.ts` | resolved |
| SPEC-2b | Status filter (active/archived) | UI | Added segmented control | Toggling switches query and resets pagination | [screenshot](../qa-evidence/2026-04-18/screenshots/spec-2b.gif) · `catalog-filter.spec.ts` | resolved |
| SPEC-3 | PDF export with Acme Corp logo | backend | Logo embedded via placeholder | PDF renders with header logo | PENDING — waiting on GAP-2 (client asset) | gap-blocked |

## Per-point detail

### SPEC-1 — Reduce density on widget catalog page

**Quote:** "La pantalla principal del catálogo de widgets está muy cargada, simplificar"

**Interpretation:** The client wants fewer visible fields by default, with a way to access the hidden ones on demand.

**What changed:**
- `apps/catalog/src/pages/CatalogList.tsx` — default visible columns reduced from 11 to 5
- `apps/catalog/src/components/CatalogRowExpander.tsx` — new component for the expand interaction
- Migration: none

**Tests:**
- `apps/catalog/src/pages/__tests__/CatalogList.spec.ts` — `SPEC-1: default view shows primary columns only`
- `apps/catalog/src/components/__tests__/CatalogRowExpander.spec.ts` — `SPEC-1: expander reveals hidden columns on click`

**Manual verification steps (UI — please run these):**
1. Go to `/catalog` (as any authenticated user with catalog access).
2. Verify the default table shows exactly these columns: `Reference`, `Client`, `Status`, `Updated`, `Actions`.
3. Click the chevron on any row. Verify it expands to show the 6 additional columns (`Material`, `Thickness`, `Width`, `Length`, `Weight`, `Notes`).
4. Click the chevron again. Verify it collapses.
5. Resize the browser to ~1024px width. Verify the 5-column view still fits without horizontal scroll.

**Expected visible outcome:** Screenshot at `../qa-evidence/2026-04-18/screenshots/spec-1-before-after.png` (captured against the deployment; indexed in [`visual-qa.md`](../qa-evidence/2026-04-18/visual-qa.md)).

**Caveats / follow-ups:** None.

---

### SPEC-3 — PDF export with Acme Corp logo

**Quote:** "Los PDFs exportados deben llevar el logo de Acme Corp"

**Interpretation:** PDF export includes the Acme Corp logo in the header.

**Status:** `gap-blocked` — waiting on [GAP-2](./<feature>-gaps.md#gap-2) (client needs to provide vector asset).

**Current state:** A placeholder logo is embedded to unblock end-to-end flow. When GAP-2 resolves, replace `apps/catalog/src/pdf/assets/logo-placeholder.svg` with the real asset and rerun the snapshot tests.

**Pending external input:** Acme Corp marketing — SVG/EPS logo. Asked 2026-04-17.

---

## Deferred / out of scope

Things that surfaced during implementation but were deliberately not included in this work. Each has a reason and a pointer to where they live if they come back.

| Item | Why deferred | Where tracked |
|------|--------------|---------------|
| Add bulk-archive action to widget catalog | Not in spec; would expand surface of SPEC-2b considerably | `docs/spec-review/<feature>-deferred.md#bulk-archive` |
| Refactor `CatalogList.tsx` hooks into a dedicated store | Code-quality cleanup, not client-visible | `docs/spec-review/<feature>-deferred.md#catalog-store-refactor` |

## Sign-off checklist (for the user)

- [ ] Summary table reflects what you expected to see delivered
- [ ] Every UI point has a captured screenshot under `docs/qa-evidence/<date>/screenshots/`, indexed in `visual-qa.md`
- [ ] All UI points manually verified using the steps above
- [ ] Gap-blocked points have clear owners and blocking reasons
- [ ] Deferred items are acceptable to defer
```

## Depth rules per surface

- **UI points** — always attach the captured screenshot(s) as the point's evidence (named by SPEC-ID under `docs/qa-evidence/<date>/screenshots/`, captured against the real deployment), and include per-point manual verification steps so a reviewer can reproduce. A user has to look at the screen; no automated test proves a UI point to the eyes of a reviewer — the screenshot is that proof. When the point depends on role/state, attach the relevant contrast (two roles, or before/after).
- **backend points** — per-point detail can be one or two paragraphs if tests cover it cleanly. Include a "how to verify" pointer (test name, curl command, log query) so the user can re-run if needed.
- **infra/process points** — link to the dashboard, healthcheck, runbook, or ADR. Don't duplicate that content in the review doc.

## Visual-evidence index (`docs/qa-evidence/<date>/visual-qa.md`)

UI captures live under `docs/qa-evidence/<date>/screenshots/` and are indexed in a sibling `visual-qa.md` that maps each capture to the SPEC-ID it proves. The review doc links to it. Minimal shape:

```markdown
# Visual QA evidence — <date>

| Screenshot | Proves | Deployment | Notes |
|------------|--------|------------|-------|
| screenshots/spec-2a.png | SPEC-2a | <deployment URL> | client-filter dropdown open |
| screenshots/spec-5-admin.png | SPEC-5 | <deployment URL> | admin role — action visible |
| screenshots/spec-5-viewer.png | SPEC-5 | <deployment URL> | viewer role — action hidden (contrast) |
```

## What this doc is not

It's not a PR description; that lives in the PR. It's not a changelog; that lives in commit history. It's the document that lets someone other than the implementer confirm — point by point — that the spec was honored.
