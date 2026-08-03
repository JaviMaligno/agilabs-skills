/**
 * Capture an MCP stdio server's capabilities by actually talking to it.
 *
 * Performs the handshake (initialize -> notifications/initialized) and then
 * calls tools/list, prompts/list and resources/list, writing a single JSON
 * object that can be dropped straight into a Smithery release payload.
 *
 * Methods the server does not implement are reported as absent rather than
 * failing the run — plenty of servers ship tools only.
 *
 * Usage:
 *   node capture_capabilities.mjs <entry.js> [-- ENV=value ...] > caps.json
 *
 * Example:
 *   node capture_capabilities.mjs ./dist/index.js -- API_TOKEN=dummy WORKSPACE=dummy
 *
 * Servers that validate credentials at startup will exit before answering.
 * Passing throwaway values for the required variables is enough: this only
 * reads static definitions, it never calls a tool.
 */
import { spawn } from 'node:child_process';
import process from 'node:process';

const argv = process.argv.slice(2);
const sepIndex = argv.indexOf('--');
const entry = argv[0];
const envPairs = sepIndex === -1 ? [] : argv.slice(sepIndex + 1);

if (!entry) {
  console.error('usage: capture_capabilities.mjs <entry.js> [-- ENV=value ...]');
  process.exit(2);
}

const env = { ...process.env };
for (const pair of envPairs) {
  const eq = pair.indexOf('=');
  if (eq > 0) env[pair.slice(0, eq)] = pair.slice(eq + 1);
}

const PROTOCOL_VERSION = '2025-06-18';
const REQUESTS = [
  { id: 2, method: 'tools/list', key: 'tools' },
  { id: 3, method: 'prompts/list', key: 'prompts' },
  { id: 4, method: 'resources/list', key: 'resources' },
];

const child = spawn(process.execPath, [entry], {
  env,
  stdio: ['pipe', 'pipe', 'pipe'],
});

const responses = new Map();
let stdoutBuffer = '';
let stderrText = '';

child.stderr.on('data', (chunk) => {
  stderrText += chunk.toString();
});

child.stdout.on('data', (chunk) => {
  stdoutBuffer += chunk.toString();
  const lines = stdoutBuffer.split('\n');
  stdoutBuffer = lines.pop() ?? '';
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    let message;
    try {
      message = JSON.parse(trimmed);
    } catch {
      // Anything non-JSON on stdout corrupts the MCP stream. Surface it: it is
      // a real defect in the server, usually a console.log that should be a
      // console.error.
      console.error(`[warn] non-JSON line on stdout: ${trimmed.slice(0, 120)}`);
      continue;
    }
    if (message.id !== undefined) responses.set(message.id, message);
  }
});

const send = (payload) => child.stdin.write(`${JSON.stringify(payload)}\n`);

const waitFor = (id, timeoutMs = 10_000) =>
  new Promise((resolve, reject) => {
    const startedAt = Date.now();
    const poll = () => {
      if (responses.has(id)) return resolve(responses.get(id));
      if (child.exitCode !== null) {
        return reject(
          new Error(
            `server exited with code ${child.exitCode} before answering id ${id}.` +
              (stderrText ? `\nstderr:\n${stderrText.trim()}` : ''),
          ),
        );
      }
      if (Date.now() - startedAt > timeoutMs) return reject(new Error(`timed out waiting for id ${id}`));
      setTimeout(poll, 50);
    };
    poll();
  });

try {
  send({
    jsonrpc: '2.0',
    id: 1,
    method: 'initialize',
    params: {
      protocolVersion: PROTOCOL_VERSION,
      capabilities: {},
      clientInfo: { name: 'capture-capabilities', version: '1.0.0' },
    },
  });

  const initResult = await waitFor(1);
  send({ jsonrpc: '2.0', method: 'notifications/initialized' });

  const out = {
    serverInfo: initResult.result?.serverInfo,
    negotiatedProtocolVersion: initResult.result?.protocolVersion,
  };

  for (const { id, method, key } of REQUESTS) {
    send({ jsonrpc: '2.0', id, method });
    try {
      const response = await waitFor(id, 8_000);
      if (response.error) {
        console.error(`[info] ${method} not supported: ${response.error.message}`);
        continue;
      }
      const list = response.result?.[key];
      if (Array.isArray(list) && list.length > 0) out[key] = list;
    } catch (error) {
      console.error(`[info] ${method} skipped: ${error.message}`);
    }
  }

  console.log(JSON.stringify(out, null, 2));
  console.error(
    `[ok] tools ${out.tools?.length ?? 0} | prompts ${out.prompts?.length ?? 0} | resources ${
      out.resources?.length ?? 0
    }`,
  );
} finally {
  child.stdin.end();
  child.kill();
}
