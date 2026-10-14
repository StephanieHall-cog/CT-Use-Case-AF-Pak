// AfPak target tracker — UNCLASSIFIED demo GUI over db/afpak*.sqlite (read-only) + gui/data/app.db (analyst writes).
import express from 'express';
import Database from 'better-sqlite3';
import { mkdirSync, existsSync, readFileSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import { createUser, hashPassword, login, logout, sessionUser, parseCookies, requireRole, ROLES } from './lib/auth.mjs';
import { memosRouter } from './lib/memos.mjs';

const HERE = dirname(fileURLToPath(import.meta.url)); const ROOT = join(HERE, '..');
const PORT = +(process.env.PORT || 3300);
const AFPAK_DB = process.env.AFPAK_DB || (existsSync(join(ROOT, 'db/afpak_demo.sqlite')) ? join(ROOT, 'db/afpak_demo.sqlite') : join(ROOT, 'db/afpak.sqlite'));
const DATA_DIR = process.env.DATA_DIR || join(HERE, 'data'); mkdirSync(DATA_DIR, { recursive: true });
const R = new Database(AFPAK_DB, { readonly: true });
const db = new Database(join(DATA_DIR, 'app.db')); db.pragma('journal_mode = WAL');
// cache prepared statements per SQL text: avoids re-preparing on every request (and a better-sqlite3 Statement-destructor assertion seen under GC)
for (const d of [R, db]) { const cache = new Map(), raw = d.prepare.bind(d); d.prepare = sql => { let st = cache.get(sql); if (!st) { st = raw(sql); cache.set(sql, st); } return st; }; }
db.exec(`
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, pass_hash TEXT NOT NULL, salt TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'viewer', created_at TEXT DEFAULT (datetime('now')), last_login TEXT);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at TEXT, expires_at TEXT);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, ts TEXT DEFAULT (datetime('now')), user TEXT, action TEXT, target TEXT, before TEXT, after TEXT);
CREATE TABLE IF NOT EXISTS card_fields(id INTEGER PRIMARY KEY, entity_id TEXT NOT NULL, field TEXT NOT NULL, value TEXT, citation TEXT, citation_url TEXT,
  status TEXT NOT NULL DEFAULT 'accepted', proposed_by TEXT, edited_by TEXT, edited_at TEXT DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS cf_e ON card_fields(entity_id, field);
CREATE TABLE IF NOT EXISTS card_selectors(id INTEGER PRIMARY KEY, entity_id TEXT NOT NULL, kind TEXT NOT NULL, value TEXT NOT NULL, parent_id INTEGER, platform TEXT, label TEXT,
  citation TEXT, citation_url TEXT, status TEXT NOT NULL DEFAULT 'accepted', proposed_by TEXT, edited_by TEXT, edited_at TEXT DEFAULT (datetime('now')), src_id TEXT);
CREATE INDEX IF NOT EXISTS cs_e ON card_selectors(entity_id);
CREATE TABLE IF NOT EXISTS card_links(id INTEGER PRIMARY KEY, a_id INTEGER NOT NULL, b_id INTEGER NOT NULL, relation TEXT NOT NULL, evidence TEXT, citation TEXT, citation_url TEXT,
  status TEXT NOT NULL DEFAULT 'accepted', proposed_by TEXT, edited_by TEXT, edited_at TEXT DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS card_hits(id INTEGER PRIMARY KEY, entity_id TEXT NOT NULL, kind TEXT, ts TEXT, lat REAL, lon REAL, precision_km REAL, place TEXT, detail TEXT, selector_id INTEGER,
  citation TEXT, citation_url TEXT, status TEXT NOT NULL DEFAULT 'accepted', proposed_by TEXT, edited_by TEXT, edited_at TEXT DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS poi(entity_id TEXT PRIMARY KEY, on_ INTEGER, priority TEXT, reason TEXT, by_user TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS investigations(id INTEGER PRIMARY KEY, name TEXT NOT NULL, owner TEXT, data TEXT NOT NULL, created_at TEXT DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);`);
{ const pw = process.env.ADMIN_PASSWORD, au = process.env.ADMIN_USER || 'admin'; const ex = db.prepare('SELECT id FROM users WHERE username=?').get(au);
  if (!ex) { if (!pw) throw new Error('ADMIN_PASSWORD required for first boot'); createUser(db, au, pw, 'admin'); }
  else if (pw) { const { salt, hash } = hashPassword(pw); db.prepare("UPDATE users SET pass_hash=?, salt=?, role='admin' WHERE id=?").run(hash, salt, ex.id); } }
const audit = (user, action, target, before, after) => db.prepare('INSERT INTO audit(user,action,target,before,after) VALUES (?,?,?,?,?)').run(user || null, action, target || null, before == null ? null : JSON.stringify(before), after == null ? null : JSON.stringify(after));

// ---- fixed card field set (Stephanie's list). Every field: value + citation + citation_url, always rendered even if blank.
export const CARD_FIELDS = [
  ['name', 'Name', 'text'], ['name_variations', 'Name variations', 'list'], ['kunyah', 'Kunyah / Call sign / Nicknames', 'list'], ['objective_name', 'Objective name', 'text'],
  ['tribe', 'Tribe affiliation', 'text'], ['religion', 'Religion', 'text'], ['network', 'Terrorist network', 'text'], ['role', 'Role in government / network', 'text'],
  ['dob', 'Date of birth', 'text'], ['pob', 'Place of birth', 'text'], ['passport', 'Passport number', 'list'], ['cnic', 'CNIC or ID number', 'list'], ['visa', 'Visa number', 'list'],
  ['bdl', 'Bed Down Location (BDL)', 'text'], ['addresses', 'Addresses or alternate known locations', 'list'], ['travel', 'Travel', 'list'],
  ['vehicle', 'Car make / model', 'list'], ['family', 'Family members (name — relationship)', 'list'], ['physical', 'Physical descriptors', 'list'], ['notes', 'Additional notes', 'long']];
const SEL_KINDS = ['phone', 'imsi', 'imei', 'pushtoken', 'email', 'social', 'social_id', 'cma_account', 'vehicle'];
const HIT_KINDS = ['gsm_cdr', 'ss7', 'isr', 'travel', 'humint', 'open_source', 'other'];
const has = t => !!R.prepare("SELECT 1 FROM sqlite_master WHERE name=?").get(t);
const SRC = { podcast: 'FDD Long War Journal — Generation Jihad podcast', document: 'Open-access document corpus', un_1988: 'UN Security Council 1988 Sanctions List', fbi_wanted: 'FBI Wanted — Terrorism', isw_maps: 'ISW / CTP Map Room', synthetic: 'SYNTHETIC scenario (synthetic/targets_demo.json)', public_reference: 'Public reference (approximate; verify)', analyst: 'Analyst entry' };
const SYN_CIT = 'SYNTHETIC scenario — synthetic/targets_demo.json'; const SYN_URL = 'https://github.com/StephanieHall-cog/CT-Use-Case-AF-Pak/blob/main/synthetic/targets_demo.json';

// ---- seed card_fields / card_selectors / card_hits from the built DB (synthetic target_cards + real-person biodata) once per entity
function seedCard(eid) {
  if (db.prepare('SELECT 1 FROM kv WHERE k=?').get('seeded:' + eid)) return;
  const e = R.prepare('SELECT * FROM entities WHERE id=?').get(eid); if (!e) return;
  const tc = has('target_cards') ? R.prepare('SELECT * FROM target_cards WHERE entity_id=?').get(eid) : null;
  const put = db.prepare('INSERT INTO card_fields(entity_id,field,value,citation,citation_url,status,proposed_by,edited_by) VALUES (?,?,?,?,?,?,?,?)');
  const aliases = R.prepare('SELECT alias, source FROM aliases WHERE entity_id=?').all(eid);
  const fam = R.prepare(`SELECT r.type, x.name, r.source, r.episode_idx, r.quote, r.detail FROM relationships r JOIN entities x ON x.id=CASE WHEN r.source_id=? THEN r.target_id ELSE r.source_id END
     WHERE (r.source_id=? OR r.target_id=?) AND (r.type LIKE '%\\_of' ESCAPE '\\' OR r.type='family')`).all(eid, eid, eid);
  const cit = s => s === 'synthetic' ? [SYN_CIT, SYN_URL] : s === 'un_1988' ? ['UN 1988 Sanctions List', 'https://main.un.org/securitycouncil/en/sanctions/1988/materials'] : s === 'fbi_wanted' ? ['FBI Wanted', 'https://www.fbi.gov/wanted/terrorism'] : s === 'podcast' || s === 'extraction' ? ['Generation Jihad podcast (extracted)', 'https://redcircle.com/shows/generation-jihad'] : [SRC[s] || s, null];
  const syn = e.dataset === 'synthetic';
  const C = syn ? [SYN_CIT, SYN_URL] : ['Podcast/document extraction — see Sources tab', null];
  put.run(eid, 'name', e.name, ...C, 'accepted', 'seed', 'seed');
  for (const a of aliases) { const k = tc && JSON.parse(tc.kunyas || '[]').includes(a.alias) ? 'kunyah' : 'name_variations'; const [c, u] = cit(a.source); put.run(eid, k, a.alias, c, u, 'accepted', 'seed', 'seed'); }
  if (e.role) put.run(eid, 'role', e.role, ...C, 'accepted', 'seed', 'seed');
  for (const f of fam) { const [c, u] = cit(f.source); put.run(eid, 'family', `${f.name} — ${f.type.replace(/_/g, ' ')}`, f.quote ? `${c}: "${String(f.quote).slice(0, 160)}"` : c, u, 'accepted', 'seed', 'seed'); }
  const orgs = R.prepare('SELECT DISTINCT o.name FROM memberships m JOIN entities o ON o.id=m.org_id WHERE m.entity_id=?').all(eid).map(x => x.name);
  if (tc) {
    const T = (f, v) => v != null && v !== '' && put.run(eid, f, typeof v === 'string' ? v : JSON.stringify(v), SYN_CIT, SYN_URL, 'accepted', 'seed', 'seed');
    T('objective_name', tc.objective_name); T('tribe', [tc.tribe, tc.sub_tribe].filter(Boolean).join(' / ')); T('religion', tc.religion); T('network', tc.network); T('dob', tc.dob); T('pob', tc.pob); T('bdl', tc.bdl);
    for (const a of JSON.parse(tc.addresses || '[]')) T('addresses', `${a.label}: ${a.detail}, ${a.place} (${a.lat}, ${a.lon}; since ${a.since})`);
    for (const t of JSON.parse(tc.travel || '[]')) T('travel', `${t.date} → ${t.end}: ${t.origin} → ${t.destination}, ${t.mode}; purpose ${t.purpose} [${t.source}, ${t.confidence}]`);
    T('notes', tc.summary);
    // deterministic synthetic identity docs + physical descriptors (fictional)
    const h = [...eid].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7); const n = k => (h >> k) % 1000;
    const pk = /Pakistan|Miram|Mir Ali|Bannu|Peshawar|Quetta|Bara|Dera/.test(tc.home_area + tc.pob);
    T('passport', pk ? `PK${String(1000000 + n(3) * 997).slice(0, 7)}X (fictional)` : `P0${String(1000000 + n(5) * 991).slice(0, 7)} (fictional; Afghan)`);
    T('cnic', pk ? `21${n(2) % 9}0${n(7)}-${String(n(4)).padStart(3, '0')}${n(1) % 10}${n(9) % 10}-${n(2) % 10} (fictional CNIC)` : `Tazkira 1399-${n(6)}-${n(8)} (fictional)`);
    if (n(2) % 3 === 0) T('visa', `UAE visit visa ${n(4)}${n(1)}${n(2)} (fictional)`);
    T('physical', `Height ~${165 + n(2) % 20} cm; build ${['slim', 'medium', 'heavy'][n(3) % 3]}; beard ${['long black', 'greying', 'trimmed', 'henna-dyed'][n(4) % 4]}; ${['scar left cheek', 'limp (right leg)', 'missing fingertip left hand', 'no distinguishing marks noted'][n(5) % 4]} (fictional)`);
    if (!orgs.length && tc.network) orgs.push(tc.network);
  } else {
    for (const o of orgs) put.run(eid, 'network', o, ...C, 'accepted', 'seed', 'seed');
    const prof = has('profiles') ? R.prepare('SELECT * FROM profiles WHERE entity_id=?').all(eid) : [];
    for (const p of prof) { const u = p.url || (p.source === 'un_1988' ? 'https://main.un.org/securitycouncil/en/sanctions/1988/materials' : null), c = `${SRC[p.source]} ${p.reference}`;
      if (p.dob) put.run(eid, 'dob', p.dob, c, u, 'accepted', 'seed', 'seed'); if (p.pob) put.run(eid, 'pob', p.pob, c, u, 'accepted', 'seed', 'seed'); if (p.addresses) put.run(eid, 'addresses', p.addresses, c, u, 'accepted', 'seed', 'seed');
      if (p.documents) put.run(eid, 'passport', p.documents, c, u, 'accepted', 'seed', 'seed'); if (p.physical) { try { const ph = JSON.parse(p.physical); const s = Object.entries(ph).map(([k, v]) => `${k}: ${v}`).join('; '); if (s) put.run(eid, 'physical', s, c, u, 'accepted', 'seed', 'seed'); } catch { } }
      if (p.nationality) put.run(eid, 'notes', `Nationality (as listed): ${p.nationality}`, c, u, 'accepted', 'seed', 'seed'); if (p.designation || p.title) put.run(eid, 'role', [p.title, p.designation].filter(Boolean).join(' — '), c, u, 'accepted', 'seed', 'seed'); }
    if (e.nationality) put.run(eid, 'notes', `Origin (podcast): ${e.nationality}`, ...C, 'accepted', 'seed', 'seed');
  }
  if (tc && orgs.length) for (const o of orgs) if (!db.prepare("SELECT 1 FROM card_fields WHERE entity_id=? AND field='network' AND value=?").get(eid, o)) put.run(eid, 'network', o, SYN_CIT, SYN_URL, 'accepted', 'seed', 'seed');
  // selectors with pairing: phone <- imsi/imei/pushtoken/social via selector_links
  if (has('selectors')) {
    const sels = R.prepare('SELECT * FROM selectors WHERE entity_id=?').all(eid); const idmap = {};
    const ins = db.prepare('INSERT INTO card_selectors(entity_id,kind,value,parent_id,platform,label,citation,citation_url,status,proposed_by,edited_by,src_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)');
    const links = R.prepare('SELECT * FROM selector_links WHERE a_id IN (SELECT id FROM selectors WHERE entity_id=?) OR b_id IN (SELECT id FROM selectors WHERE entity_id=?)').all(eid, eid);
    const parentOf = {}; for (const l of links) { if (l.relation === 'same_subscriber') parentOf[l.b_id] = l.a_id; if (l.relation === 'used_with') parentOf[l.b_id] = parentOf[l.a_id] || l.a_id; if (l.relation === 'registered_with') parentOf[l.a_id] = l.b_id; }
    const order = [...sels].sort((a, b) => (parentOf[a.id] ? 1 : 0) - (parentOf[b.id] ? 1 : 0));
    for (const s of order) { if (s.kind === 'vehicle') { put.run(eid, 'vehicle', s.value + (s.platform ? ` — ${s.platform}` : ''), SYN_CIT, SYN_URL, 'accepted', 'seed', 'seed'); continue; }
      const pid = parentOf[s.id] && idmap[parentOf[s.id]] ? idmap[parentOf[s.id]] : null;
      const r = ins.run(eid, s.kind, s.value, pid, s.platform || s.provider || null, s.label || null, `${SYN_CIT} (${s.confidence || 'n/a'} confidence)`, SYN_URL, 'accepted', 'seed', 'seed', s.id); idmap[s.id] = r.lastInsertRowid;
      if (s.kind === 'social') { const h2 = [...s.value].reduce((a, c) => (a * 33 + c.charCodeAt(0)) >>> 0, 5); ins.run(eid, 'social_id', `${(s.platform || 'platform').toLowerCase()}:${100000000000 + h2 % 900000000000} (fictional platform ID)`, r.lastInsertRowid, s.platform, 'platform user ID', SYN_CIT, SYN_URL, 'accepted', 'seed', 'seed', null); }
      if (s.kind === 'phone' && (parseInt(s.id.slice(4)) % 2 === 0)) ins.run(eid, 'pushtoken', `apns:${[...s.value].reduce((a, c) => (a * 17 + c.charCodeAt(0)) >>> 0, 3).toString(16)}…${s.id.slice(4)} (fictional push token)`, r.lastInsertRowid, 'APNs/FCM', 'push token', SYN_CIT, SYN_URL, 'accepted', 'seed', 'seed', null); }
    const li = db.prepare('INSERT INTO card_links(a_id,b_id,relation,evidence,citation,citation_url,status,proposed_by,edited_by) VALUES (?,?,?,?,?,?,?,?,?)');
    for (const l of links) { const a = idmap[l.a_id] || db.prepare('SELECT id FROM card_selectors WHERE src_id=?').get(l.a_id)?.id, b = idmap[l.b_id] || db.prepare('SELECT id FROM card_selectors WHERE src_id=?').get(l.b_id)?.id;
      if (a && b && !db.prepare('SELECT 1 FROM card_links WHERE a_id=? AND b_id=? AND relation=?').get(a, b, l.relation)) li.run(a, b, l.relation, l.evidence, SYN_CIT, SYN_URL, l.confidence === 'low' ? 'proposed' : 'accepted', l.confidence === 'low' ? 'algorithm:selector-correlator' : 'seed', 'seed'); }
  }
  if (has('location_hits')) { const hi = db.prepare('INSERT INTO card_hits(entity_id,kind,ts,lat,lon,precision_km,place,detail,selector_id,citation,citation_url,status,proposed_by,edited_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)');
    for (const h of R.prepare('SELECT * FROM location_hits WHERE entity_id=? ORDER BY ts').all(eid)) { const sid = h.selector_id ? db.prepare('SELECT id FROM card_selectors WHERE src_id=?').get(h.selector_id)?.id : null;
      hi.run(eid, h.kind, h.ts, h.lat, h.lon, h.precision_km, h.place, h.detail, sid, `${SYN_CIT} — ${h.kind.toUpperCase()} (${h.confidence})`, SYN_URL, h.confidence === 'low' ? 'proposed' : 'accepted', h.confidence === 'low' ? 'algorithm:geo-feed-ingest' : 'seed', 'seed'); } }
  // algorithm proposals for real people: profile matches (auto-citation to the UN/FBI record) that were NOT curated
  db.prepare('INSERT INTO kv(k,v) VALUES (?,?)').run('seeded:' + eid, new Date().toISOString());
}

const app = express(); app.disable('x-powered-by'); app.set('trust proxy', 1); app.use(express.json({ limit: '8mb' }));
app.use((req, res, next) => { res.setHeader('X-Frame-Options', 'SAMEORIGIN'); res.setHeader('X-Content-Type-Options', 'nosniff');
  req.user = sessionUser(db, parseCookies(req.headers.cookie).uw);
  if (req.path.startsWith('/api/') && !req.user && !['/api/login', '/api/health'].includes(req.path)) return res.status(401).json({ error: 'auth required' }); next(); });
app.get('/api/health', (_q, r) => r.json({ ok: true, db: AFPAK_DB }));
app.post('/api/login', (req, res) => { const s = login(db, req.body?.username, req.body?.password, req.ip); if (!s) return res.status(401).json({ error: 'invalid credentials' });
  res.setHeader('Set-Cookie', `uw=${s.token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200${req.secure ? '; Secure' : ''}`); res.json(s.user); });
app.post('/api/logout', (req, res) => { logout(db, parseCookies(req.headers.cookie).uw); res.setHeader('Set-Cookie', 'uw=; Path=/; Max-Age=0'); res.json({ ok: true }); });
app.get('/api/me', (req, res) => res.json(req.user));
app.get('/api/meta', (_q, res) => {
  const groups = R.prepare("SELECT name, n_episodes FROM entities WHERE kind='organization' AND name IN ('Haqqani Network','Taliban','Tehrik-i-Taliban Pakistan','Islamic State Khorasan Province','al-Qaeda','Islamic State','al-Qaeda in the Indian Subcontinent','Lashkar-e-Taiba') ORDER BY n_episodes DESC").all();
  const sitekinds = has('sites') ? R.prepare('SELECT kind, count(*) n FROM sites GROUP BY kind').all() : [];
  const years = R.prepare("SELECT min(substr(date,1,4)) y0, max(substr(date,1,4)) y1 FROM events WHERE date GLOB '[12][0-9][0-9][0-9]*'").get();
  res.json({ cardFields: CARD_FIELDS, selKinds: SEL_KINDS, hitKinds: HIT_KINDS, groups: groups.map(g => g.name), sitekinds, sources: SRC, years, roles: ROLES, center: { lat: 33.4, lon: 69.6 }, db: AFPAK_DB.split('/').pop() });
});
// ---- map layers
const epUrl = R.prepare('SELECT audio_url, title FROM episodes WHERE idx=?');
const docUrl = has('documents') ? R.prepare('SELECT url, title FROM documents WHERE doc_id=?') : null;
function evSource(r) {
  if (r.dataset === 'synthetic') return [SRC.synthetic, SYN_URL];
  if (r.source === 'isw_maps' && r.map_url) return [`${SRC.isw_maps} — ${r.map_title || ''}`, r.map_url];
  if (r.episode_idx != null) { const e = epUrl.get(r.episode_idx); return [`${SRC.podcast} — ep. ${r.episode_idx} ${e?.title || ''} @ ${r.timestamp || ''}`, e?.audio_url || 'https://redcircle.com/shows/generation-jihad']; }
  if (r.doc_id && docUrl) { const d = docUrl.get(r.doc_id); return [`${SRC.document} — ${d?.title || r.doc_id} (${r.timestamp || ''})`, d?.url || null]; }
  return [SRC[r.source] || r.source || 'unknown', null];
}
app.get('/api/events', (req, res) => {
  const q = req.query, from = q.from || '1990-01-01', to = q.to || '2099-12-31', lim = Math.min(+q.limit || 4000, 20000);
  const rows = R.prepare(`SELECT ev.id, ev.date, ev.type, ev.description, ev.place_text, ev.dataset, ev.source, ev.episode_idx, ev.timestamp, ev.doc_id,
      COALESCE(g.lat, mp.lat, pc.lat) lat, COALESCE(g.lon, mp.lon, pc.lon) lon, COALESCE(g.precision_km, mp.geo_precision_km, 15) precision_km,
      CASE WHEN g.event_id IS NOT NULL THEN 'scenario' WHEN mp.id IS NOT NULL THEN 'isw_plot' ELSE 'place_coords' END geo_method, ms.url map_url, ms.title map_title, mp.legend_class,
      (SELECT group_concat(en.name,'; ') FROM event_actors ea JOIN entities en ON en.id=ea.entity_id WHERE ea.event_id=ev.id) actors,
      (SELECT group_concat(en.name,'; ') FROM event_actors ea JOIN entities en ON en.id=ea.entity_id WHERE ea.event_id=ev.id AND en.kind='organization') groups
    FROM events ev LEFT JOIN event_geo g ON g.event_id=ev.id ${has('map_plots') ? 'LEFT JOIN map_plots mp ON mp.event_id=ev.id LEFT JOIN map_sources ms ON ms.id=mp.map_id' : 'LEFT JOIN (SELECT NULL id, NULL event_id, NULL lat, NULL lon, NULL geo_precision_km, NULL legend_class, NULL map_id) mp ON 0 LEFT JOIN (SELECT NULL id, NULL url, NULL title) ms ON 0'}
    LEFT JOIN place_coords pc ON pc.entity_id=ev.place_id
    WHERE ev.date >= ? AND ev.date <= ? AND COALESCE(g.lat, mp.lat, pc.lat) IS NOT NULL ${q.types ? `AND ev.type IN (${String(q.types).split(',').map(t => `'${t.replace(/'/g, "''")}'`).join(',')})` : ''}
    ORDER BY ev.date DESC LIMIT ${lim}`).all(from, to);
  const feats = rows.filter(r => !q.group || (r.groups || '').includes(q.group)).filter(r => q.synthetic === '1' || r.dataset !== 'synthetic').map(r => { const [sl, su] = evSource(r);
    return { type: 'Feature', geometry: { type: 'Point', coordinates: [r.lon, r.lat] }, properties: { ...r, source_label: sl, source_url: su } }; });
  res.json({ type: 'FeatureCollection', features: feats });
});
app.get('/api/sites', (req, res) => { const rows = has('sites') ? R.prepare('SELECT * FROM sites').all() : [];
  res.json({ type: 'FeatureCollection', features: rows.map(r => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [r.lon, r.lat] }, properties: { ...r, source_label: SRC[r.source] || r.source, source_url: r.source_url || 'https://github.com/StephanieHall-cog/CT-Use-Case-AF-Pak/blob/main/synthetic/sites_reference.json' } })) }); });
app.get('/api/hits', (req, res) => { // all accepted geolocation events across cards (last-known layer + trails)
  const rows = db.prepare(`SELECT h.*, (SELECT value FROM card_fields f WHERE f.entity_id=h.entity_id AND f.field='name' AND f.status='accepted' ORDER BY id LIMIT 1) name,
     (SELECT value FROM card_fields f WHERE f.entity_id=h.entity_id AND f.field='objective_name' AND f.status='accepted' ORDER BY id LIMIT 1) objective FROM card_hits h WHERE h.status='accepted' ${req.query.entity ? 'AND h.entity_id=@e' : ''} ORDER BY h.ts`).all({ e: req.query.entity });
  const last = {}; for (const r of rows) last[r.entity_id] = r.id;
  res.json({ type: 'FeatureCollection', features: rows.map(r => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [r.lon, r.lat] }, properties: { ...r, is_last: last[r.entity_id] === r.id ? 1 : 0, source_label: r.citation, source_url: r.citation_url } })) }); });
app.get('/api/maps', (_q, res) => res.json(has('map_sources') ? R.prepare('SELECT id, title, url, page_date, as_of_date, map_type, image_path, image_corners FROM map_sources ORDER BY page_date').all() : []));
// ---- targets / cards
function ensureSeeded() { if (db.prepare("SELECT 1 FROM kv WHERE k='seeded:all'").get()) return;
  const ids = [...(has('target_cards') ? R.prepare('SELECT entity_id id FROM target_cards').all() : []), ...(has('profiles') ? R.prepare("SELECT DISTINCT entity_id id FROM profiles WHERE entity_id IS NOT NULL AND entity_id IN (SELECT id FROM entities WHERE kind='person' AND n_episodes>0)").all() : [])];
  for (const { id } of ids) seedCard(id); db.prepare("INSERT OR REPLACE INTO kv VALUES('seeded:all',datetime('now'))").run(); }
ensureSeeded();
const fieldsOf = (eid, status = null) => db.prepare(`SELECT * FROM card_fields WHERE entity_id=? ${status ? 'AND status=?' : ''} ORDER BY field, id`).all(...(status ? [eid, status] : [eid]));
app.get('/api/targets', (req, res) => { ensureSeeded(); const q = (req.query.q || '').toLowerCase();
  const ids = db.prepare('SELECT DISTINCT entity_id FROM card_fields').all().map(x => x.entity_id);
  const out = ids.map(id => { const e = R.prepare('SELECT * FROM entities WHERE id=?').get(id) || { id, name: id, dataset: 'synthetic' }; const F = fieldsOf(id, 'accepted');
    const g = f => F.filter(x => x.field === f).map(x => x.value); const last = db.prepare("SELECT * FROM card_hits WHERE entity_id=? AND status='accepted' ORDER BY ts DESC LIMIT 1").get(id);
    const poi = db.prepare('SELECT * FROM poi WHERE entity_id=?').get(id);
    return { id, name: g('name')[0] || e.name, dataset: e.dataset, objective: g('objective_name')[0], network: g('network'), tribe: g('tribe')[0], role: g('role')[0], aliases: [...g('kunyah'), ...g('name_variations')].slice(0, 6), n_episodes: e.n_episodes, sources: e.sources,
      n_selectors: db.prepare("SELECT count(*) n FROM card_selectors WHERE entity_id=? AND status='accepted'").get(id).n, n_hits: db.prepare("SELECT count(*) n FROM card_hits WHERE entity_id=? AND status='accepted'").get(id).n,
      n_proposed: db.prepare("SELECT (SELECT count(*) FROM card_fields WHERE entity_id=@i AND status='proposed')+(SELECT count(*) FROM card_selectors WHERE entity_id=@i AND status='proposed')+(SELECT count(*) FROM card_hits WHERE entity_id=@i AND status='proposed') n").get({ i: id }).n,
      last_hit: last ? { kind: last.kind, ts: last.ts, place: last.place, lat: last.lat, lon: last.lon } : null, poi: poi?.on_ ? poi : null }; })
    .filter(t => !q || JSON.stringify(t).toLowerCase().includes(q)).filter(t => !req.query.dataset || t.dataset === req.query.dataset);
  res.json(out); });
app.get('/api/entities/search', (req, res) => { const q = `%${req.query.q || ''}%`; res.json(R.prepare("SELECT DISTINCT e.id, e.name, e.kind, e.dataset, e.n_episodes, e.sources FROM entities e LEFT JOIN aliases a ON a.entity_id=e.id WHERE (e.name LIKE ? OR a.alias LIKE ?) ORDER BY e.n_episodes DESC LIMIT 40").all(q, q)); });
app.get('/api/targets/:id', (req, res) => { const id = req.params.id; seedCard(id); const e = R.prepare('SELECT * FROM entities WHERE id=?').get(id); if (!e && !fieldsOf(id).length) return res.status(404).json({ error: 'not found' });
  const sels = db.prepare('SELECT * FROM card_selectors WHERE entity_id=? ORDER BY COALESCE(parent_id,id), parent_id IS NOT NULL, id').all(id);
  const links = db.prepare('SELECT l.*, a.value a_value, a.kind a_kind, a.entity_id a_entity, b.value b_value, b.kind b_kind, b.entity_id b_entity FROM card_links l JOIN card_selectors a ON a.id=l.a_id JOIN card_selectors b ON b.id=l.b_id WHERE a.entity_id=? OR b.entity_id=?').all(id, id);
  const hits = db.prepare('SELECT * FROM card_hits WHERE entity_id=? ORDER BY ts DESC').all(id);
  const rels = e ? R.prepare(`SELECT r.type, r.source, r.confidence, r.dataset, r.quote, r.detail, r.episode_idx, r.timestamp, r.doc_id, x.id other_id, x.name other, x.kind other_kind, CASE WHEN r.source_id=? THEN 'out' ELSE 'in' END dir FROM relationships r JOIN entities x ON x.id=CASE WHEN r.source_id=? THEN r.target_id ELSE r.source_id END WHERE r.source_id=? OR r.target_id=? ORDER BY r.source, r.type LIMIT 400`).all(id, id, id, id).map(r => { const [sl, su] = evSource(r); return { ...r, source_label: sl, source_url: su }; }) : [];
  const profiles = e && has('profiles') ? R.prepare('SELECT * FROM profiles WHERE entity_id=?').all(id) : [];
  const mentions = e ? R.prepare('SELECT m.episode_idx, m.timestamp, m.quote, ep.title, ep.audio_url, ep.published FROM mentions m LEFT JOIN episodes ep ON ep.idx=m.episode_idx WHERE m.entity_id=? ORDER BY ep.published DESC LIMIT 60').all(id) : [];
  const events = e ? R.prepare(`SELECT ev.id, ev.date, ev.type, ev.description, ev.place_text, ev.dataset, ev.source, ev.episode_idx, ev.timestamp, ev.doc_id, COALESCE(g.lat, pc.lat) lat, COALESCE(g.lon, pc.lon) lon FROM events ev JOIN event_actors ea ON ea.event_id=ev.id LEFT JOIN event_geo g ON g.event_id=ev.id LEFT JOIN place_coords pc ON pc.entity_id=ev.place_id WHERE ea.entity_id=? ORDER BY ev.date DESC LIMIT 200`).all(id).map(r => { const [sl, su] = evSource(r); return { ...r, source_label: sl, source_url: su }; }) : [];
  res.json({ entity: e || { id, name: id, dataset: 'synthetic' }, fields: fieldsOf(id), selectors: sels, links, hits, relationships: rels, profiles, mentions, events, poi: db.prepare('SELECT * FROM poi WHERE entity_id=?').get(id) || null }); });
// ---- analyst writes (every one carries a citation; status proposed/accepted; audited)
const A = requireRole('analyst');
const upd = (tbl, cols) => (req, res) => { const b = req.body || {}; const row = db.prepare(`SELECT * FROM ${tbl} WHERE id=?`).get(req.params.id); if (!row) return res.status(404).json({ error: 'not found' });
  const sets = cols.filter(c => b[c] !== undefined); if (!sets.length) return res.status(400).json({ error: 'nothing to update' });
  db.prepare(`UPDATE ${tbl} SET ${sets.map(c => `${c}=@${c}`).join(',')}, edited_by=@u, edited_at=datetime('now') WHERE id=@id`).run({ ...Object.fromEntries(sets.map(c => [c, b[c]])), u: req.user.username, id: req.params.id });
  audit(req.user.username, tbl + '_edit', req.params.id, row, b); res.json({ ok: true }); };
const del = tbl => (req, res) => { const row = db.prepare(`SELECT * FROM ${tbl} WHERE id=?`).get(req.params.id); db.prepare(`DELETE FROM ${tbl} WHERE id=?`).run(req.params.id); if (tbl === 'card_selectors') db.prepare('DELETE FROM card_links WHERE a_id=? OR b_id=?').run(req.params.id, req.params.id); audit(req.user.username, tbl + '_delete', req.params.id, row, null); res.json({ ok: true }); };
app.post('/api/targets/:id/fields', A, (req, res) => { const b = req.body || {}; if (!CARD_FIELDS.some(f => f[0] === b.field)) return res.status(400).json({ error: 'unknown field' }); if (b.value && !b.citation) return res.status(400).json({ error: 'citation required' });
  const r = db.prepare('INSERT INTO card_fields(entity_id,field,value,citation,citation_url,status,proposed_by,edited_by) VALUES (?,?,?,?,?,?,?,?)').run(req.params.id, b.field, b.value || '', b.citation || '', b.citation_url || null, b.status || 'accepted', b.proposed_by || 'analyst', req.user.username);
  audit(req.user.username, 'field_add', req.params.id, null, b); res.json({ id: r.lastInsertRowid }); });
app.patch('/api/fields/:id', A, upd('card_fields', ['value', 'citation', 'citation_url', 'status'])); app.delete('/api/fields/:id', A, del('card_fields'));
app.post('/api/targets/:id/selectors', A, (req, res) => { const b = req.body || {}; if (!SEL_KINDS.includes(b.kind) || !b.value) return res.status(400).json({ error: 'kind/value required' }); if (!b.citation) return res.status(400).json({ error: 'citation required' });
  const r = db.prepare('INSERT INTO card_selectors(entity_id,kind,value,parent_id,platform,label,citation,citation_url,status,proposed_by,edited_by) VALUES (?,?,?,?,?,?,?,?,?,?,?)').run(req.params.id, b.kind, b.value, b.parent_id || null, b.platform || null, b.label || null, b.citation || '', b.citation_url || null, b.status || 'accepted', b.proposed_by || 'analyst', req.user.username);
  audit(req.user.username, 'selector_add', req.params.id, null, b); res.json({ id: r.lastInsertRowid }); });
app.patch('/api/selectors/:id', A, upd('card_selectors', ['value', 'parent_id', 'platform', 'label', 'citation', 'citation_url', 'status'])); app.delete('/api/selectors/:id', A, del('card_selectors'));
app.post('/api/links', A, (req, res) => { const b = req.body || {}; if (!b.a_id || !b.b_id || !b.relation) return res.status(400).json({ error: 'a_id, b_id, relation required' }); if (!b.citation) return res.status(400).json({ error: 'citation required' });
  const r = db.prepare('INSERT INTO card_links(a_id,b_id,relation,evidence,citation,citation_url,status,proposed_by,edited_by) VALUES (?,?,?,?,?,?,?,?,?)').run(b.a_id, b.b_id, b.relation, b.evidence || '', b.citation || '', b.citation_url || null, b.status || 'accepted', b.proposed_by || 'analyst', req.user.username); audit(req.user.username, 'link_add', r.lastInsertRowid, null, b); res.json({ id: r.lastInsertRowid }); });
app.patch('/api/links/:id', A, upd('card_links', ['relation', 'evidence', 'citation', 'citation_url', 'status'])); app.delete('/api/links/:id', A, del('card_links'));
app.post('/api/targets/:id/hits', A, (req, res) => { const b = req.body || {}; if (!b.ts || b.lat == null || b.lon == null) return res.status(400).json({ error: 'ts, lat, lon required' }); if (!b.citation) return res.status(400).json({ error: 'citation required' });
  const r = db.prepare('INSERT INTO card_hits(entity_id,kind,ts,lat,lon,precision_km,place,detail,selector_id,citation,citation_url,status,proposed_by,edited_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)').run(req.params.id, b.kind || 'other', b.ts, +b.lat, +b.lon, b.precision_km == null ? null : +b.precision_km, b.place || null, b.detail || null, b.selector_id || null, b.citation || '', b.citation_url || null, b.status || 'accepted', b.proposed_by || 'analyst', req.user.username);
  audit(req.user.username, 'hit_add', req.params.id, null, b); res.json({ id: r.lastInsertRowid }); });
app.patch('/api/hits/:id', A, upd('card_hits', ['kind', 'ts', 'lat', 'lon', 'precision_km', 'place', 'detail', 'selector_id', 'citation', 'citation_url', 'status'])); app.delete('/api/hits/:id', A, del('card_hits'));
app.post('/api/targets/:id/poi', A, (req, res) => { const b = req.body || {}; db.prepare('INSERT OR REPLACE INTO poi VALUES (?,?,?,?,?,datetime(\'now\'))').run(req.params.id, b.on ? 1 : 0, b.priority || 'Medium', b.reason || '', req.user.username); audit(req.user.username, 'poi', req.params.id, null, b); res.json({ ok: true }); });
app.post('/api/targets', A, (req, res) => { const b = req.body || {}; if (!b.name) return res.status(400).json({ error: 'name required' }); const id = 'SP-' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  db.prepare('INSERT INTO card_fields(entity_id,field,value,citation,citation_url,status,proposed_by,edited_by) VALUES (?,?,?,?,?,?,?,?)').run(id, 'name', b.name, b.citation || 'Analyst entry', b.citation_url || null, 'accepted', 'analyst', req.user.username);
  db.prepare('INSERT INTO kv(k,v) VALUES (?,?)').run('seeded:' + id, 'manual'); audit(req.user.username, 'target_create', id, null, b); res.json({ id }); });
// proposals queue (algorithm-identified additions awaiting approval) and algorithm runs
app.get('/api/proposals', (req, res) => res.json({
  fields: db.prepare("SELECT f.*, (SELECT value FROM card_fields n WHERE n.entity_id=f.entity_id AND n.field='name' AND n.status='accepted' LIMIT 1) name FROM card_fields f WHERE status='proposed' ORDER BY edited_at DESC").all(),
  selectors: db.prepare("SELECT s.*, (SELECT value FROM card_fields n WHERE n.entity_id=s.entity_id AND n.field='name' AND n.status='accepted' LIMIT 1) name FROM card_selectors s WHERE status='proposed' ORDER BY edited_at DESC").all(),
  links: db.prepare("SELECT l.*, a.value a_value, a.kind a_kind, a.entity_id a_entity, b.value b_value, b.kind b_kind, b.entity_id b_entity FROM card_links l JOIN card_selectors a ON a.id=l.a_id JOIN card_selectors b ON b.id=l.b_id WHERE l.status='proposed'").all(),
  hits: db.prepare("SELECT h.*, (SELECT value FROM card_fields n WHERE n.entity_id=h.entity_id AND n.field='name' AND n.status='accepted' LIMIT 1) name FROM card_hits h WHERE status='proposed' ORDER BY edited_at DESC").all() }));
app.post('/api/algorithms/run', A, (req, res) => { // inference pass: (1) UN/FBI profile aliases not yet on the card; (2) selectors shared across targets → proposed links; (3) podcast family edges missing on the card
  let n = 0; const ids = db.prepare('SELECT DISTINCT entity_id FROM card_fields').all().map(x => x.entity_id);
  for (const id of ids) { if (!has('profiles')) break;
    for (const p of R.prepare('SELECT * FROM profiles WHERE entity_id=?').all(id)) { let al = []; try { al = (JSON.parse(p.raw || '{}').aliases || []).map(a => a.name || a); } catch { }
      for (const a of al) if (!db.prepare('SELECT 1 FROM card_fields WHERE entity_id=? AND field IN (\'name_variations\',\'kunyah\') AND value=?').get(id, a)) { db.prepare('INSERT INTO card_fields(entity_id,field,value,citation,citation_url,status,proposed_by,edited_by) VALUES (?,?,?,?,?,?,?,?)').run(id, 'name_variations', a, `Auto-citation: ${SRC[p.source]} ${p.reference} (alias field)`, p.url || (p.source === 'fbi_wanted' ? 'https://www.fbi.gov/wanted/terrorism' : 'https://main.un.org/securitycouncil/en/sanctions/1988/materials'), 'proposed', 'algorithm:profile-alias-matcher', 'algorithm'); n++; } } }
  const dup = db.prepare("SELECT value, kind, group_concat(id) ids, count(DISTINCT entity_id) ne FROM card_selectors WHERE status='accepted' AND kind IN ('imei','imsi','phone','email','pushtoken') GROUP BY kind, value HAVING ne>1").all();
  for (const d of dup) { const [a, b] = d.ids.split(','); if (!db.prepare('SELECT 1 FROM card_links WHERE a_id=? AND b_id=?').get(a, b)) { db.prepare('INSERT INTO card_links(a_id,b_id,relation,evidence,citation,citation_url,status,proposed_by,edited_by) VALUES (?,?,?,?,?,?,?,?,?)').run(a, b, 'shared_selector', `Same ${d.kind} value appears on two targets`, 'Auto-citation: selector table cross-match', null, 'proposed', 'algorithm:selector-correlator', 'algorithm'); n++; } }
  audit(req.user.username, 'algorithm_run', null, null, { proposals: n }); res.json({ proposals: n }); });
// ---- link chart
app.get('/api/graph', (req, res) => { const root = req.query.root, depth = Math.min(+req.query.depth || 1, 2), syn = req.query.synthetic !== '0', sel = req.query.selectors === '1'; if (!root) return res.status(400).json({ error: 'root required' });
  const nodes = new Map(), edges = []; let frontier = [root]; const add = id => { if (nodes.has(id)) return; const e = R.prepare('SELECT id,name,kind,dataset,n_episodes,sources,role FROM entities WHERE id=?').get(id) || { id, name: db.prepare("SELECT value FROM card_fields WHERE entity_id=? AND field='name' LIMIT 1").get(id)?.value || id, kind: 'person', dataset: 'synthetic' }; nodes.set(id, e); };
  add(root); const seen = new Set();
  for (let d = 0; d < depth; d++) { const next = []; for (const id of frontier) { const rows = R.prepare(`SELECT r.id, r.source_id, r.target_id, r.type, r.source, r.confidence, r.dataset, r.quote, r.episode_idx, r.timestamp, r.doc_id FROM relationships r WHERE (r.source_id=? OR r.target_id=?) ${syn ? '' : "AND r.dataset='real'"} LIMIT 300`).all(id, id);
      const mem = R.prepare('SELECT entity_id, org_id FROM memberships WHERE entity_id=? OR org_id=? LIMIT 200').all(id, id);
      for (const r of rows) { if (seen.has('r' + r.id)) continue; seen.add('r' + r.id); const o = r.source_id === id ? r.target_id : r.source_id; add(o); next.push(o); const [sl, su] = evSource(r); edges.push({ from: r.source_id, to: r.target_id, type: r.type, source: r.source, dataset: r.dataset, confidence: r.confidence, quote: r.quote, source_label: sl, source_url: su }); }
      for (const m of mem) { const k = 'm' + m.entity_id + m.org_id; if (seen.has(k)) continue; seen.add(k); add(m.entity_id); add(m.org_id); next.push(m.entity_id === id ? m.org_id : m.entity_id); edges.push({ from: m.entity_id, to: m.org_id, type: 'member_of', source: 'podcast', dataset: 'real', confidence: 'stated' }); } }
    frontier = [...new Set(next)].slice(0, 150); }
  if (sel) { for (const id of [...nodes.keys()]) { for (const s of db.prepare("SELECT * FROM card_selectors WHERE entity_id=? AND status='accepted'").all(id)) { nodes.set('sel' + s.id, { id: 'sel' + s.id, name: s.value, kind: 'selector:' + s.kind, dataset: 'synthetic' }); edges.push({ from: id, to: 'sel' + s.id, type: s.parent_id ? 'paired' : 'uses', source: 'card', dataset: 'synthetic' }); } }
    for (const l of db.prepare("SELECT * FROM card_links WHERE status='accepted'").all()) if (nodes.has('sel' + l.a_id) && nodes.has('sel' + l.b_id)) edges.push({ from: 'sel' + l.a_id, to: 'sel' + l.b_id, type: l.relation, source: 'card', dataset: 'synthetic', quote: l.evidence }); }
  res.json({ nodes: [...nodes.values()], edges }); });
app.get('/api/investigations', (req, res) => res.json(db.prepare('SELECT id,name,owner,created_at FROM investigations ORDER BY id DESC').all()));
app.post('/api/investigations', A, (req, res) => { const r = db.prepare('INSERT INTO investigations(name,owner,data) VALUES (?,?,?)').run(req.body?.name || 'untitled', req.user.username, JSON.stringify(req.body?.data || {})); res.json({ id: r.lastInsertRowid }); });
app.get('/api/investigations/:id', (req, res) => { const r = db.prepare('SELECT * FROM investigations WHERE id=?').get(req.params.id); if (!r) return res.status(404).json({}); res.json({ ...r, data: JSON.parse(r.data) }); });
app.use('/api', memosRouter(db, R, requireRole));
// ---- admin
app.get('/api/users', requireRole('admin'), (_q, res) => res.json(db.prepare('SELECT id,username,role,created_at,last_login FROM users').all()));
app.post('/api/users', requireRole('admin'), (req, res) => { try { createUser(db, req.body.username, req.body.password, req.body.role); audit(req.user.username, 'user_create', req.body.username); res.json({ ok: true }); } catch (e) { res.status(400).json({ error: e.message }); } });
app.get('/api/audit', requireRole('instructor'), (_q, res) => res.json(db.prepare('SELECT * FROM audit ORDER BY id DESC LIMIT 300').all()));
app.use('/isw', express.static(join(ROOT, 'isw', 'images')));
app.use(express.static(join(HERE, 'public')));
app.listen(PORT, () => console.log(`afpak target tracker on :${PORT} (db ${AFPAK_DB})`));
