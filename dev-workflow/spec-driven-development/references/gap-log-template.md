# Gap Log Template

The gap log captures points where the spec is insufficient to plan or implement. Living document at `docs/spec-review/<feature>-gaps.md`. Update it as gaps get resolved.

## Format

```markdown
# Gaps & pending external inputs — <feature name>

**Related inventory:** <path to inventory>
**Last updated:** <date>

## Open gaps

### GAP-1 — SPEC-1: "simplificar" is underspecified

**Question for client:** Which of these does "simplificar la pantalla del catálogo de widgets" mean?
- Fewer columns by default
- Collapsed/grouped rows
- Different default sort
- Something else

**Owner:** <name / team that needs to answer>
**Blocks:** SPEC-1
**Status:** pending client response (asked 2026-04-17)

### GAP-2 — SPEC-3: missing asset

**Question for client:** Please provide the Acme Corp logo in a vector format (SVG or EPS) suitable for PDF embedding.

**Owner:** Acme Corp marketing
**Blocks:** SPEC-3
**Status:** pending (email sent 2026-04-17)

## Resolved

### GAP-0 — SPEC-4 — RESOLVED 2026-04-16

**Question:** Does "recálculo en tiempo real" mean on every edit, or on save?
**Answer:** On save. Client confirmed in call on 2026-04-16.
**Applied to inventory:** SPEC-4 interpretation updated; status moved to `pending`.
```

## When to add a gap

Add a gap whenever any of these is true for an inventory point:

- The acceptance criteria would let you build two different things and you can't tell which is right.
- The point depends on an asset, credential, data file, or mapping the client hasn't provided.
- The point conflicts with another point in the same document.
- The point references an external system whose behavior is undocumented.
- The point uses subjective language ("fácil", "rápido", "limpio") without a measurable target.

## How to present gaps to the user

After building the inventory, present the gap list to the user in one pass, as a set of concrete questions grouped by the SPEC-N they block. This gives the user one chance to either:

- Answer some questions immediately (they know the client's intent)
- Confirm others need to go to the client
- Mark some as "work around it, ask if it becomes a blocker"

When the user confirms a gap needs external input, the inventory row status becomes `gap-blocked` and a `Pending external input:` line is added to the corresponding review doc entry with:
- Who owns the answer
- What specifically is needed
- Date asked

This is the only source of truth for "why isn't SPEC-N done yet" that the user can point to in a client meeting.

## The "work around it" case

If a gap is real but not blocking (e.g. a missing logo asset for a PDF — you can stub it with a placeholder and swap in later), the inventory status stays `pending`, not `gap-blocked`, but the row gets an **Assumption** annotation:

```markdown
| SPEC-3 | ... | ... | backend | p.1 | pending — assumption: placeholder logo until GAP-2 resolves |
```

The review doc then calls this out explicitly in the per-point detail so the user doesn't miss the swap-in later.
