// Build a single self-contained, OFFLINE HTML snapshot of the GUI: boots server.mjs, pulls every API payload + the source
// tables the link chart needs, inlines vendor libs (maplibre, vis-network, mgrs), the offline Natural Earth basemap and
// photos as data URLs, and wires the in-browser shim (standalone/shim.js). Output: gui/dist/afpak-target-tracker-standalone.html
import { spawn } from 'node:child_process'; import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs'; import { join, dirname } from 'node:path'; import { fileURLToPath } from 'node:url';
import Database from 'better-sqlite3';
const HERE = dirname(fileURLToPath(import.meta.url)), GUI = join(HERE, '..'), ROOT = join(GUI, '..');
const DATA_DIR = process.env.DATA_DIR || join(GUI, 'data'), PW = process.env.ADMIN_PASSWORD || 'demo-pass-123', PORT = 3900 + Math.floor(Math.random() * 500), BASE = `http://127.0.0.1:${PORT}`;
const OUT = process.env.OUT || join(GUI, 'dist', 'afpak-target-tracker-standalone.html');
const proc = spawn(process.execPath, [join(GUI, 'server.mjs')], { env: { ...process.env, PORT: String(PORT), DATA_DIR, ADMIN_PASSWORD: PW }, stdio: ['ignore', 'inherit', 'inherit'] });
let cookie = '';
const api = async (path) => { const r = await fetch(BASE + path, { headers: { cookie } }); if (!r.ok) throw new Error(path + ' ' + r.status); return r.json(); };
try {
  const t0 = Date.now(); while (Date.now() - t0 < 60000) { try { if ((await fetch(BASE + '/api/health')).ok) break; } catch { } await new Promise(r => setTimeout(r, 300)); }
  const lr = await fetch(BASE + '/api/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ username: 'admin', password: PW }) }); cookie = lr.headers.get('set-cookie').split(';')[0];
  const health = await api('/api/health'); const meta = await api('/api/meta'); const targets = await api('/api/targets');
  const cards = {}, links = new Map(), poi = {}, memos = [];
  const photoCache = existsSync(join(GUI, 'standalone', 'photos.json')) ? JSON.parse(readFileSync(join(GUI, 'standalone', 'photos.json'), 'utf8')) : {}; // from standalone/fetch_photos.cjs
  const toDataUrl = async (src) => { if (photoCache[src]) return photoCache[src]; try { if (src.startsWith('/photos/')) { const f = join(DATA_DIR, src.slice(1)); const ext = f.split('.').pop().toLowerCase(); return `data:image/${ext === 'jpg' ? 'jpeg' : ext};base64,${readFileSync(f).toString('base64')}`; }
      if (/^https?:/.test(src)) { const r = await fetch(src, { headers: { 'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/137 Safari/537.36', accept: 'image/*,*/*' }, redirect: 'follow' }); if (!r.ok) { console.warn('photo fetch', r.status, src); return src; } const ct = r.headers.get('content-type') || 'image/jpeg'; return `data:${ct.split(';')[0]};base64,${Buffer.from(await r.arrayBuffer()).toString('base64')}`; } } catch (e) { console.warn('photo skipped', src, e.message); } return src; };
  for (const t of targets) { const c = await api('/api/targets/' + encodeURIComponent(t.id)); for (const l of c.links) { const { a_value, a_kind, a_entity, b_value, b_kind, b_entity, ...row } = l; links.set(row.id, row); } if (c.poi) poi[t.id] = c.poi;
    for (const f of c.fields) if (f.field === 'photo' && f.value) f.value = await toDataUrl(f.value);
    const { links: _l, poi: _p, ...rest } = c; cards[t.id] = rest;
    for (const m of await api(`/api/targets/${encodeURIComponent(t.id)}/memos`)) { const full = await api('/api/memos/' + m.id); const { kind_label, classification, text, ...row } = full; memos.push(row); } }
  const audit = await api('/api/audit'), rejections = await api('/api/rejections'), investigations = await api('/api/investigations');
  const events = await api('/api/events?synthetic=1&from=2001-01-01'), sites = await api('/api/sites');
  // source tables for the link chart + entity search
  const R = new Database(health.db, { readonly: true });
  const entities = R.prepare('SELECT id,name,kind,dataset,n_episodes,sources,role FROM entities').all(); const entityIdx = Object.fromEntries(entities.map(e => [e.id, e]));
  const aliasIdx = {}; for (const a of R.prepare('SELECT entity_id, alias FROM aliases').all()) (aliasIdx[a.entity_id] ||= []).push(a.alias);
  const relationships = R.prepare('SELECT id, source_id, target_id, type, source, confidence, dataset, substr(quote,1,160) quote, episode_idx, timestamp, doc_id FROM relationships').all(); const relIdx = {}; relationships.forEach((r, i) => { (relIdx[r.source_id] ||= []).push(i); (relIdx[r.target_id] ||= []).push(i); });
  const memberships = R.prepare('SELECT entity_id, org_id FROM memberships').all(); const memIdx = {}; memberships.forEach((m, i) => { (memIdx[m.entity_id] ||= []).push(i); (memIdx[m.org_id] ||= []).push(i); });
  const episodes = Object.fromEntries(R.prepare('SELECT idx, title, audio_url FROM episodes').all().map(e => [e.idx, e])); const documents = Object.fromEntries((R.prepare("SELECT 1 FROM sqlite_master WHERE name='documents'").get() ? R.prepare('SELECT doc_id, title, url FROM documents').all() : []).map(d => [d.doc_id, d]));
  const seq = {}; const mx = (k, rows) => seq[k] = rows.reduce((a, r) => Math.max(a, r.id || 0), 0);
  mx('card_fields', Object.values(cards).flatMap(c => c.fields)); mx('card_selectors', Object.values(cards).flatMap(c => c.selectors)); mx('card_hits', Object.values(cards).flatMap(c => c.hits)); mx('card_links', [...links.values()]); mx('memos', memos); mx('audit', audit); mx('rejections', rejections); mx('investigations', investigations);
  const bmPath = join(GUI, 'standalone', 'basemap.json'); if (!existsSync(bmPath)) throw new Error('standalone/basemap.json missing — run python3 standalone/build_basemap.py (see its docstring for the Natural Earth inputs)');
  const snap = { exported_at: new Date().toISOString(), meta, synUrl: 'https://github.com/StephanieHall-cog/CT-Use-Case-AF-Pak/blob/main/synthetic/targets_demo.json', cards, links: [...links.values()], poi, memos, audit, rejections, investigations, events, sites, entities, entityIdx, aliasIdx, relationships, relIdx, memberships, memIdx, episodes, documents, seq, basemap: JSON.parse(readFileSync(bmPath, 'utf8')) };
  const safe = s => s.replace(/<\/script/gi, '<\\/script').replace(/\u2028/g, '\\u2028').replace(/\u2029/g, '\\u2029');
  const V = f => readFileSync(join(GUI, 'standalone', 'vendor', f), 'utf8');
  let html = readFileSync(join(GUI, 'public', 'index.html'), 'utf8');
  html = html.replace(/<link href="https:\/\/unpkg\.com\/maplibre-gl[^>]*>/, `<style>${V('maplibre-gl.css')}</style>`)
    .replace(/<script src="https:\/\/unpkg\.com\/maplibre-gl[^>]*><\/script>/, `<script>${safe(V('maplibre-gl.js'))}</script>`)
    .replace(/<script src="https:\/\/unpkg\.com\/vis-network[^>]*><\/script>/, `<script>${safe(V('vis-network.min.js'))}</script>`)
    .replace(/<script src="https:\/\/unpkg\.com\/mgrs[^>]*><\/script>/, `<script>${safe(V('mgrs.js'))}</script>`);
  if (/unpkg\.com/.test(html)) throw new Error('a CDN reference survived: ' + html.match(/https:\/\/unpkg\.com[^"']*/)[0]);
  const core = readFileSync(join(GUI, 'lib', 'memo_core.mjs'), 'utf8').replace(/^export (const|function) /gm, '$1 ').replace(/^export \{[^}]*\};?$/gm, '').replace("const mgrsLib = globalThis.mgrs || (await import('mgrs')).default;", 'const mgrsLib = globalThis.mgrs;');
  const banner = `<div class="banner" style="background:#1d3b55;color:#dbeafe">STANDALONE OFFLINE SNAPSHOT — exported ${snap.exported_at.slice(0, 16).replace('T', ' ')}Z from the AfPak Target Tracker; no server or network needed. Edits you make are saved in this browser only. <button class="sm" onclick="if(confirm('Discard all edits made in this browser and reload the snapshot?'))__standalone.reset()">Reset edits</button></div>`;
  html = html.replace('<body>', `<body>${banner}<script>window.__SNAPSHOT__=${safe(JSON.stringify(snap))};</script><script>${safe(readFileSync(join(GUI, 'standalone', 'shim.js'), 'utf8'))}</script><script type="module">${safe(core)}\nwindow.MemoCore={KINDS,CLASSIFICATION,KIND_LABEL,toMgrs,makeCard,prevList,citeText,buildTemplateData,profileBodyText,normaliseMemo,parseMemo,memoText};</script>`)
    .replace('<script src="memos.js" defer></script>', `<script>${safe(readFileSync(join(GUI, 'public', 'memos.js'), 'utf8'))}</script>`)
    .replace(/<title>[^<]*<\/title>/, '<title>AfPak Target Tracker — standalone offline snapshot (UNCLASSIFIED demo)</title>');
  mkdirSync(dirname(OUT), { recursive: true }); writeFileSync(OUT, html);
  console.log(`wrote ${OUT} (${(html.length / 1e6).toFixed(1)} MB): ${targets.length} cards, ${events.features.length} events, ${sites.features.length} sites, ${memos.length} memos, ${entities.length} entities, ${relationships.length} relationships`);
} finally { proc.kill(); }
