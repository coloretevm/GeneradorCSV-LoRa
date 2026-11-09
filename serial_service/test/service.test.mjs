import test from 'node:test';
import assert from 'node:assert/strict';
import { SerialService, deviceId, canonical, hash } from '../src/worker.mjs';

function state() {
  const data = new Map();
  return { blockConcurrencyWhile: fn => fn(), storage: {
    get: async key => structuredClone(data.get(key)),
    put: async (key, value) => data.set(key, structuredClone(value)),
    delete: async key => data.delete(key),
    list: async ({ prefix }) => new Map([...data].filter(([key]) => key.startsWith(prefix))),
  } };
}
async function identity() {
  const keys = await crypto.subtle.generateKey({ name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048,
    publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' }, true, ['sign', 'verify']);
  const exported = await crypto.subtle.exportKey('jwk', keys.publicKey);
  const jwk = { kty: exported.kty, n: exported.n, e: exported.e };
  return { keys, jwk, id: await deviceId(jwk) };
}
async function signed(who, method, path, data, extra = {}) {
  const body = data === undefined ? '' : JSON.stringify(data);
  const timestamp = String(Math.floor(Date.now() / 1000));
  const nonce = crypto.randomUUID().replaceAll('-', '');
  const req = new Request('https://test.workers.dev' + path, { method,
    ...(body ? { body } : {}) });
  const signature = Buffer.from(await crypto.subtle.sign('RSASSA-PKCS1-v1_5', who.keys.privateKey,
    new TextEncoder().encode(canonical(req, timestamp, nonce, await hash(body))))).toString('base64url');
  return new Request(req, { headers: { 'X-Device-ID': who.id, 'X-Device-Time': timestamp,
    'X-Device-Nonce': nonce, 'X-Device-Signature': signature, ...extra } });
}
const owner = await identity();
const guest = await identity();
function service() {
  return new SerialService(state(), { GITHUB_REPOSITORY: 'coloretevm/GeneradorCSV-LoRa', GITHUB_BRANCH: 'main',
    BOOTSTRAP_DEVICE: JSON.stringify({ id: owner.id, jwk: owner.jwk, label: 'owner' }) });
}

test('anonymous caller cannot read registry or list devices', async () => {
  const gate = service();
  for (const path of ['/v1/registry', '/v1/admin/devices'])
    assert.equal((await gate.fetch(new Request('https://test.workers.dev' + path))).status, 401);
});
test('large streamed bodies are rejected before authentication or JSON parsing', async () => {
  const gate = service();
  const result = await gate.fetch(new Request('https://test.workers.dev/v1/enroll',
    { method: 'POST', body: 'x'.repeat(32769) }));
  assert.equal(result.status, 413);
});
test('new device stays pending until the owner approves it', async () => {
  const gate = service();
  let result = await gate.fetch(await signed(guest, 'POST', '/v1/enroll', { jwk: guest.jwk, label: 'office' }));
  assert.equal((await result.json()).status, 'pending');
  assert.equal((await gate.fetch(await signed(guest, 'GET', '/v1/admin/devices'))).status, 403);
  result = await gate.fetch(await signed(owner, 'GET', '/v1/admin/devices'));
  assert.equal((await result.json()).devices[0].id, guest.id);
  assert.equal((await gate.fetch(await signed(owner, 'POST', '/v1/admin/devices', { id: guest.id, status: 'approved' }))).status, 200);
  result = await gate.fetch(await signed(guest, 'POST', '/v1/enroll', { jwk: guest.jwk, label: 'office' }));
  assert.equal((await result.json()).status, 'approved');
  assert.equal((await gate.fetch(await signed(guest, 'GET', '/v1/admin/devices'))).status, 403);
});
test('owner identity cannot be forged with another public key', async () => {
  const gate = service();
  const req = await signed(guest, 'GET', '/v1/admin/devices', undefined, { 'X-Device-ID': owner.id });
  assert.equal((await gate.fetch(req)).status, 401);
});
test('signed requests cannot be replayed', async () => {
  const gate = service();
  const req = await signed(owner, 'GET', '/v1/admin/devices');
  const copy = req.clone();
  assert.equal((await gate.fetch(req)).status, 200);
  assert.equal((await gate.fetch(copy)).status, 409);
});
test('signature binds the body and endpoint', async () => {
  const gate = service();
  const req = await signed(owner, 'POST', '/v1/admin/devices', { id: guest.id, status: 'approved' });
  assert.equal((await gate.fetch(new Request(req.url, { method: 'POST', headers: req.headers,
    body: JSON.stringify({ id: guest.id, status: 'revoked' }) }))).status, 401);
});
test('expired timestamps are rejected', async () => {
  const gate = service();
  const req = await signed(owner, 'GET', '/v1/admin/devices', undefined, { 'X-Device-Time': '1000000000' });
  assert.equal((await gate.fetch(req)).status, 401);
});
test('revoked devices cannot enroll again', async () => {
  const gate = service();
  await gate.fetch(await signed(guest, 'POST', '/v1/enroll', { jwk: guest.jwk, label: 'office' }));
  await gate.fetch(await signed(owner, 'POST', '/v1/admin/devices', { id: guest.id, status: 'revoked' }));
  assert.equal((await gate.fetch(await signed(guest, 'POST', '/v1/enroll', { jwk: guest.jwk, label: 'office' }))).status, 403);
});
test('unconfigured GitHub returns no secrets in errors', async () => {
  const gate = service();
  const result = await gate.fetch(await signed(owner, 'GET', '/v1/registry'));
  assert.deepEqual(await result.json(), { error: 'github_not_configured' });
});
test('only serial families and nonnegative integers can be written', async () => {
  const gate = service();
  const current = { _service_revision: 'old', families: {} };
  for (const incoming of [{ families: { Other: {} } }, { families: { RTU: { last_serial: -1 } } }]) {
    Object.defineProperty(current, '_documents', { value: [{ families: {} }, { families: {} }], configurable: true });
    await assert.rejects(() => gate.writeRegistry(current, incoming, 'office'));
  }
});
test('atomic commit contains only the two registry paths and an expected head', async () => {
  const gate = service();
  const family = { last_serial: 1, last_count: 1, last_range: '1-1', last_year: '2026' };
  const families = Object.fromEntries(['RTU', 'GW', 'I-TIC', 'TIC12', 'Istantaneo'].map(name => [name, { ...family }]));
  const current = { _service_revision: 'head', families };
  const desired = structuredClone(families);
  desired.RTU.last_serial = 2;
  desired.RTU.last_range = '2-2';
  Object.defineProperty(current, '_documents', { value: [{ families: { ...families } }, { families: { Istantaneo: family } }] });
  gate.github = async (path, options) => {
    assert.equal(path, '/graphql');
    const input = JSON.parse(options.body).variables.input;
    assert.equal(input.expectedHeadOid, 'head');
    assert.deepEqual(input.fileChanges.additions.map(file => file.path), ['serial_registry.json', 'serial_registry_istantaneo.json']);
    return { data: { createCommitOnBranch: { commit: { oid: 'new' } } } };
  };
  gate.readRegistry = async () => ({ ...current, families: desired });
  await gate.writeRegistry(current, { families: desired }, 'office');
});
