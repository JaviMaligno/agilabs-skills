/**
 * Publish a Smithery stdio release without corrupting the .mcpb bundle.
 *
 * `smithery mcp publish` derives the release payload from the manifest inside
 * the bundle. Its API validates `serverCard.tools` as full MCP Tool objects, so
 * every tool needs an `inputSchema`; the MCPB manifest schema (v0.3 and v0.4)
 * declares tools as `{name, description}` with `additionalProperties: false`.
 * A manifest that satisfies Smithery therefore cannot be built by `mcpb pack`
 * and fails `mcpb validate` — and one that satisfies MCPB gets rejected by
 * Smithery with one "expected object, received undefined" per tool.
 *
 * The REST API takes `payload` and `bundle` as separate multipart fields, which
 * dissolves the conflict: ship a spec-valid bundle, send the full capability
 * list alongside it.
 *
 * Usage:
 *   node publish_release.mjs <namespace/name> <bundle.mcpb> <capabilities.json>
 *
 * <capabilities.json> is the output of capture_capabilities.mjs. The bundle's
 * own manifest supplies identity, runtime and config schema.
 *
 * Auth: SMITHERY_API_KEY, or the key stored by `smithery auth login`.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import zlib from 'node:zlib';

const [qualifiedName, bundlePath, capabilitiesPath] = process.argv.slice(2);
if (!qualifiedName || !bundlePath || !capabilitiesPath) {
  console.error('usage: publish_release.mjs <namespace/name> <bundle.mcpb> <capabilities.json>');
  process.exit(2);
}

const API_BASE = process.env.SMITHERY_API_BASE ?? 'https://api.smithery.ai';

/** Where `smithery auth login` stores its settings, per platform. */
function settingsCandidates() {
  const home = os.homedir();
  return [
    process.env.APPDATA && path.join(process.env.APPDATA, 'smithery', 'settings.json'),
    path.join(home, 'AppData', 'Roaming', 'smithery', 'settings.json'),
    path.join(home, 'Library', 'Application Support', 'smithery', 'settings.json'),
    process.env.XDG_CONFIG_HOME && path.join(process.env.XDG_CONFIG_HOME, 'smithery', 'settings.json'),
    path.join(home, '.config', 'smithery', 'settings.json'),
  ].filter(Boolean);
}

function resolveApiKey() {
  if (process.env.SMITHERY_API_KEY) return process.env.SMITHERY_API_KEY;
  for (const candidate of settingsCandidates()) {
    if (!fs.existsSync(candidate)) continue;
    const { apiKey } = JSON.parse(fs.readFileSync(candidate, 'utf8'));
    if (apiKey) return apiKey;
  }
  throw new Error('No API key. Set SMITHERY_API_KEY or run "smithery auth login".');
}

/**
 * Read one entry out of a zip. A .mcpb is a zip, and shelling out to the mcpb
 * CLI is not portable here: Node >= 20 refuses to spawnSync a `.cmd` shim
 * without `shell: true`, and `shell: true` concatenates arguments instead of
 * escaping them. Twenty lines of zip parsing avoids both problems and the
 * dependency.
 */
function readZipEntry(zipPath, entryName) {
  const buf = fs.readFileSync(zipPath);

  // End of Central Directory: signature, then the comment (max 64KB) behind it.
  let eocd = -1;
  for (let i = buf.length - 22; i >= 0 && i >= buf.length - 22 - 0xffff; i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) {
      eocd = i;
      break;
    }
  }
  if (eocd === -1) throw new Error(`${zipPath} is not a zip archive`);

  const entryCount = buf.readUInt16LE(eocd + 10);
  let pointer = buf.readUInt32LE(eocd + 16);

  for (let i = 0; i < entryCount; i++) {
    if (buf.readUInt32LE(pointer) !== 0x02014b50) throw new Error('Corrupt central directory');
    const nameLength = buf.readUInt16LE(pointer + 28);
    const extraLength = buf.readUInt16LE(pointer + 30);
    const commentLength = buf.readUInt16LE(pointer + 32);
    const name = buf.toString('utf8', pointer + 46, pointer + 46 + nameLength);
    const localOffset = buf.readUInt32LE(pointer + 42);

    if (name === entryName) {
      const method = buf.readUInt16LE(localOffset + 8);
      const compressedSize = buf.readUInt32LE(pointer + 20);
      const localNameLength = buf.readUInt16LE(localOffset + 26);
      const localExtraLength = buf.readUInt16LE(localOffset + 28);
      const start = localOffset + 30 + localNameLength + localExtraLength;
      const data = buf.subarray(start, start + compressedSize);
      if (method === 0) return data;
      if (method === 8) return zlib.inflateRawSync(data);
      throw new Error(`Unsupported zip compression method ${method}`);
    }

    pointer += 46 + nameLength + extraLength + commentLength;
  }
  throw new Error(`${entryName} not found in ${zipPath}`);
}

function readBundleManifest(bundle) {
  return JSON.parse(readZipEntry(bundle, 'manifest.json').toString('utf8'));
}

/** Mirrors the Smithery CLI's runtime detection. */
function detectRuntime(manifest) {
  if (path.basename(manifest.server?.mcp_config?.command ?? '') === 'bun') return 'bun';
  if (manifest.server?.type === 'python') return 'python';
  if (manifest.server?.type === 'node') return 'node';
  if (manifest.server?.type === 'binary') return 'binary';
  throw new Error('Could not determine bundle runtime from manifest');
}

/**
 * Mirrors the Smithery CLI's user_config -> JSON Schema conversion, dotted keys
 * included. Note `sensitive` is not carried over — the CLI drops it too.
 */
function toConfigSchema(userConfig) {
  const root = { type: 'object', properties: {}, required: [] };
  const topLevelRequired = [];

  for (const [key, option] of Object.entries(userConfig)) {
    const segments = key.split('.');
    if (segments.length === 0) continue;

    let node = root;
    for (let i = 0; i < segments.length - 1; i++) {
      const segment = segments[i];
      node.properties ??= {};
      node.properties[segment] ??= { type: 'object', properties: {} };
      node = node.properties[segment];
    }

    const leaf = segments.at(-1);
    node.properties ??= {};
    const type = option.type === 'directory' || option.type === 'file' ? 'string' : option.type;
    const annotations = {
      ...(option.title ? { title: option.title } : {}),
      ...(option.description ? { description: option.description } : {}),
      ...(option.default !== undefined ? { default: option.default } : {}),
    };
    node.properties[leaf] = option.multiple
      ? { type: 'array', items: { type }, ...annotations }
      : { type, ...annotations };

    if (!option.required) continue;
    if (segments.length === 1) {
      topLevelRequired.push(leaf);
      continue;
    }
    root.required ??= [];
    if (!root.required.includes(segments[0])) root.required.push(segments[0]);
    let parent = root.properties[segments[0]];
    for (let i = 1; i < segments.length - 1; i++) parent = parent.properties[segments[i]];
    parent.required ??= [];
    if (!parent.required.includes(leaf)) parent.required.push(leaf);
  }

  if (topLevelRequired.length > 0) root.required = topLevelRequired;
  return root;
}

const manifest = readBundleManifest(bundlePath);
if (!manifest.name || !manifest.version) {
  throw new Error('Bundle manifest must include name and version');
}
const capabilities = JSON.parse(fs.readFileSync(capabilitiesPath, 'utf8'));

const configSchema =
  manifest.user_config && Object.keys(manifest.user_config).length > 0
    ? toConfigSchema(manifest.user_config)
    : undefined;

const payload = {
  type: 'stdio',
  runtime: detectRuntime(manifest),
  serverCard: {
    serverInfo: { name: manifest.name, version: manifest.version },
    ...(capabilities.tools ? { tools: capabilities.tools } : {}),
    ...(capabilities.prompts ? { prompts: capabilities.prompts } : {}),
    ...(capabilities.resources ? { resources: capabilities.resources } : {}),
  },
  ...(configSchema ? { configSchema } : {}),
};

const form = new FormData();
form.append('payload', JSON.stringify(payload));
form.append(
  'bundle',
  new Blob([fs.readFileSync(bundlePath)], { type: 'application/octet-stream' }),
  path.basename(bundlePath),
);

const response = await fetch(`${API_BASE}/servers/${encodeURIComponent(qualifiedName)}/releases`, {
  method: 'PUT',
  headers: { Authorization: `Bearer ${resolveApiKey()}` },
  body: form,
});

const body = await response.text();
console.log(
  `${qualifiedName}: HTTP ${response.status} | tools ${capabilities.tools?.length ?? 0} | prompts ${
    capabilities.prompts?.length ?? 0
  } | resources ${capabilities.resources?.length ?? 0}`,
);
console.log(body.slice(0, 800));
if (!response.ok) process.exit(1);
