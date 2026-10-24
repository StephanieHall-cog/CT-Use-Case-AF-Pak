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

test('structured citations: trigraph/pub/date/trust on seeded rows; analyst writes accept cit_* fields and reject bad trust', async () => {
  const { body: list } = await api('GET', '/api/targets');
  const syn = list.find(t => t.dataset === 'synthetic'), real = list.find(t => t.dataset !== 'synthetic' && (t.sources || '').includes('un_1988'));
  const { body: card } = await api('GET', `/api/targets/${syn.id}`);
  assert.ok(card.fields.filter(f => f.value).every(f => /^[A-Z]{3}$/.test(f.cit_src) && f.cit_pub && f.cit_date && f.cit_trust >= 1 && f.cit_trust <= 4), 'every synthetic field carries src/pub/date/trust');
  assert.ok(card.fields.some(f => f.cit_src === 'SYN'));
  assert.ok(card.selectors.every(s => s.cit_src) && card.hits.every(h => h.cit_src));
  if (real) { const { body: rc } = await api('GET', `/api/targets/${real.id}`); assert.ok(rc.fields.some(f => f.cit_src === 'UNS' && f.cit_trust === 1), 'UN-sourced field is UNS trust 1'); }
  const { body: meta } = await api('GET', '/api/meta'); assert.ok(meta.citeCodes.GJP && meta.trust[1] && meta.cardFields.some(f => f[0] === 'photo'));
  const bad = await api('POST', `/api/targets/${syn.id}/fields`, { field: 'tribe', value: 'X', cit_pub: 'Y', cit_trust: 7 }); assert.equal(bad.status, 400);
  const ok = await api('POST', `/api/targets/${syn.id}/fields`, { field: 'tribe', value: 'Zadran (test)', cit_src: 'HUM', cit_pub: 'HUMINT report 17', cit_date: '2026-10-02', cit_trust: 2, citation_url: 'https://example.org/r/17' });
  assert.equal(ok.status, 200);
  const { body: c2 } = await api('GET', `/api/targets/${syn.id}`); const f = c2.fields.find(x => x.id === ok.body.id);
  assert.deepEqual([f.cit_src, f.cit_pub, f.cit_date, f.cit_trust, f.citation], ['HUM', 'HUMINT report 17', '2026-10-02', 2, 'HUMINT report 17, 2026-10-02']);
  const pt = await api('PATCH', `/api/fields/${f.id}`, { cit_trust: 1, cit_date: '2026-10-03' }); assert.equal(pt.status, 200);
  const { body: c3 } = await api('GET', `/api/targets/${syn.id}`); assert.equal(c3.fields.find(x => x.id === f.id).cit_trust, 1);
});

test('reject requires a comment, is remembered, and re-identification is counted; bulk accept/reject', async () => {
  await api('POST', '/api/algorithms/run', {});
  const { body: p0 } = await api('GET', '/api/proposals');
  const fld = p0.fields[0]; assert.ok(fld, 'an alias proposal exists');
  const noc = await api('PATCH', `/api/fields/${fld.id}`, { status: 'rejected' }); assert.equal(noc.status, 400);
  const rj = await api('PATCH', `/api/fields/${fld.id}`, { status: 'rejected', reject_comment: 'Transliteration already covered by existing variation' }); assert.equal(rj.status, 200);
  const { body: p1 } = await api('GET', '/api/proposals');
  const rrow = p1.rejected.find(r => r.tbl === 'card_fields' && r.id === fld.id); assert.ok(rrow && rrow.reject_comment.includes('Transliteration') && rrow.rejected_by === 'admin');
  const { body: hist } = await api('GET', `/api/rejections?tbl=card_fields&id=${fld.id}`); assert.equal(hist.length, 1);
  const run2 = await api('POST', '/api/algorithms/run', {}); assert.ok(run2.body.reidentified >= 1, 'rejected alias re-identified on next pass');
  const { body: p2 } = await api('GET', '/api/proposals'); assert.ok(p2.rejected.find(r => r.id === fld.id && r.tbl === 'card_fields').reidentified >= 1);
  assert.ok(!p2.fields.some(x => x.id === fld.id), 'rejected item is not re-queued as a fresh proposal');
  const items = p2.fields.slice(0, 3).map(x => ({ tbl: 'card_fields', id: x.id })); assert.ok(items.length >= 2);
  const bbad = await api('POST', '/api/proposals/bulk', { items, status: 'rejected' }); assert.equal(bbad.status, 400);
  const bok = await api('POST', '/api/proposals/bulk', { items: items.slice(0, 1), status: 'rejected', reject_comment: 'bulk test' }); assert.equal(bok.body.updated, 1);
  const acc = await api('POST', '/api/proposals/bulk', { items: items.slice(1), status: 'accepted' }); assert.equal(acc.body.updated, items.length - 1);
  const { body: p3 } = await api('GET', '/api/proposals'); assert.ok(items.every(i => !p3.fields.some(x => x.id === i.id)));
  const { body: audit } = await api('GET', '/api/audit'); assert.ok(audit.some(a => a.action === 'card_fields_reject') && audit.some(a => a.action === 'proposals_bulk'));
});

test('profile photo upload (data URL) is stored, served and recorded as a cited photo field', async () => {
  const { body: list } = await api('GET', '/api/targets'); const id = list.find(t => t.dataset === 'synthetic').id;
  const png = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';
  const bad = await api('POST', `/api/targets/${id}/photo`, { data: png }); assert.equal(bad.status, 400);
  const ok = await api('POST', `/api/targets/${id}/photo`, { data: png, cit_src: 'OSN', cit_pub: 'Telegram channel (synthetic)', cit_trust: 3 }); assert.equal(ok.status, 200);
  const img = await fetch(BASE + ok.body.url, { headers: { cookie } }); assert.equal(img.status, 200); assert.equal(img.headers.get('content-type'), 'image/png');
  const { body: card } = await api('GET', `/api/targets/${id}`); const ph = card.fields.find(f => f.field === 'photo' && f.value === ok.body.url); assert.ok(ph && ph.cit_src === 'OSN');
  const { body: l2 } = await api('GET', '/api/targets'); assert.equal(l2.find(t => t.id === id).photo, ok.body.url);
});
