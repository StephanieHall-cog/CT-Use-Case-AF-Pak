// node --test — memo module: template building for the 4 kinds, save/list/read via the Express router, audit rows.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import Database from 'better-sqlite3';
import express from 'express';
import { memosRouter, buildTemplate, memoText, KINDS, CLASSIFICATION, toMgrs } from '../lib/memos.mjs';

const EID = 'SP-test0001';
let db, R, server, base;
const requireRole = min => (req, res, next) => { if (!req.user) return res.status(401).json({ error: 'auth required' }); if (min === 'analyst' && req.user.role === 'viewer') return res.status(403).json({ error: 'analyst role required' }); next(); };

before(async () => {
  db = new Database(':memory:');
  db.exec(`CREATE TABLE audit(id INTEGER PRIMARY KEY, ts TEXT DEFAULT (datetime('now')), user TEXT, action TEXT, target TEXT, before TEXT, after TEXT);
  CREATE TABLE card_fields(id INTEGER PRIMARY KEY, entity_id TEXT, field TEXT, value TEXT, citation TEXT, citation_url TEXT, status TEXT);
  CREATE TABLE card_selectors(id INTEGER PRIMARY KEY, entity_id TEXT, kind TEXT, value TEXT, parent_id INTEGER, platform TEXT, label TEXT, citation TEXT, citation_url TEXT, status TEXT);
  CREATE TABLE card_hits(id INTEGER PRIMARY KEY, entity_id TEXT, kind TEXT, ts TEXT, lat REAL, lon REAL, precision_km REAL, place TEXT, detail TEXT, selector_id INTEGER, citation TEXT, citation_url TEXT, status TEXT);`);
  const F = db.prepare('INSERT INTO card_fields(entity_id,field,value,citation,citation_url,status) VALUES (?,?,?,?,?,?)');
  const SYN = 'SYNTHETIC scenario — synthetic/targets_demo.json', URL = 'https://example.com/targets_demo.json';
  F.run(EID, 'name', 'Fictional Test Target', SYN, URL, 'accepted');
  F.run(EID, 'objective_name', 'OBJECTIVE UNITTEST', SYN, URL, 'accepted');
  F.run(EID, 'network', 'Fictional Network', SYN, URL, 'accepted');
  F.run(EID, 'role', 'facilitator', 'Analyst entry', null, 'accepted');
  F.run(EID, 'tribe', 'Fictional tribe / sub-tribe', SYN, URL, 'accepted');
  F.run(EID, 'kunyah', 'Abu Test', SYN, URL, 'accepted');
  F.run(EID, 'kunyah', 'Rejected Kunyah', SYN, URL, 'rejected');
  F.run(EID, 'notes', 'Fictional summary paragraph for the unit test.', SYN, URL, 'accepted');
  F.run(EID, 'bdl', 'Fictional compound, Nowhere district', SYN, URL, 'accepted');
  const S = db.prepare('INSERT INTO card_selectors(entity_id,kind,value,parent_id,platform,citation,citation_url,status) VALUES (?,?,?,?,?,?,?,?)');
  const ph = S.run(EID, 'phone', '+92 555 0100', null, null, SYN, URL, 'accepted').lastInsertRowid;
  S.run(EID, 'imsi', '410-99-0000000001', ph, null, SYN, URL, 'accepted');
  const H = db.prepare('INSERT INTO card_hits(entity_id,kind,ts,lat,lon,precision_km,place,citation,citation_url,status) VALUES (?,?,?,?,?,?,?,?,?,?)');
  H.run(EID, 'gsm_cdr', '2026-10-01T10:00Z', 33.1, 70.1, 1, 'Older place', SYN, URL, 'accepted');
  H.run(EID, 'ss7', '2026-10-12T14:30Z', 33.3, 69.9, 0.5, 'Latest place', SYN + ' — SS7', URL, 'accepted');
  H.run(EID, 'isr', '2026-10-13T09:00Z', 34.0, 71.0, 0.1, 'Proposed place', SYN, URL, 'proposed');
  R = new Database(':memory:'); R.exec("CREATE TABLE entities(id TEXT PRIMARY KEY, name TEXT, kind TEXT, dataset TEXT, role TEXT)"); R.prepare('INSERT INTO entities VALUES (?,?,?,?,?)').run(EID, 'Entity Name', 'person', 'synthetic', null);
  const app = express(); app.use(express.json());
  app.use((req, _res, next) => { const u = req.headers['x-user']; req.user = u ? { username: u, role: req.headers['x-role'] || 'analyst' } : null; next(); });
  app.use('/api', memosRouter(db, R, requireRole));
  await new Promise(r => { server = app.listen(0, r); }); base = `http://127.0.0.1:${server.address().port}`;
});
after(() => { server.close(); db.close(); R.close(); });
const get = (p, h = {}) => fetch(base + p, { headers: { 'x-user': 'tester', ...h } }).then(async r => [r.status, await r.json()]);
const post = (p, body, h = {}) => fetch(base + p, { method: 'POST', headers: { 'content-type': 'application/json', 'x-user': 'tester', ...h }, body: JSON.stringify(body) }).then(async r => [r.status, await r.json()]);

test('tables are created on mount', () => { assert.ok(db.prepare("SELECT 1 FROM sqlite_master WHERE name='memos'").get()); });
test('mgrs helper', () => { assert.equal(toMgrs(33.3, 69.9), '42SWB8378984907'); assert.equal(toMgrs(null, 'x'), null); });

test('profile template: accepted fields with [n] citations, numbered sources, summary from notes', () => {
  const t = buildTemplate(db, R, EID, 'profile', 'tester');
  assert.equal(t.kind, 'profile'); assert.equal(t.classification, CLASSIFICATION); assert.equal(t.name, 'Fictional Test Target'); assert.equal(t.objective_name, 'OBJECTIVE UNITTEST');
  assert.match(t.subject, /^PROFILE OF THE TARGET — OBJECTIVE UNITTEST \/ Fictional Test Target \(SP-test0001\)$/);
  assert.equal(t.summary, 'Fictional summary paragraph for the unit test.');
  const allItems = t.profile.flatMap(g => g.rows.flatMap(r => r.items));
  assert.ok(allItems.length >= 8); for (const i of allItems) assert.ok(Number.isInteger(i.n) && i.n >= 1, 'every value has a citation number');
  assert.ok(!allItems.some(i => i.value === 'Rejected Kunyah'), 'rejected fields excluded');
  assert.equal(t.sources.length, 3, 'distinct (citation,url) pairs numbered'); assert.deepEqual(t.sources.map(s => s.n), [1, 2, 3]);
  assert.equal(t.sources[0].citation, 'SYNTHETIC scenario — synthetic/targets_demo.json'); assert.equal(t.sources[0].url, 'https://example.com/targets_demo.json');
  const sel = t.profile.find(g => /Selectors/.test(g.title)); assert.ok(sel); assert.ok(sel.rows[0].items[1].paired, 'IMSI shown paired under its phone');
  const loc = t.profile.find(g => g.title === 'Last known location'); assert.match(loc.rows[0].items[0].value, /Latest place — 33\.30000, 69\.90000 \(MGRS 42SWB8378984907\) as of 2026-10-12T14:30Z \[ss7\]/);
  assert.match(t.body, /IDENTITY\n  Name: Fictional Test Target \[1\]/); assert.match(t.body, /Role in government \/ network: facilitator \[2\]/);
  assert.equal(t.refs.hit_id, 2); assert.equal(t.refs.mgrs, '42SWB8378984907');
});
test('profile template falls back to a generated one-liner when there are no notes', () => {
  db.prepare("UPDATE card_fields SET status='rejected' WHERE field='notes'").run();
  const t = buildTemplate(db, R, EID, 'profile'); assert.match(t.summary, /^Fictional Test Target \(OBJECTIVE UNITTEST\) is facilitator in Fictional Network \(tribe: Fictional tribe \/ sub-tribe\)\. Last known location: Latest place/);
  db.prepare("UPDATE card_fields SET status='accepted' WHERE field='notes'").run();
});
test('location template: auto line from latest ACCEPTED hit with MGRS, reference to the card', () => {
  const t = buildTemplate(db, R, EID, 'location');
  assert.equal(t.location_line, 'Fictional Test Target is located at 33.30000, 69.90000 (MGRS 42SWB8378984907) as of 2026-10-12T14:30Z [ss7, SYNTHETIC scenario — synthetic/targets_demo.json — SS7]');
  assert.equal(t.location_editable, false); assert.equal(t.card_link, '#card:' + EID); assert.equal(t.refs.profile_memo_id, null, 'no profile memo saved yet');
  assert.match(t.subject, /^LOCATION UPDATE — OBJECTIVE UNITTEST \/ Fictional Test Target \(SP-test0001\) — as of 2026-10-12T14:30Z$/);
  assert.equal(t.sources.length, 1);
});
test('location template leaves an editable placeholder when there is no accepted hit', () => {
  const t = buildTemplate(db, R, 'SP-nohits', 'location');
  assert.equal(t.location_editable, true); assert.match(t.location_line, /is located at <lat>, <lon> \(MGRS <mgrs>\) as of <time>/); assert.equal(t.name, 'SP-nohits');
});
test('burn and threat templates before any memo exists', () => {
  const b = buildTemplate(db, R, EID, 'burn'); assert.deepEqual(b.previous_memos, []); assert.deepEqual(b.required, ['body']); assert.match(b.subject, /^BURN NOTICE — /); assert.equal(b.body_label, 'Why we should not engage with this individual');
  const th = buildTemplate(db, R, EID, 'threat'); assert.equal(th.header, 'IMMEDIATE ATTENTION'); assert.deepEqual(th.required, ['body']); assert.match(th.subject, /^THREAT NOTICE — IMMEDIATE ATTENTION — /);
  assert.deepEqual(th.linked_profile, { entity_id: EID, name: 'Fictional Test Target', objective_name: 'OBJECTIVE UNITTEST', last_known_location: 'Latest place — 33.30000, 69.90000 (MGRS 42SWB8378984907) as of 2026-10-12T14:30Z [ss7]', card_link: '#card:' + EID, profile_memo_link: null });
  assert.throws(() => buildTemplate(db, R, EID, 'bogus'), /bad kind/);
});

test('HTTP: template route, save all 4 kinds, list newest first, read back, audit', async () => {
  let [st, t] = await get(`/api/targets/${EID}/memo-template?kind=profile`); assert.equal(st, 200); assert.equal(t.kind, 'profile');
  [st] = await get(`/api/targets/${EID}/memo-template?kind=nope`); assert.equal(st, 400);
  // viewer cannot save
  [st] = await post(`/api/targets/${EID}/memos`, { kind: 'profile', subject: 'x' }, { 'x-role': 'viewer' }); assert.equal(st, 403);
  // validation
  [st] = await post(`/api/targets/${EID}/memos`, { kind: 'burn', subject: 'Burn', body: '' }); assert.equal(st, 400);
  [st] = await post(`/api/targets/${EID}/memos`, { kind: 'threat', subject: 'Threat', body: '   ' }); assert.equal(st, 400);
  [st] = await post(`/api/targets/${EID}/memos`, { kind: 'profile', subject: '' }); assert.equal(st, 400);
  // 1. profile with an added section
  let [s1, p] = await post(`/api/targets/${EID}/memos`, { ...t, sections: [{ title: 'Assessment', body: 'Fictional assessment text.' }, { title: '', body: '' }], refs: { ...t.refs, profile_groups: t.profile } });
  assert.equal(s1, 200); assert.equal(p.kind, 'profile'); assert.equal(p.created_by, 'tester'); assert.equal(p.sections.length, 1, 'empty section dropped'); assert.equal(p.sources.length, 3); assert.equal(p.refs.profile_groups.length, t.profile.length);
  // 2. location now references the profile memo
  [st, t] = await get(`/api/targets/${EID}/memo-template?kind=location`); assert.equal(t.refs.profile_memo_id, p.id); assert.equal(t.refs.profile_memo_link, '#memo:' + p.id); assert.deepEqual(t.refs.memo_ids, [p.id]);
  const [s2, l] = await post(`/api/targets/${EID}/memos`, { ...t, body: 'Fictional movement update.', refs: { ...t.refs, location_line: t.location_line } }); assert.equal(s2, 200); assert.equal(l.refs.location_line, t.location_line);
  // 3. threat
  [st, t] = await get(`/api/targets/${EID}/memo-template?kind=threat`); assert.equal(t.linked_profile.profile_memo_link, '#memo:' + p.id);
  const [s3, th] = await post(`/api/targets/${EID}/memos`, { ...t, body: 'Fictional threat description.', refs: { ...t.refs, linked_profile: t.linked_profile } }); assert.equal(s3, 200); assert.equal(th.refs.linked_profile.name, 'Fictional Test Target');
  // 4. burn lists every previous memo
  [st, t] = await get(`/api/targets/${EID}/memo-template?kind=burn`); assert.deepEqual(t.previous_memos.map(m => m.id), [th.id, l.id, p.id]); assert.deepEqual(t.previous_memos.map(m => m.kind), ['threat', 'location', 'profile']);
  assert.ok(t.previous_memos.every(m => m.link === '#memo:' + m.id && m.created_by === 'tester' && m.kind_label && m.subject));
  const [s4, b] = await post(`/api/targets/${EID}/memos`, { ...t, body: 'Fictional reason not to engage.' }); assert.equal(s4, 200); assert.equal(b.refs.previous_memos.length, 3, 'server fills previous_memos when client omits');
  // list: newest first, lightweight rows
  const [s5, list] = await get(`/api/targets/${EID}/memos`); assert.equal(s5, 200); assert.deepEqual(list.map(m => m.kind), ['burn', 'threat', 'location', 'profile']); assert.ok(list.every(m => m.kind_label && m.subject && m.created_by && m.created_at)); assert.equal(list[0].body, undefined);
  const [s6, other] = await get(`/api/targets/SP-other/memos`); assert.equal(s6, 200); assert.deepEqual(other, []);
  // read back with rendered e-mail text
  const [s7, full] = await get(`/api/memos/${p.id}`); assert.equal(s7, 200); assert.equal(full.classification, CLASSIFICATION); assert.equal(full.kind_label, 'Profile of the Target');
  assert.ok(full.text.startsWith(CLASSIFICATION + '\n')); assert.ok(full.text.trim().endsWith(CLASSIFICATION)); assert.match(full.text, /Subject: PROFILE OF THE TARGET/); assert.match(full.text, /ASSESSMENT\nFictional assessment text\./); assert.match(full.text, /SOURCES\n  \[1\] SYNTHETIC scenario/);
  const [s8] = await get(`/api/memos/99999`); assert.equal(s8, 404);
  const bt = memoText(db.prepare('SELECT * FROM memos WHERE id=?').get(b.id)); assert.match(bt, /WHY WE SHOULD NOT ENGAGE WITH THIS INDIVIDUAL:\nFictional reason not to engage\./); assert.match(bt, /PREVIOUS MEMOS ON THIS INDIVIDUAL:\n  - \[Threat Notice\]/);
  const tt = memoText(db.prepare('SELECT * FROM memos WHERE id=?').get(th.id)); assert.match(tt, /\*\*\* IMMEDIATE ATTENTION \*\*\*/); assert.match(tt, /THREAT:\nFictional threat description\./);
  const lt = memoText(db.prepare('SELECT * FROM memos WHERE id=?').get(l.id)); assert.match(lt, /is located at 33\.30000, 69\.90000 \(MGRS 42SWB8378984907\) as of 2026-10-12T14:30Z/);
  // audit rows like server.mjs (user, action, target, after)
  const au = db.prepare("SELECT user, action, target, after FROM audit WHERE action='memo_create' ORDER BY id").all(); assert.equal(au.length, 4);
  assert.ok(au.every(a => a.user === 'tester' && a.target === EID)); assert.deepEqual(au.map(a => JSON.parse(a.after).kind), ['profile', 'location', 'threat', 'burn']);
  // unauthenticated
  const r = await fetch(`${base}/api/targets/${EID}/memos`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}' }); assert.equal(r.status, 401);
});
