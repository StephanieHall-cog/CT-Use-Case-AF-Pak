// Standalone-snapshot shim: intercepts fetch('/api/...') and serves it from the embedded snapshot (window.__SNAPSHOT__),
// applying analyst writes in memory and persisting them as an ops log in localStorage (replayed on load). Also swaps the
// online basemap for the embedded offline Natural Earth style. Loaded BEFORE the app script; the app itself is unchanged.
(function () {
  const D = window.__SNAPSHOT__; const LS = 'afpak-standalone-ops-v1';
  const ME = { id: 1, username: 'demo-analyst', role: 'analyst' };
  const TBL = { fields: 'card_fields', selectors: 'card_selectors', links: 'card_links', hits: 'card_hits' };
  const CITE = D.meta.citeCodes; const SYN_DATE = '2026-10-14';
  const now = () => new Date().toISOString().replace('T', ' ').slice(0, 19);
  const codeOf = (c = '', u = '') => /SYNTHETIC/i.test(c) ? 'SYN' : /UN 1988|Security Council|un\.org/i.test(c + u) ? 'UNS' : /FBI/i.test(c + u) ? 'FBI' : /Generation Jihad|podcast|redcircle/i.test(c + u) ? 'GJP' : /ISW/i.test(c) ? 'ISW' : /document/i.test(c) ? 'DOC' : /Auto-citation|algorithm/i.test(c) ? 'ALG' : /Public reference/i.test(c) ? 'PUB' : 'ANL';
  const deriveCite = (c, u, x = {}) => { const src = String(x.src || codeOf(c || '', u || '')).toUpperCase().slice(0, 3); const d = CITE[src] || {}; const t = +x.trust || d.trust || 3; return { cit_src: src, cit_pub: x.pub || d.pub || src, cit_date: (x.date || '').slice(0, 10) || (src === 'SYN' ? SYN_DATE : new Date().toISOString().slice(0, 10)), cit_trust: Math.min(4, Math.max(1, t)) }; };
  const hasCite = b => !!((b.citation || '').trim() || (b.cit_pub || '').trim() || b.cit_src);
  const citeText = b => (b.citation || '').trim() || [b.cit_pub, b.cit_date].filter(Boolean).join(', ');
  const citeX = b => ({ src: b.cit_src, pub: b.cit_pub, date: b.cit_date, trust: b.cit_trust });

  // ---- state (deep copy of snapshot so replay is deterministic)
  const S = JSON.parse(JSON.stringify({ cards: D.cards, links: D.links, memos: D.memos, audit: D.audit, rejections: D.rejections, investigations: D.investigations, poi: D.poi, seq: D.seq }));
  const T = { card_fields: () => Object.values(S.cards).flatMap(c => c.fields), card_selectors: () => Object.values(S.cards).flatMap(c => c.selectors), card_hits: () => Object.values(S.cards).flatMap(c => c.hits), card_links: () => S.links };
  const find = (tbl, id) => T[tbl]().find(r => r.id === +id);
  const nextId = k => (S.seq[k] = (S.seq[k] || 0) + 1);
  const selById = id => T.card_selectors().find(s => s.id === +id);
  const audit = (action, target, before, after) => S.audit.unshift({ id: nextId('audit'), ts: now(), user: ME.username, action, target: target == null ? null : String(target), before: before == null ? null : JSON.stringify(before), after: after == null ? null : JSON.stringify(after) });
  const ensureCard = id => S.cards[id] || (S.cards[id] = { entity: { id, name: id, dataset: 'synthetic' }, fields: [], selectors: [], hits: [], relationships: [], profiles: [], mentions: [], events: [] });
  const nameOf = id => S.cards[id]?.fields.find(f => f.field === 'name' && f.status === 'accepted')?.value || S.cards[id]?.entity?.name || id;
  const linkRow = l => { const a = selById(l.a_id) || {}, b = selById(l.b_id) || {}; return { ...l, a_value: a.value, a_kind: a.kind, a_entity: a.entity_id, b_value: b.value, b_kind: b.kind, b_entity: b.entity_id }; };
  const fingerprint = (tbl, r) => tbl === 'card_links' ? `${r.a_id}|${r.b_id}|${r.relation}` : `${r.entity_id}|${r.field || r.kind}|${r.value || r.ts}`;

  // ---- ops: every write goes through apply(op) so it can be replayed from localStorage
  const ops = []; let replaying = false;
  function record(op) { if (!replaying) { ops.push(op); try { localStorage.setItem(LS, JSON.stringify(ops)); } catch (e) { console.warn('localStorage full — edits kept for this page view only', e); } } }
  const E = (code, error) => ({ status: code, body: { error } });
  const OK = body => ({ status: 200, body });
  function apply(op) {
    const b = op.body || {}, p = op.params || {}; let r;
    switch (op.kind) {
      case 'field_add': { if (!D.meta.cardFields.some(f => f[0] === b.field)) return E(400, 'unknown field'); if (b.value && !hasCite(b)) return E(400, 'citation required');
        const c = ensureCard(p.id); r = { id: nextId('card_fields'), entity_id: p.id, field: b.field, value: b.value || '', citation: citeText(b), citation_url: b.citation_url || null, status: b.status || 'accepted', proposed_by: b.proposed_by || 'analyst', edited_by: ME.username, edited_at: op.ts, reidentified: 0, ...deriveCite(citeText(b), b.citation_url, citeX(b)) }; c.fields.push(r); audit('field_add', r.id, null, b); return OK({ id: r.id }); }
      case 'selector_add': { if (!D.meta.selKinds.includes(b.kind) || !b.value) return E(400, 'kind/value required'); if (!hasCite(b)) return E(400, 'citation required');
        const c = ensureCard(p.id); r = { id: nextId('card_selectors'), entity_id: p.id, kind: b.kind, value: b.value, parent_id: b.parent_id || null, platform: b.platform || null, label: b.label || null, citation: citeText(b), citation_url: b.citation_url || null, status: b.status || 'accepted', proposed_by: b.proposed_by || 'analyst', edited_by: ME.username, edited_at: op.ts, src_id: null, reidentified: 0, ...deriveCite(citeText(b), b.citation_url, citeX(b)) }; c.selectors.push(r); audit('selector_add', r.id, null, b); return OK({ id: r.id }); }
      case 'link_add': { if (!b.a_id || !b.b_id || !b.relation) return E(400, 'a_id, b_id, relation required'); if (!hasCite(b)) return E(400, 'citation required');
        r = { id: nextId('card_links'), a_id: +b.a_id, b_id: +b.b_id, relation: b.relation, evidence: b.evidence || '', citation: citeText(b), citation_url: b.citation_url || null, status: b.status || 'accepted', proposed_by: b.proposed_by || 'analyst', edited_by: ME.username, edited_at: op.ts, reidentified: 0, ...deriveCite(citeText(b), b.citation_url, citeX(b)) }; S.links.push(r); audit('link_add', r.id, null, b); return OK({ id: r.id }); }
      case 'hit_add': { if (!b.ts || b.lat == null || b.lon == null) return E(400, 'ts, lat, lon required'); if (!hasCite(b)) return E(400, 'citation required');
        const c = ensureCard(p.id); r = { id: nextId('card_hits'), entity_id: p.id, kind: b.kind || 'other', ts: b.ts, lat: +b.lat, lon: +b.lon, precision_km: b.precision_km == null ? null : +b.precision_km, place: b.place || null, detail: b.detail || null, selector_id: b.selector_id || null, citation: citeText(b), citation_url: b.citation_url || null, status: b.status || 'accepted', proposed_by: b.proposed_by || 'analyst', edited_by: ME.username, edited_at: op.ts, reidentified: 0, ...deriveCite(citeText(b), b.citation_url, citeX(b)) }; c.hits.push(r); c.hits.sort((x, y) => x.ts < y.ts ? 1 : -1); audit('hit_add', r.id, null, b); return OK({ id: r.id }); }
      case 'photo_add': { if (!/^data:image\//.test(b.data || '')) return E(400, 'image data URL required'); if (!hasCite(b)) return E(400, 'citation required');
        const c = ensureCard(p.id); r = { id: nextId('card_fields'), entity_id: p.id, field: 'photo', value: b.data, citation: citeText(b), citation_url: b.citation_url || null, status: 'accepted', proposed_by: 'analyst', edited_by: ME.username, edited_at: op.ts, reidentified: 0, ...deriveCite(citeText(b), b.citation_url, citeX(b)) }; c.fields.push(r); audit('photo_add', r.id, null, { citation: b.citation }); return OK({ id: r.id, url: b.data }); }
      case 'update': { const row = find(p.tbl, p.id); if (!row) return E(404, 'not found');
        if (b.cit_trust != null && b.cit_trust !== '' && !(+b.cit_trust >= 1 && +b.cit_trust <= 4)) return E(400, 'trust must be 1-4');
        if (b.status === 'rejected' && !(b.reject_comment || '').trim()) return E(400, 'rejection comment required');
        const before = { ...row }; for (const k of ['value', 'citation', 'citation_url', 'status', 'parent_id', 'platform', 'label', 'relation', 'evidence', 'kind', 'ts', 'lat', 'lon', 'precision_km', 'place', 'detail', 'selector_id', 'reject_comment']) if (b[k] !== undefined) row[k] = b[k];
        if (['cit_src', 'cit_pub', 'cit_date', 'cit_trust', 'citation'].some(k => b[k] !== undefined)) Object.assign(row, deriveCite(row.citation, row.citation_url, { src: b.cit_src ?? row.cit_src, pub: b.cit_pub ?? row.cit_pub, date: b.cit_date ?? row.cit_date, trust: b.cit_trust ?? row.cit_trust }));
        if (b.status === 'rejected') { row.rejected_by = ME.username; row.rejected_at = op.ts; S.rejections.unshift({ id: nextId('rejections'), tbl: p.tbl, row_id: row.id, entity_id: row.entity_id || null, fingerprint: fingerprint(p.tbl, row), comment: b.reject_comment.trim(), user: ME.username, ts: op.ts }); }
        row.edited_by = ME.username; row.edited_at = op.ts; audit(p.tbl + (b.status === 'rejected' ? '_reject' : b.status === 'accepted' && before.status !== 'accepted' ? '_accept' : '_edit'), row.id, before, b); return OK({ ok: true }); }
      case 'delete': { const row = find(p.tbl, p.id); if (!row) return E(404, 'not found'); for (const c of Object.values(S.cards)) for (const k of ['fields', 'selectors', 'hits']) c[k] = c[k].filter(x => x !== row); S.links = S.links.filter(l => l !== row && !(p.tbl === 'card_selectors' && (l.a_id === row.id || l.b_id === row.id))); audit(p.tbl + '_delete', p.id, row, null); return OK({ ok: true }); }
      case 'bulk': { const items = Array.isArray(b.items) ? b.items : []; if (!['accepted', 'rejected', 'proposed'].includes(b.status)) return E(400, 'status must be accepted / rejected / proposed'); if (b.status === 'rejected' && !(b.reject_comment || '').trim()) return E(400, 'rejection comment required');
        let n = 0; const errors = []; for (const it of items) { if (!T[it.tbl]) { errors.push({ ...it, error: 'bad table' }); continue; } const x = apply({ kind: 'update', ts: op.ts, params: { tbl: it.tbl, id: it.id }, body: { status: b.status, reject_comment: b.reject_comment } }); x.status === 200 ? n++ : errors.push({ ...it, error: x.body.error }); } audit('proposals_bulk', null, null, { status: b.status, n, comment: b.reject_comment }); return OK({ updated: n, errors }); }
      case 'poi': { S.poi[p.id] = { entity_id: p.id, on_: b.on ? 1 : 0, priority: b.priority || 'Medium', reason: b.reason || '', by_user: ME.username, at: op.ts }; audit('poi', p.id, null, b); return OK({ ok: true }); }
      case 'target_create': { if (!b.name) return E(400, 'name required'); const id = 'SP-' + op.ts.replace(/\D/g, '').slice(-9) + Math.floor(Math.random() * 1e4).toString(36); const c = ensureCard(id); c.fields.push({ id: nextId('card_fields'), entity_id: id, field: 'name', value: b.name, citation: citeText(b) || 'Analyst entry', citation_url: b.citation_url || null, status: 'accepted', proposed_by: 'analyst', edited_by: ME.username, edited_at: op.ts, reidentified: 0, ...deriveCite(citeText(b) || 'Analyst entry', b.citation_url, citeX(b)) }); audit('target_create', id, null, b); return OK({ id }); }
      case 'algorithm_run': { let n = 0, m = 0; const reid = row => { row.reidentified = (row.reidentified || 0) + 1; row.last_identified = op.ts; m++; };
        for (const [id, c] of Object.entries(S.cards)) for (const pr of c.profiles || []) { let al = []; try { al = (JSON.parse(pr.raw || '{}').aliases || []).map(a => a.name || a); } catch { }
          for (const a of al) { const ex = c.fields.find(f => ['name_variations', 'kunyah'].includes(f.field) && f.value === a); if (ex) { if (ex.status === 'rejected') reid(ex); continue; }
            const cit = `Auto-citation: ${D.meta.sources[pr.source]} ${pr.reference} (alias field)`, url = pr.url || (pr.source === 'fbi_wanted' ? 'https://www.fbi.gov/wanted/terrorism' : 'https://main.un.org/securitycouncil/en/sanctions/1988/materials');
            c.fields.push({ id: nextId('card_fields'), entity_id: id, field: 'name_variations', value: a, citation: cit, citation_url: url, status: 'proposed', proposed_by: 'algorithm:profile-alias-matcher', edited_by: 'algorithm', edited_at: op.ts, reidentified: 0, ...deriveCite(cit, url, { date: ((pr.last_updated || '').split(';').pop().trim() || pr.listed_on || '').slice(0, 10) || undefined, trust: 4 }) }); n++; } }
        const groups = {}; for (const s of T.card_selectors()) if (s.status === 'accepted' && ['imei', 'imsi', 'phone', 'email', 'pushtoken'].includes(s.kind)) (groups[s.kind + '|' + s.value] ||= []).push(s);
        for (const g of Object.values(groups)) { if (new Set(g.map(s => s.entity_id)).size < 2) continue; const [a, b2] = g; const ex = S.links.find(l => l.a_id === a.id && l.b_id === b2.id); if (ex) { if (ex.status === 'rejected') reid(ex); continue; }
          const cit = 'Auto-citation: selector table cross-match'; S.links.push({ id: nextId('card_links'), a_id: a.id, b_id: b2.id, relation: 'shared_selector', evidence: `Same ${a.kind} value appears on two targets`, citation: cit, citation_url: null, status: 'proposed', proposed_by: 'algorithm:selector-correlator', edited_by: 'algorithm', edited_at: op.ts, reidentified: 0, ...deriveCite(cit, null, { src: 'ALG' }) }); n++; }
        audit('algorithm_run', null, null, { proposals: n, reidentified: m }); return OK({ proposals: n, reidentified: m }); }
      case 'investigation_add': { const inv = { id: nextId('investigations'), name: b.name || 'untitled', owner: ME.username, data: b.data || {}, created_at: op.ts }; S.investigations.unshift(inv); return OK({ id: inv.id }); }
      case 'memo_add': { const MC = window.MemoCore; const prevRows = memoRows(p.id); const nm = MC.normaliseMemo(b, p.id, ME.username, prevRows); if (nm.error) return E(400, nm.error); const row = { id: nextId('memos'), ...nm.row, created_at: op.ts }; S.memos.push(row); const saved = MC.parseMemo(row); audit('memo_create', p.id, null, { id: row.id, kind: row.kind, subject: row.subject }); return OK(saved); }
    }
    return E(400, 'unknown op');
  }
  const memoRows = eid => S.memos.filter(m => m.entity_id === eid).sort((a, b) => a.created_at < b.created_at ? 1 : a.created_at > b.created_at ? -1 : b.id - a.id).map(m => ({ id: m.id, kind: m.kind, subject: m.subject, created_by: m.created_by, created_at: m.created_at }));
  function write(kind, params, body) { const op = { kind, ts: now(), params, body }; const r = apply(op); if (r.status === 200) record(op); return r; }
  // replay persisted ops
  try { const saved = JSON.parse(localStorage.getItem(LS) || '[]'); replaying = true; for (const op of saved) { apply(op); ops.push(op); } replaying = false; } catch (e) { console.warn('could not replay saved edits', e); replaying = false; }

  // ---- reads
  const accepted = rows => rows.filter(r => r.status === 'accepted');
  function targetsList(q, ds) {
    const out = Object.entries(S.cards).map(([id, c]) => { const F = accepted(c.fields); const g = f => F.filter(x => x.field === f).map(x => x.value); const hits = accepted(c.hits).slice().sort((a, b) => a.ts < b.ts ? 1 : -1); const last = hits[0]; const poi = S.poi[id];
      return { id, name: g('name')[0] || c.entity.name, dataset: c.entity.dataset, objective: g('objective_name')[0], network: g('network'), tribe: g('tribe')[0], role: g('role')[0], aliases: [...g('kunyah'), ...g('name_variations')].slice(0, 6), photo: g('photo').slice(-1)[0] || null, n_episodes: c.entity.n_episodes, sources: c.entity.sources,
        n_selectors: accepted(c.selectors).length, n_hits: hits.length, n_proposed: [...c.fields, ...c.selectors, ...c.hits].filter(x => x.status === 'proposed').length, last_hit: last ? { kind: last.kind, ts: last.ts, place: last.place, lat: last.lat, lon: last.lon } : null, poi: poi?.on_ ? poi : null }; });
    return out.filter(t => !q || JSON.stringify(t).toLowerCase().includes(q.toLowerCase())).filter(t => !ds || t.dataset === ds);
  }
  function cardOut(id) { const c = S.cards[id]; if (!c) return null; const links = S.links.filter(l => { const a = selById(l.a_id), b = selById(l.b_id); return a && b && (a.entity_id === id || b.entity_id === id); }).map(linkRow);
    return { entity: c.entity, fields: c.fields.slice().sort((a, b) => a.field < b.field ? -1 : a.field > b.field ? 1 : a.id - b.id), selectors: c.selectors.slice().sort((a, b) => (a.parent_id || a.id) - (b.parent_id || b.id) || (a.parent_id ? 1 : 0) - (b.parent_id ? 1 : 0) || a.id - b.id), links, hits: c.hits.slice().sort((a, b) => a.ts < b.ts ? 1 : -1), relationships: c.relationships, profiles: c.profiles, mentions: c.mentions, events: c.events, poi: S.poi[id] || null }; }
  function hitsGeo(entity) { const rows = []; for (const [id, c] of Object.entries(S.cards)) if (!entity || entity === id) for (const h of accepted(c.hits)) rows.push({ ...h, name: nameOf(id), objective: accepted(c.fields).find(f => f.field === 'objective_name')?.value }); rows.sort((a, b) => a.ts < b.ts ? -1 : 1); const last = {}; for (const r of rows) last[r.entity_id] = r.id;
    return { type: 'FeatureCollection', features: rows.map(r => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [r.lon, r.lat] }, properties: { ...r, is_last: last[r.entity_id] === r.id ? 1 : 0, source_label: r.citation, source_url: r.citation_url } })) }; }
  function proposals() { const withName = r => ({ ...r, name: nameOf(r.entity_id) }); const by = (tbl, st) => T[tbl]().filter(r => r.status === st);
    return { fields: by('card_fields', 'proposed').map(withName), selectors: by('card_selectors', 'proposed').map(withName), links: by('card_links', 'proposed').map(linkRow), hits: by('card_hits', 'proposed').map(withName),
      rejected: [...['card_fields', 'card_selectors', 'card_hits'].flatMap(t => by(t, 'rejected').map(r => ({ ...withName(r), tbl: t }))), ...by('card_links', 'rejected').map(l => ({ ...linkRow(l), tbl: 'card_links' }))].sort((a, b) => ((b.last_identified || b.rejected_at || '') > (a.last_identified || a.rejected_at || '') ? 1 : -1)) }; }
  const evSource = r => { if (r.dataset === 'synthetic') return [D.meta.sources.synthetic, D.synUrl]; if (r.episode_idx != null) { const e = D.episodes[r.episode_idx]; return [`${D.meta.sources.podcast} — ep. ${r.episode_idx} ${e?.title || ''} @ ${r.timestamp || ''}`, e?.audio_url || 'https://redcircle.com/shows/generation-jihad']; } if (r.doc_id) { const d = D.documents[r.doc_id]; return [`${D.meta.sources.document} — ${d?.title || r.doc_id} (${r.timestamp || ''})`, d?.url || null]; } return [D.meta.sources[r.source] || r.source || 'unknown', null]; };
  function graph(root, depth, syn, sel) { const ent = D.entityIdx; const nodes = new Map(), edges = []; const add = id => { if (nodes.has(id)) return; nodes.set(id, ent[id] || { id, name: nameOf(id), kind: 'person', dataset: 'synthetic' }); }; add(root); const seen = new Set(); let frontier = [root];
    for (let d = 0; d < depth; d++) { const next = []; for (const id of frontier) { const rows = (D.relIdx[id] || []).map(i => D.relationships[i]).filter(r => syn || r.dataset === 'real').slice(0, 300); for (const r of rows) { if (seen.has('r' + r.id)) continue; seen.add('r' + r.id); const o = r.source_id === id ? r.target_id : r.source_id; add(o); next.push(o); const [sl, su] = evSource(r); edges.push({ from: r.source_id, to: r.target_id, type: r.type, source: r.source, dataset: r.dataset, confidence: r.confidence, quote: r.quote, source_label: sl, source_url: su }); }
        for (const m of (D.memIdx[id] || []).map(i => D.memberships[i]).slice(0, 200)) { const k = 'm' + m.entity_id + m.org_id; if (seen.has(k)) continue; seen.add(k); add(m.entity_id); add(m.org_id); next.push(m.entity_id === id ? m.org_id : m.entity_id); edges.push({ from: m.entity_id, to: m.org_id, type: 'member_of', source: 'podcast', dataset: 'real', confidence: 'stated' }); } } frontier = [...new Set(next)].slice(0, 150); }
    if (sel) { for (const id of [...nodes.keys()]) for (const s of accepted(S.cards[id]?.selectors || [])) { nodes.set('sel' + s.id, { id: 'sel' + s.id, name: s.value, kind: 'selector:' + s.kind, dataset: 'synthetic' }); edges.push({ from: id, to: 'sel' + s.id, type: s.parent_id ? 'paired' : 'uses', source: 'card', dataset: 'synthetic' }); }
      for (const l of accepted(S.links)) if (nodes.has('sel' + l.a_id) && nodes.has('sel' + l.b_id)) edges.push({ from: 'sel' + l.a_id, to: 'sel' + l.b_id, type: l.relation, source: 'card', dataset: 'synthetic', quote: l.evidence }); }
    return { nodes: [...nodes.values()], edges }; }
  const search = q => { q = (q || '').toLowerCase(); const hit = new Map(); for (const e of D.entities) if (e.name.toLowerCase().includes(q)) hit.set(e.id, e); for (const [id, al] of Object.entries(D.aliasIdx)) if (!hit.has(id) && al.some(a => a.toLowerCase().includes(q)) && D.entityIdx[id]) hit.set(id, D.entityIdx[id]); return [...hit.values()].sort((a, b) => (b.n_episodes || 0) - (a.n_episodes || 0)).slice(0, 40); };

  // ---- router
  async function route(method, url, body) {
    const u = new URL(url, 'http://standalone.local'); const p = u.pathname, q = Object.fromEntries(u.searchParams); let m;
    if (p === '/api/health') return OK({ ok: true, db: 'standalone snapshot' });
    if (p === '/api/login' || p === '/api/me') return OK(ME); if (p === '/api/logout') return OK({ ok: true });
    if (p === '/api/meta') return OK({ ...D.meta, db: 'standalone snapshot (' + D.exported_at.slice(0, 10) + ')' });
    if (p === '/api/targets' && method === 'GET') return OK(targetsList(q.q, q.dataset));
    if (p === '/api/targets' && method === 'POST') return write('target_create', {}, body);
    if (p === '/api/entities/search') return OK(search(q.q));
    if (p === '/api/events') return OK(D.events); if (p === '/api/sites') return OK(D.sites); if (p === '/api/hits') return OK(hitsGeo(q.entity)); if (p === '/api/maps') return OK([]);
    if (p === '/api/proposals') return OK(proposals()); if (p === '/api/proposals/bulk') return write('bulk', {}, body);
    if (p === '/api/algorithms/run') return write('algorithm_run', {}, body);
    if (p === '/api/graph') return q.root ? OK(graph(q.root, Math.min(+q.depth || 1, 2), q.synthetic !== '0', q.selectors === '1')) : E(400, 'root required');
    if (p === '/api/investigations' && method === 'GET') return OK(S.investigations.map(i => ({ id: i.id, name: i.name, owner: i.owner, created_at: i.created_at }))); if (p === '/api/investigations') return write('investigation_add', {}, body);
    if ((m = p.match(/^\/api\/investigations\/(\d+)$/))) { const i = S.investigations.find(x => x.id === +m[1]); return i ? OK(i) : E(404, 'not found'); }
    if (p === '/api/users') return OK([{ id: 1, username: ME.username, role: ME.role, created_at: D.exported_at, last_login: now() }]); if (p === '/api/audit') return OK(S.audit.slice(0, 300));
    if (p === '/api/rejections') return OK(S.rejections.filter(r => (!q.tbl || r.tbl === q.tbl) && (!q.id || r.row_id === +q.id) && (!q.entity || r.entity_id === q.entity)).slice(0, 200));
    if (p === '/api/links' && method === 'POST') return write('link_add', {}, body);
    if ((m = p.match(/^\/api\/(fields|selectors|links|hits)\/(\d+)$/))) return method === 'PATCH' ? write('update', { tbl: TBL[m[1]], id: +m[2] }, body) : method === 'DELETE' ? write('delete', { tbl: TBL[m[1]], id: +m[2] }, body) : E(405, 'method');
    if ((m = p.match(/^\/api\/targets\/([^/]+)\/(fields|selectors|hits|photo|poi|memos|memo-template)$/))) { const id = decodeURIComponent(m[1]), what = m[2];
      if (what === 'memo-template') { const MC = await memoCore(); const c = S.cards[id]; if (!c) return E(404, 'not found'); const card = MC.makeCard(id, accepted(c.fields), accepted(c.selectors), accepted(c.hits).slice().sort((a, b) => a.ts < b.ts ? 1 : -1), c.entity); try { return OK(MC.buildTemplateData(card, MC.prevList(memoRows(id)), id, String(q.kind || 'profile'), ME.username)); } catch (e) { return E(e.status || 500, e.message); } }
      if (what === 'memos' && method === 'GET') { const MC = await memoCore(); return OK(memoRows(id).map(r => ({ ...S.memos.find(x => x.id === r.id), kind_label: MC.KIND_LABEL[r.kind] })).map(({ sections, refs, sources, body, summary, ...rest }) => rest)); }
      if (what === 'memos') { await memoCore(); return write('memo_add', { id }, body); }
      return write({ fields: 'field_add', selectors: 'selector_add', hits: 'hit_add', photo: 'photo_add', poi: 'poi' }[what], { id }, body); }
    if ((m = p.match(/^\/api\/targets\/([^/]+)$/))) { const c = cardOut(decodeURIComponent(m[1])); return c ? OK(c) : E(404, 'not found'); }
    if ((m = p.match(/^\/api\/memos\/(\d+)$/))) { const MC = await memoCore(); const row = S.memos.find(x => x.id === +m[1]); if (!row) return E(404, 'not found'); const mm = MC.parseMemo(row); return OK({ ...mm, kind_label: MC.KIND_LABEL[mm.kind], classification: MC.CLASSIFICATION, text: MC.memoText(row) }); }
    return E(404, 'no such route in standalone snapshot: ' + p);
  }
  const memoCore = () => window.MemoCore ? Promise.resolve(window.MemoCore) : new Promise(res => { const t = setInterval(() => { if (window.MemoCore) { clearInterval(t); res(window.MemoCore); } }, 30); });
  const realFetch = window.fetch.bind(window);
  window.fetch = async function (input, init = {}) { const url = typeof input === 'string' ? input : input.url; if (!/^(\/api\/|\.\/api\/)/.test(url) && !url.startsWith(location.origin + '/api/')) return realFetch(input, init);
    let body = null; try { body = init.body ? JSON.parse(init.body) : null; } catch { } const r = await route((init.method || 'GET').toUpperCase(), url.replace(location.origin, ''), body);
    return new Response(JSON.stringify(r.body), { status: r.status, headers: { 'content-type': 'application/json' } }); };

  // ---- offline basemap: swap any remote style for the embedded Natural Earth layers
  const BM = D.basemap; const offlineStyle = { version: 8, name: 'offline-afpak', glyphs: 'offline://glyphs/{fontstack}/{range}.pbf', sources: { countries: { type: 'geojson', data: BM.countries }, provinces: { type: 'geojson', data: BM.provinces }, rivers: { type: 'geojson', data: BM.rivers }, lakes: { type: 'geojson', data: BM.lakes }, places: { type: 'geojson', data: BM.places } },
    layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#0b0f14' } }, { id: 'land', type: 'fill', source: 'countries', paint: { 'fill-color': '#151c25' } }, { id: 'lakes', type: 'fill', source: 'lakes', paint: { 'fill-color': '#0e1a2a' } }, { id: 'rivers', type: 'line', source: 'rivers', paint: { 'line-color': '#1d3350', 'line-width': 0.8 } },
      { id: 'prov', type: 'line', source: 'provinces', paint: { 'line-color': '#2a3646', 'line-width': 0.6, 'line-dasharray': [2, 2] } }, { id: 'borders', type: 'line', source: 'countries', paint: { 'line-color': '#55667a', 'line-width': 1.2 } }, { id: 'places', type: 'circle', source: 'places', paint: { 'circle-radius': ['case', ['<=', ['get', 'rank'], 2], 4, 2.5], 'circle-color': '#8b98a5' } }] };
  window.__offlineStyle = offlineStyle; // labels need glyphs; the app draws its own labels only where a font stack is available, so place names are drawn as HTML markers by addPlaceLabels()
  // no glyph server offline -> symbol layers are replaced by HTML markers that evaluate the layer's text-field / filter
  const evalX = (x, p) => Array.isArray(x) ? (x[0] === 'get' ? p[x[1]] : x[0] === 'concat' ? x.slice(1).map(y => evalX(y, p)).join('') : x[0] === '==' ? evalX(x[1], p) == evalX(x[2], p) : x[0] === 'literal' ? x[1] : x) : x;
  function htmlLabels(m, layer) { let marks = []; const draw = () => { marks.forEach(k => k.remove()); marks = []; const src = m.getSource(layer.source); const data = src && src._data; if (!data || !data.features) return; if (layer.minzoom && m.getZoom() < layer.minzoom) return;
      for (const f of data.features) { const p = f.properties || {}; if (layer.filter && !evalX(layer.filter, p)) continue; const txt = evalX(layer.layout?.['text-field'], p); if (!txt) continue; const el = document.createElement('div'); el.textContent = txt; el.style.cssText = `font:${layer.layout?.['text-size'] || 10}px system-ui;color:${layer.paint?.['text-color'] || '#ddd'};text-shadow:0 0 3px #000,0 0 3px #000;pointer-events:none;white-space:nowrap`; marks.push(new maplibregl.Marker({ element: el, anchor: 'top', offset: [0, 8] }).setLngLat(f.geometry.coordinates).addTo(m)); } };
    m.on('sourcedata', e => { if (e.sourceId === layer.source) draw(); }); m.on('zoomend', draw); draw(); }
  const wrap = () => { if (!window.maplibregl || maplibregl.__offline) return; const Orig = maplibregl.Map; maplibregl.Map = function (opts) { const m = new Orig({ ...opts, style: offlineStyle, attributionControl: false }); const addLayer = m.addLayer.bind(m); m.addLayer = (layer, before) => { if (layer.type === 'symbol') { htmlLabels(m, layer); return m; } return addLayer(layer, before); };
      const setLayout = m.setLayoutProperty.bind(m); m.setLayoutProperty = (id, k, v) => m.getLayer(id) ? setLayout(id, k, v) : m;
      m.on('load', () => { try { m.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: BM.attribution })); } catch { } addPlaceLabels(m); }); return m; }; maplibregl.Map.prototype = Orig.prototype; maplibregl.__offline = true; };
  function addPlaceLabels(m) { const feats = BM.places.features.filter(f => f.properties.rank <= 4); const els = feats.map(f => { const el = document.createElement('div'); el.textContent = f.properties.name; el.style.cssText = 'font:10px system-ui;color:#aab4c0;text-shadow:0 0 3px #000,0 0 3px #000;pointer-events:none;white-space:nowrap;transform:translate(6px,-6px)'; return new maplibregl.Marker({ element: el, anchor: 'left' }).setLngLat(f.geometry.coordinates).addTo(m); });
    const upd = () => { const z = m.getZoom(); els.forEach((mk, i) => mk.getElement().style.display = feats[i].properties.rank <= (z < 5 ? 1 : z < 6.5 ? 2 : 4) ? '' : 'none'); }; m.on('zoom', upd); upd(); }
  if (window.maplibregl) wrap(); else document.addEventListener('DOMContentLoaded', wrap);
  window.__standalone = { reset() { localStorage.removeItem(LS); location.reload(); }, ops, state: S };
})();
