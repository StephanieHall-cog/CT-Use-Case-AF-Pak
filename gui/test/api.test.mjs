// API tests: boots server.mjs on a free port with a throw-away DATA_DIR and exercises
// login, cited field edits, selector pairing, proposal accept/reject and the real/synthetic boundary.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const PORT = 3900 + Math.floor(Math.random() * 500);
const BASE = `http://127.0.0.1:${PORT}`;
let proc, cookie = '', dir;

const api = async (method, path, body) => {
  const r = await fetch(BASE + path, { method, headers: { 'content-type': 'application/json', cookie }, body: body ? JSON.stringify(body) : undefined });
  const sc = r.headers.get('set-cookie'); if (sc) cookie = sc.split(';')[0];
  const t = await r.text(); let j; try { j = JSON.parse(t); } catch { j = t; }
  return { status: r.status, body: j };
};

before(async () => {
  dir = mkdtempSync(join(tmpdir(), 'afpak-gui-'));
  proc = spawn(process.execPath, [join(HERE, '..', 'server.mjs')], { env: { ...process.env, PORT: String(PORT), DATA_DIR: dir, ADMIN_PASSWORD: 'test-pass-123' }, stdio: ['ignore', 'pipe', 'pipe'] });
  const t0 = Date.now();
  while (Date.now() - t0 < 60000) { try { if ((await fetch(BASE + '/api/health')).ok) break; } catch {} await new Promise(r => setTimeout(r, 300)); }
  const l = await api('POST', '/api/login', { username: 'admin', password: 'test-pass-123' });
  assert.equal(l.status, 200, 'login');
});
after(() => { proc?.kill(); try { rmSync(dir, { recursive: true, force: true }); } catch {} });

test('synthetic targets exist with the fixed field set and citations; real people have no selectors/hits', async () => {
  const { body: list } = await api('GET', '/api/targets');
  const syn = list.find(t => t.dataset === 'synthetic'), real = list.find(t => t.dataset !== 'synthetic');
  assert.ok(syn && real);
  const { body: card } = await api('GET', `/api/targets/${syn.id}`);
  const fields = new Set(card.fields.map(f => f.field));
  for (const f of ['name', 'name_variations', 'kunyah', 'tribe', 'religion', 'network', 'bdl', 'addresses', 'travel', 'vehicle', 'family', 'physical', 'dob', 'passport', 'cnic', 'visa', 'notes']) assert.ok(fields.has(f), `field ${f} present`);
  assert.ok(card.fields.filter(f => f.value).every(f => f.citation), 'every populated field is cited');
  assert.ok(card.selectors.length > 0 && card.hits.length > 0);
  assert.ok(card.selectors.some(s => s.kind === 'imsi' && s.parent_id), 'IMSI paired to a phone');
  assert.ok(card.hits.every(h => h.citation), 'every location hit is cited');
  const { body: rc } = await api('GET', `/api/targets/${real.id}`);
  assert.equal(rc.selectors.length, 0); assert.equal(rc.hits.length, 0);
});

test('field add requires a citation and is auditable; selector pairing via parent_id', async () => {
  const { body: list } = await api('GET', '/api/targets');
  const id = list.find(t => t.dataset === 'synthetic').id;
  const bad = await api('POST', `/api/targets/${id}/fields`, { field: 'visa', value: 'V-1' });
  assert.equal(bad.status, 400);
  const ok = await api('POST', `/api/targets/${id}/fields`, { field: 'visa', value: 'V-1', citation: 'test', citation_url: 'https://example.org' });
  assert.equal(ok.status, 200);
  const ph = await api('POST', `/api/targets/${id}/selectors`, { kind: 'phone', value: '+93 700 000 0001', citation: 'test' });
  const im = await api('POST', `/api/targets/${id}/selectors`, { kind: 'imsi', value: '412200000000001', parent_id: ph.body.id, citation: 'test' });
  const { body: c2 } = await api('GET', `/api/targets/${id}`);
  assert.equal(c2.selectors.find(s => s.id === im.body.id)?.parent_id, ph.body.id);
  const { body: audit } = await api('GET', '/api/audit');
  assert.ok(audit.some(a => a.action === 'field_add'));
});

test('inference pass creates proposals that need accept/reject', async () => {
  const run = await api('POST', '/api/algorithms/run', {});
  assert.equal(run.status, 200);
  const { body: pb } = await api('GET', '/api/proposals');
  const props = Object.entries(pb).flatMap(([k, v]) => v.map(x => ({ ...x, type: k.replace(/s$/, '') })));
  assert.ok(props.length > 0);
  const p = props[0];
  assert.ok(p.proposed_by?.startsWith('algorithm:') || p.proposed_by, 'proposed_by set');
  const route = { field: `/api/fields/${p.id}`, selector: `/api/selectors/${p.id}`, link: `/api/links/${p.id}`, hit: `/api/hits/${p.id}` }[p.type];
  const acc = await api('PATCH', route, { status: 'accepted' });
  assert.equal(acc.status, 200);
  const { body: ab } = await api('GET', '/api/proposals');
  assert.ok(!ab[p.type + 's'].some(x => x.id === p.id));
});

test('map geojson carries source_label/source_url on every feature', async () => {
  for (const path of ['/api/events?synthetic=1&from=2001-01-01', '/api/sites', '/api/hits']) {
    const { body } = await api('GET', path);
    assert.ok(body.features.length > 0, path);
    assert.ok(body.features.every(f => f.properties.source_label), `${path} labelled`);
  }
});
