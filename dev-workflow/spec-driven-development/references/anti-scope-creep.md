# Anti-Scope-Creep Checklist

Use this checklist every time the urge to "just also..." strikes during implementation. Scope creep is usually well-intentioned — you spot something suboptimal while you're in the file, or a natural adjacent improvement presents itself. The cost is that the PR grows, the client has to review things they never asked for, and the spec-traceability story falls apart.

## The decision

Before making a change that isn't traceable to a specific `SPEC-N`, answer these in order:

### 1. Does this change serve any `SPEC-N` currently in scope?

- **Yes** → do it. Cite the SPEC-N in the commit.
- **No** → continue to (2).

### 2. Is this change a pure refactor *required* to land a `SPEC-N` safely?

(For example, extracting a function that both a new and existing code path need to call, or adding a test harness hook that the new test needs.)

- **Yes** → do it, but in a separate commit tagged `refactor(scope): <description> (enables SPEC-N)`. Keep it minimal — only what SPEC-N needs.
- **No** → continue to (3).

### 3. Is this change a bug fix for something the user would be surprised to learn is broken?

- **Yes** → stop. Tell the user. A silent bug fix inside a spec-driven PR is still scope creep from the client's perspective. The user may want it landed as a separate PR, bundled, or deferred. That decision is theirs.
- **No** → continue to (4).

### 4. Everything else: defer.

- Add the idea to `docs/spec-review/<feature>-deferred.md` with:
  - What you noticed
  - Why you think it's worth doing
  - Where it would live (file paths, rough approach)
- Do not change it in this PR.

## The deferred file

```markdown
# Deferred — <feature name>

## bulk-archive

**Noticed while:** implementing SPEC-2b (status filter).

**Idea:** Add a bulk-archive action to the widget catalog so users can archive multiple rows at once instead of row-by-row.

**Why worth doing:** Users with 50+ widgets per client will appreciate it; status filter makes the archived set selectable now.

**Where it would live:** `apps/catalog/src/pages/CatalogList.tsx` — add row-selection state and a bulk-action toolbar, similar to the pattern in `apps/orders/src/pages/OrderList.tsx`.

**Not doing because:** Not in the current spec. Would need a separate client request.

---

## catalog-store-refactor

**Noticed while:** implementing SPEC-1 (column density).

**Idea:** Extract the hooks-soup in `CatalogList.tsx` into a dedicated zustand store.

**Why worth doing:** The component is ~400 lines and has 7 interdependent hooks; hard to test in isolation.

**Where it would live:** New `apps/catalog/src/stores/catalogListStore.ts`.

**Not doing because:** Pure code-quality cleanup; not client-visible; no immediate spec coverage needs it.
```

## Why this discipline matters

Two reasons. The first is practical: every change outside the spec is a change the user (and possibly the client) has to mentally hold against the spec to see if it's OK. More stuff = worse review.

The second is trust: clients (and product owners) learn over time whether "I asked for X" produces "X, and a bunch of other stuff I now have to evaluate" or produces "exactly X". The latter is the relationship you want.

The deferred file isn't a graveyard — it's a catcher. Things that belong there often come back as their own spec later, which is the healthy shape.

## When the user overrides

If the user explicitly says "yeah, while you're in there, also do Y" — that's fine, honor it. But add Y to the inventory as an `out-of-spec-addition` row so the review doc still shows everything that was done, and the client-facing story is clean ("these are the spec points; the user additionally authorized these").
