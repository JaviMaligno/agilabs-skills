# Gap 16 — Cross-boundary partner contacts in IR runbook

[Preamble must be prepended at invocation.]

## Objective

Extend the controls document's cross-boundary section with the partner-incident contact, SLA, and central-register reference per partner. Stack-agnostic — deliverable is documentation.

## "Done" criteria (stack-agnostic)

The repo's Responsible-AI controls document gains a table with columns:

| Partner | Role | Data flowing out | Data flowing in | Incident contact (channel) | SLA / response window | Register ref |

The `Register ref` column uses keys `register/partners/<id>` that map to the central AI register. Where a register row does not yet exist, mark SLA/contact `TBD` — the gap is visible.

Add the operational note:

> During an incident the on-call resolves the partner contact by looking up the `Register ref` in the central AI register, not by relying on this table. This table is a *cache* — the register is the source of truth. Reconciliation cadence: quarterly, alongside the threat-model review.

Update `docs/RESPONSIBLE_AI_COMPLIANCE.md` item 16 to ✅ with the "Compliance to confirm each `register/partners/<id>` row exists" follow-up.

## Discovery (stack-agnostic)

Identify external partners by inspecting outbound HTTP clients and known SaaS clients in the codebase:

```bash
# Outbound HTTP — grep typical client invocations per stack
grep -rEn "axios\.|fetch\(|HttpClient|Guzzle|HTTP::|requests\.|http\.NewRequest|net/http" {{SOURCE_DIR}} 2>/dev/null | head -20

# SaaS service identifiers in config
grep -rEn "API_KEY|_URL|baseURL|base_url|BASE_URL" .env* config/ 2>/dev/null | head -30
```

Cross-reference any existing partner table; list only partners the code actually talks to. Examples to look for: model providers (OpenAI / Anthropic / Azure OpenAI / Bedrock), search providers (Tavily / Bing / SerpApi), registries (NZBN / ABR / Companies House), document/blob storage, payment processors, identity providers.

## Out of scope

- Creating entries in the central register.
- Negotiating SLAs.
