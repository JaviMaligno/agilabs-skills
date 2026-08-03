---
name: smithery-publish
description: Use when publishing or updating an MCP server on Smithery — packaging a stdio server as an .mcpb bundle, getting its tools/prompts/resources to actually show on the listing, and filling the listing metadata the CLI silently ignores. Trigger on "publish to Smithery", "register my MCP", "my Smithery listing shows no capabilities", "smithery mcp publish", or "no description on my server page".
---

# Publishing an MCP server to Smithery

## Overview

Getting a listing that is actually useful takes three separate things, and only the
first is what the CLI does:

1. **The release** — a `.mcpb` bundle, published through the REST API (not the CLI, for
   the reason in [The inputSchema conflict](#the-inputschema-conflict)).
2. **The listing metadata** — description, homepage, repository, icon. **None of it
   comes from the bundle manifest.** It is typed into the web UI, or the page reads
   "No description".
3. **Visibility** — new servers are created `Unlisted` and never appear in search until
   you uncheck it.

Skip any one and the listing looks broken or invisible. On one real server the quality
score moved 13 → 37 (metadata) → 57 (capabilities) → 65 (listed).

**The repo-based route is dead.** A `smithery.yaml` with `startCommand: type: stdio` and
a `commandFunction` no longer deploys anything. Today there are three release types:
hosted (JS module), external (URL), and stdio (`.mcpb` bundle). A local-run server is
the third.

## When to use

- First-time registration of an MCP server on Smithery
- Shipping a new version of an already-listed server
- A listing that says "No capabilities found" or "No description"
- A server that publishes fine but never appears in search

## Workflow

### 1. Build the bundle

The bundle does not have to live in the server's repo. Install the published package
into a scratch directory and point the manifest at it:

```bash
mkdir bundle && cd bundle
npm init -y && npm install <your-package> --omit=dev
# write manifest.json (see below), then:
rm package.json package-lock.json
npx -y @anthropic-ai/mcpb validate manifest.json
npx -y @anthropic-ai/mcpb pack . ../server.mcpb
```

A minimal Node manifest:

```json
{
  "manifest_version": "0.3",
  "name": "your-package",
  "display_name": "Your Server",
  "version": "1.0.0",
  "description": "One line.",
  "author": { "name": "You", "email": "you@example.com" },
  "server": {
    "type": "node",
    "entry_point": "node_modules/your-package/dist/index.js",
    "mcp_config": {
      "command": "node",
      "args": ["${__dirname}/node_modules/your-package/dist/index.js"],
      "env": { "API_TOKEN": "${user_config.API_TOKEN}" }
    }
  },
  "user_config": {
    "API_TOKEN": {
      "type": "string",
      "title": "API token",
      "description": "Where to get it",
      "sensitive": true,
      "required": true
    }
  }
}
```

`user_config` becomes the config form users fill in. Mark secrets `sensitive` and give
every field a real `description` — it is what users see when connecting.

### 2. Capture the capabilities

Do not hand-write the tool list. Ask the server:

```bash
node scripts/capture_capabilities.mjs \
  bundle/node_modules/your-package/dist/index.js \
  -- API_TOKEN=dummy > caps.json
```

Throwaway credentials are fine — this reads static definitions and never calls a tool.
Many servers validate credentials at startup and exit before answering, which is why the
dummy values are needed at all.

The script also warns about **non-JSON output on stdout**. That is not cosmetic: anything
written to stdout after the stdio transport connects corrupts the JSON-RPC stream. If it
fires, fix the server (`console.log` → `console.error`) before shipping.

### 3. Publish

```bash
node scripts/publish_release.mjs your-namespace/your-server ./server.mcpb ./caps.json
```

Expect `HTTP 202` and `"status":"SUCCESS"`.

### 4. Fill the listing metadata — web UI, unavoidable

Settings → General on `smithery.ai/servers/<namespace>/<name>/settings`:

| Field | Notes |
|---|---|
| Display Name | The manifest's `display_name` does **not** populate this |
| Description | Markdown. The manifest's `description` does **not** populate this either |
| Homepage | Also decides the fallback icon (the favicon of that host) |
| GitHub Repository | Shown on the page; does not affect deployment |
| Server Icon | Optional upload, overrides the favicon |

### 5. Uncheck "Unlisted", then Save

Until you do, the server is reachable by direct link but absent from
`smithery mcp search`. Search indexing lags after the flip — not seeing it immediately is
normal.

## The inputSchema conflict

**Why `smithery mcp publish` is not used here.**

The CLI derives the release payload from the manifest inside the bundle, forwarding
`manifest.tools` verbatim into a `serverCard`. Smithery's API validates each entry as a
full MCP Tool, so every tool needs an `inputSchema`. But the MCPB manifest schema — both
v0.3 and v0.4 — declares tools as:

```json
{ "type": "object",
  "properties": { "name": {"type":"string"}, "description": {"type":"string"} },
  "required": ["name"],
  "additionalProperties": false }
```

So a manifest Smithery accepts cannot be built by `mcpb pack` and fails `mcpb validate`,
and a manifest MCPB accepts is rejected by Smithery with one
`Invalid input: expected object, received undefined` per tool. Omitting `tools` entirely
publishes cleanly and yields "No capabilities found".

Patching `manifest.json` inside the packed `.mcpb` (it is a zip) does make the listing
work, but it ships a bundle that no longer passes `mcpb validate` — a strict MCPB
consumer loading the file directly may reject it.

The REST API takes `payload` and `bundle` as **separate** multipart fields, so both
constraints can hold at once:

```
PUT https://api.smithery.ai/servers/{namespace%2Fname}/releases
Authorization: Bearer <apiKey>
multipart/form-data: payload=<JSON>, bundle=<file.mcpb>
```

`publish_release.mjs` builds that payload — reproducing the CLI's own runtime detection
and `user_config` → `configSchema` conversion — and sends the untouched, spec-valid
bundle beside it.

Verify what users actually receive:

```bash
curl -H "Authorization: Bearer $SMITHERY_API_KEY" \
  "https://api.smithery.ai/servers/your-namespace%2Fyour-server/download" -o dl.mcpb
npx -y @anthropic-ai/mcpb unpack dl.mcpb ./dl && npx -y @anthropic-ai/mcpb validate ./dl/manifest.json
```

## Gotchas

- **Metadata is not in the bundle.** The single most common surprise. A perfect manifest
  still produces "No description".
- **Unlisted by default.** A successful publish that is nowhere in search is working as
  designed.
- **`mcpName` in package.json is unrelated** to the Smithery qualified name. It is the
  MCP Registry identity (`io.github.owner/name`).
- **Verification needs a domain you control.** The "Verified" badge wants a TXT record on
  the *exact* homepage host, plus score > 80, a link back to Smithery, and a paid plan.
  A `github.com` homepage can never satisfy the TXT check — point Homepage at your own
  domain if the badge matters.
- **Publishing does not need the package on npm.** The bundle carries its dependencies,
  so it can be built from a local `npm pack` tarball. Just don't claim npm availability
  in the description until the package is really there.
- **Scoped npm names are a username or an org.** `@yourgithubhandle/...` fails with
  `404 Scope not found` unless that scope exists; the user scope is your npm username,
  which may differ from your GitHub handle.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/capture_capabilities.mjs` | Handshakes with a stdio server and dumps its tools, prompts and resources as JSON. Warns on stdout stream corruption. |
| `scripts/publish_release.mjs` | Publishes a stdio release via the REST API, keeping the `.mcpb` spec-valid. Reads `SMITHERY_API_KEY` or the `smithery auth login` store. |
