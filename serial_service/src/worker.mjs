const FAMILIES = ['RTU', 'GW', 'I-TIC', 'TIC12', 'Istantaneo'];
const FILES = ['serial_registry.json', 'serial_registry_istantaneo.json'];
const encoder = new TextEncoder();
const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
});
class ServiceError extends Error {
  constructor(code, status = 400) { super(code); this.status = status; }
}
function requireValue(condition, code, status = 400) {
  if (!condition) throw new ServiceError(code, status);
}
export function decode64(value) {
  return Uint8Array.from(atob(value.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0));
}
export async function hash(value) {
  const bytes = typeof value === 'string' ? encoder.encode(value) : value;
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))]
    .map(n => n.toString(16).padStart(2, '0')).join('');
}
export async function deviceId(jwk) {
  requireValue(jwk && jwk.kty === 'RSA' && /^[A-Za-z0-9_-]{342}$/.test(jwk.n)
    && jwk.e === 'AQAB' && Object.keys(jwk).every(k => ['kty', 'n', 'e'].includes(k)), 'invalid_device_key');
  return hash(jwk.n + '.' + jwk.e);
}
export function canonical(request, timestamp, nonce, digest) {
  const url = new URL(request.url);
  return [url.origin, request.method, url.pathname, timestamp, nonce, digest].join('\n');
}
export default {
  async fetch(request, env) {
    if (new URL(request.url).pathname === '/health' && request.method === 'GET') {
      return json({ service: 'tecnidro-serial-service', version: 1 });
    }
    return env.SERVICE.get(env.SERVICE.idFromName('registry')).fetch(request);
  },
};

export class SerialService {
  constructor(state, env) { this.state = state; this.env = env; }
  async fetch(request) {
    return this.state.blockConcurrencyWhile(async () => {
      try { return await this.dispatch(request); }
      catch (error) {
        return json({ error: error instanceof ServiceError ? error.message : 'service_error' }, error.status || 503);
      }
    });
  }
  bootstrap() {
    try { return JSON.parse(this.env.BOOTSTRAP_DEVICE || '{}'); }
    catch { return {}; }
  }
  async authenticate(request, body, candidate = null) {
    const id = request.headers.get('X-Device-ID') || '';
    const timestamp = request.headers.get('X-Device-Time') || '';
    const nonce = request.headers.get('X-Device-Nonce') || '';
    const signature = request.headers.get('X-Device-Signature') || '';
    requireValue(/^[a-f0-9]{64}$/.test(id) && /^\d{10}$/.test(timestamp)
      && /^[a-f0-9]{32}$/.test(nonce) && /^[A-Za-z0-9_-]{342}$/.test(signature), 'authentication_required', 401);
    requireValue(Math.abs(Date.now() / 1000 - Number(timestamp)) <= 300, 'clock_out_of_sync', 401);
    const bootstrap = this.bootstrap();
    const admin = bootstrap.id === id;
    const registered = admin ? bootstrap : await this.state.storage.get('device:' + id);
    const device = candidate || registered;
    requireValue(device && await deviceId(device.jwk) === id, 'device_not_approved', 403);
    requireValue(candidate || admin || registered.status === 'approved', 'device_not_approved', 403);
    const key = await crypto.subtle.importKey('jwk', device.jwk,
      { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['verify']);
    const valid = await crypto.subtle.verify('RSASSA-PKCS1-v1_5', key, decode64(signature),
      encoder.encode(canonical(request, timestamp, nonce, await hash(body))));
    requireValue(valid, 'invalid_signature', 401);
    const nonceKey = 'nonce:' + id + ':' + nonce;
    requireValue(!await this.state.storage.get(nonceKey), 'request_replayed', 409);
    await this.state.storage.put(nonceKey, Date.now());
    const nonces = await this.state.storage.list({ prefix: 'nonce:' });
    for (const [name, created] of nonces) if (Date.now() - created > 600000) await this.state.storage.delete(name);
    return { ...device, id, admin };
  }
  async dispatch(request) {
    const url = new URL(request.url);
    requireValue(url.protocol === 'https:', 'https_required');
    requireValue(!url.search, 'query_not_supported');
    requireValue(Number(request.headers.get('Content-Length') || 0) <= 32768, 'request_too_large', 413);
    const chunks = [];
    let length = 0;
    if (request.body) {
      const reader = request.body.getReader();
      try {
        while (true) {
          const next = await reader.read();
          if (next.done) break;
          length += next.value.length;
          if (length > 32768) {
            await reader.cancel();
            throw new ServiceError('request_too_large', 413);
          }
          chunks.push(next.value);
        }
      } finally { reader.releaseLock(); }
    }
    const bytes = new Uint8Array(length);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
    let data = {};
    if (bytes.length) {
      try { data = JSON.parse(new TextDecoder().decode(bytes)); }
      catch { throw new ServiceError('invalid_json'); }
    }
    requireValue(data && typeof data === 'object' && !Array.isArray(data), 'invalid_json');
    if (url.pathname === '/v1/enroll' && request.method === 'POST') {
      const id = await deviceId(data.jwk);
      const label = String(data.label || '').trim();
      requireValue(label.length > 0 && label.length <= 80 && !/[\x00-\x1f]/.test(label), 'invalid_device_label');
      const previous = await this.state.storage.get('device:' + id);
      requireValue(previous?.status !== 'revoked', 'device_revoked', 403);
      const stored = await this.state.storage.list({ prefix: 'device:' });
      const bootstrap = this.bootstrap().id === id;
      requireValue(bootstrap || previous || stored.size < 64, 'enrollment_limit', 429);
      if (!bootstrap) {
        const minute = Math.floor(Date.now() / 60000);
        const rate = await this.state.storage.get('enrollment-rate') || { minute, count: 0 };
        if (rate.minute !== minute) { rate.minute = minute; rate.count = 0; }
        requireValue(rate.count < 20, 'enrollment_limit', 429);
        rate.count++;
        await this.state.storage.put('enrollment-rate', rate);
      }
      const device = await this.authenticate(request, bytes, { id, jwk: data.jwk, label });
      if (device.admin || previous?.status === 'approved') return json({ id, status: 'approved', admin: device.admin });
      if (!previous) await this.state.storage.put('device:' + id,
        { id, jwk: data.jwk, label, status: 'pending', created_at: new Date().toISOString() });
      return json({ id, status: 'pending', admin: false });
    }
    const device = await this.authenticate(request, bytes);
    if (url.pathname === '/v1/admin/devices' && request.method === 'GET') {
      requireValue(device.admin, 'administrator_required', 403);
      const stored = await this.state.storage.list({ prefix: 'device:' });
      return json({ devices: [...stored.values()].map(({ id, label, status, created_at }) => ({ id, label, status, created_at })) });
    }
    if (url.pathname === '/v1/admin/devices' && request.method === 'POST') {
      requireValue(device.admin, 'administrator_required', 403);
      requireValue(/^[a-f0-9]{64}$/.test(data.id) && ['approved', 'revoked'].includes(data.status), 'invalid_device');
      const target = await this.state.storage.get('device:' + data.id);
      requireValue(target, 'device_not_found', 404);
      target.status = data.status;
      await this.state.storage.put('device:' + data.id, target);
      return json({ id: data.id, status: target.status });
    }
    if (url.pathname === '/v1/registry' && request.method === 'GET') return json(await this.readRegistry());
    if (url.pathname === '/v1/registry' && request.method === 'PUT') {
      requireValue(/^[a-f0-9-]{36}$/.test(data.operation_id || ''), 'invalid_operation');
      const operationKey = 'operation:' + device.id + ':' + data.operation_id;
      const digest = await hash(bytes);
      const previous = await this.state.storage.get(operationKey);
      if (previous) {
        requireValue(previous.digest === digest, 'operation_conflict', 409);
        return json(previous.result);
      }
      const current = await this.readRegistry();
      requireValue(data.revision === current._service_revision, 'registry_changed', 409);
      const result = await this.writeRegistry(current, data.registry, device.label);
      await this.state.storage.put(operationKey, { digest, result, created: Date.now() });
      const operations = await this.state.storage.list({ prefix: 'operation:' });
      for (const [name, value] of operations) if (Date.now() - value.created > 86400000) await this.state.storage.delete(name);
      return json(result);
    }
    throw new ServiceError('not_found', 404);
  }
  async github(path, options = {}) {
    requireValue(this.env.GITHUB_TOKEN, 'github_not_configured', 503);
    const response = await fetch('https://api.github.com' + path, {
      ...options, signal: AbortSignal.timeout(8000),
      headers: { 'Authorization': 'Bearer ' + this.env.GITHUB_TOKEN,
        'User-Agent': 'Tecnidro-Serial-Service', 'Accept': 'application/vnd.github+json',
        'Cache-Control': 'no-cache', ...options.headers },
    });
    if (response.status === 404 && options.optional) return null;
    requireValue(response.ok, response.status === 401 || response.status === 403
      ? 'github_credentials_rejected' : 'github_unavailable', 503);
    return response.json();
  }
  async readRegistry() {
    const repository = this.env.GITHUB_REPOSITORY;
    const branch = this.env.GITHUB_BRANCH;
    requireValue(repository === 'coloretevm/GeneradorCSV-LoRa' && branch === 'main', 'invalid_repository', 503);
    const ref = await this.github('/repos/' + repository + '/git/ref/heads/' + branch);
    const revision = ref.object.sha;
    const documents = await Promise.all(FILES.map(async path => {
      const result = await this.github('/repos/' + repository + '/contents/' + path + '?ref=' + revision,
        { optional: path === FILES[1] });
      return result ? JSON.parse(new TextDecoder().decode(decode64(result.content.replace(/\s/g, '')))) : { families: {} };
    }));
    const combined = structuredClone(documents[0]);
    combined.families = { ...combined.families, Istantaneo: documents[1].families?.Istantaneo || { last_serial: 0 } };
    combined._service_revision = revision;
    // Private snapshot is used only to preserve unknown legacy fields during a commit.
    Object.defineProperty(combined, '_documents', { value: documents, enumerable: false });
    return combined;
  }
  async writeRegistry(current, incoming, label) {
    requireValue(incoming && typeof incoming.families === 'object', 'invalid_registry');
    requireValue(Object.keys(incoming.families).every(name => FAMILIES.includes(name)), 'unknown_family');
    const documents = structuredClone(current._documents);
    const now = new Date().toISOString();
    let changed = false;
    for (const family of FAMILIES) {
      const entry = incoming.families[family];
      requireValue(entry && Number.isSafeInteger(entry.last_serial) && entry.last_serial >= 0
        && entry.last_serial <= 1000000000, 'invalid_serial');
      requireValue(Number.isSafeInteger(entry.last_count) && entry.last_count >= 0
        && entry.last_count <= 1000000000, 'invalid_count');
      requireValue(typeof entry.last_range === 'string' && entry.last_range.length <= 48
        && typeof entry.last_year === 'string' && /^(\d{4})?$/.test(entry.last_year), 'invalid_serial_metadata');
      const prior = current.families[family] || {};
      if (['last_serial', 'last_count', 'last_range', 'last_year'].every(key => entry[key] === prior[key])) continue;
      changed = true;
      const target = family === 'Istantaneo' ? documents[1] : documents[0];
      target.families = target.families || {};
      target.families[family] = { ...prior, last_serial: entry.last_serial, last_count: entry.last_count,
        last_range: entry.last_range, last_year: entry.last_year, updated_at: now, updated_by: label };
      target.updated_at = now;
    }
    if (!changed) return current;
    delete documents[0].families.Istantaneo;
    const additions = FILES.map((path, index) => ({ path,
      contents: btoa(String.fromCharCode(...encoder.encode(JSON.stringify(documents[index], null, 2)))) }));
    const query = 'mutation($input:CreateCommitOnBranchInput!){createCommitOnBranch(input:$input){commit{oid}}}';
    const result = await this.github('/graphql', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, variables: { input: {
        branch: { repositoryNameWithOwner: this.env.GITHUB_REPOSITORY, branchName: this.env.GITHUB_BRANCH },
        expectedHeadOid: current._service_revision, message: { headline: 'Update serial registry via approved device' },
        fileChanges: { additions },
      } } }),
    });
    requireValue(!result.errors?.length && result.data?.createCommitOnBranch?.commit?.oid, 'registry_changed', 409);
    const verified = await this.readRegistry();
    for (const family of FAMILIES) requireValue(verified.families[family]?.last_serial === incoming.families[family].last_serial,
      'registry_confirmation_failed', 503);
    return verified;
  }
}
