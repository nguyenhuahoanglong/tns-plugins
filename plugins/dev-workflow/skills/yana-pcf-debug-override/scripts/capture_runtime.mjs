#!/usr/bin/env node
/** Read-only CDP capture. Attach before reloading only a task-owned tab through browser tools. */
import fs from 'node:fs';
import crypto from 'node:crypto';

const options = {};
for (let i = 2; i < process.argv.length; i += 2) {
  if (!process.argv[i].startsWith('--') || !process.argv[i + 1]) throw Error('Expected --name value pairs');
  options[process.argv[i].slice(2)] = process.argv[i + 1];
}
const port = Number(options.port || 9222);
const duration = Number(options['duration-ms'] || 15000);
if (!Number.isInteger(port) || port < 1 || port > 65535) throw Error('Invalid loopback port');
if (!Number.isInteger(duration) || duration < 500 || duration > 180000) throw Error('Duration must be 500..180000 ms');
if (!options.receipt || !options.target || !options.output) {
  throw Error('Usage: node capture_runtime.mjs --receipt PATH --target CDP_TARGET_ID --output PATH [--port 9222] [--duration-ms 15000]');
}
const receipt = JSON.parse(fs.readFileSync(options.receipt, 'utf8').replace(/^\uFEFF/, ''));
const plan = receipt.plan;
if (!plan?.origin || !Array.isArray(plan.resources) || !receipt.applied_at) throw Error('A completed apply receipt is required');
const expected = new Map(plan.resources.map(resource => [resource.url, resource]));
if (expected.size !== plan.resources.length) throw Error('Duplicate resource URLs');
const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const target = targets.find(item => item.id === options.target);
if (!target || new URL(target.url).origin !== plan.origin) throw Error('Target missing or origin differs from receipt');
const endpoint = new URL(target.webSocketDebuggerUrl);
if (endpoint.protocol !== 'ws:' || !['127.0.0.1', 'localhost'].includes(endpoint.hostname)
    || Number(endpoint.port) !== port || endpoint.username || endpoint.password) {
  throw Error('CDP endpoint must be the selected loopback port');
}
const socket = new WebSocket(endpoint);
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
let sequence = 0;
const pending = new Map();
const requests = new Map();
const resources = new Map();
const jobs = new Set();
const errors = [];
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const call = (method, params = {}) => new Promise((resolve, reject) => {
  const id = ++sequence;
  const timeout = setTimeout(() => { pending.delete(id); reject(Error(`${method} timed out`)); }, 5000);
  pending.set(id, { resolve, reject, timeout });
  socket.send(JSON.stringify({ id, method, params }));
});
const recordJob = promise => {
  jobs.add(promise);
  promise.catch(error => errors.push(String(error.message))).finally(() => jobs.delete(promise));
};
const record = (url, bytes, method, details = {}, capturedAt = new Date().toISOString()) => {
  resources.set(url, {
    url, sha256: hash(bytes), method, ...details,
    captured_at: capturedAt,
    captured_after_apply: Date.parse(capturedAt) >= Date.parse(receipt.applied_at),
  });
};
socket.onmessage = event => {
  const message = JSON.parse(event.data);
  if (pending.has(message.id)) {
    const waiter = pending.get(message.id);
    pending.delete(message.id);
    clearTimeout(waiter.timeout);
    if (message.error) waiter.reject(Error(message.error.message));
    else waiter.resolve(message.result);
    return;
  }
  const data = message.params;
  if (message.method === 'Debugger.scriptParsed' && expected.has(data.url)) {
    recordJob(call('Debugger.getScriptSource', { scriptId: data.scriptId }).then(result => {
      record(data.url, Buffer.from(result.scriptSource, 'utf8'), 'Debugger.getScriptSource', { script_id: data.scriptId });
    }));
  } else if (message.method === 'Network.requestWillBeSent') {
    requests.delete(data.requestId); // Redirects may reuse IDs. Only the current exact request counts.
    if (expected.has(data.request.url)) {
      requests.set(data.requestId, { url: data.request.url, type: data.type, started: new Date().toISOString() });
    }
  } else if (message.method === 'Network.responseReceived') {
    const request = requests.get(data.requestId);
    if (request) {
      request.type = data.type;
      request.status = data.response.status;
      request.url = data.response.url;
    }
  } else if (message.method === 'Network.loadingFinished') {
    const request = requests.get(data.requestId);
    if (!request || !expected.has(request.url) || !Number.isFinite(request.status) || request.status < 200 || request.status >= 300) return;
    // Fetch/XHR is a later request, not proof of a loaded stylesheet/script/image.
    if (!['Stylesheet', 'Image', 'Font', 'Media', 'Other'].includes(request.type)) return;
    recordJob(call('Network.getResponseBody', { requestId: data.requestId }).then(result => {
      const bytes = Buffer.from(result.body, result.base64Encoded ? 'base64' : 'utf8');
      record(request.url, bytes, 'Network.getResponseBody', {
        request_id: data.requestId, resource_type: request.type, loaded_request: true,
      }, request.started);
    }));
  }
};
try {
  await call('Network.enable');
  await call('Debugger.enable');
  console.log(JSON.stringify({ status: 'CAPTURING', target: options.target, origin: plan.origin,
    instruction: 'No page is reloaded by this helper. If needed, reload only a task-owned tab and open its relevant grid.' }));
  await new Promise(resolve => setTimeout(resolve, duration));
  await Promise.allSettled([...jobs]);
  const observed = [...resources.values()];
  const result = {
    schema_version: 2, origin: plan.origin, plan_id: plan.plan_id,
    target_id: options.target, captured_at: new Date().toISOString(), resources: observed,
    missing_urls: [...expected.keys()].filter(url => !resources.has(url)), errors,
    limits: ['Capture is evidence, not a parity verdict. Run the Python verify mode.',
      'CSSOM text and later fetches are intentionally not accepted as loaded response bytes.'],
  };
  if (options['host-evidence']) {
    const host = JSON.parse(fs.readFileSync(options['host-evidence'], 'utf8').replace(/^\uFEFF/, ''));
    if (host.origin !== plan.origin) throw Error('Host evidence origin differs from receipt');
    result.host_resources = host.host_resources;
  }
  fs.writeFileSync(options.output, `${JSON.stringify(result, null, 2)}\n`);
  console.log(JSON.stringify({ output: options.output, observed: observed.length, missing: result.missing_urls.length, errors: errors.length }));
  if (errors.length || result.missing_urls.length) process.exitCode = 2;
} finally {
  for (const waiter of pending.values()) clearTimeout(waiter.timeout);
  socket.close();
}
