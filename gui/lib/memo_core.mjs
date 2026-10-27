// Pure memo-template logic shared by the server (lib/memos.mjs) and the standalone HTML snapshot (no DB, no express).
// `mgrs` comes from the UMD global in the browser or from the npm package in Node.
const mgrsLib = globalThis.mgrs || (await import('mgrs')).default;

export const KINDS = ['profile', 'location', 'burn', 'threat'];
export const CLASSIFICATION = 'UNCLASSIFIED // DEMO';
export const KIND_LABEL = { profile: 'Profile of the Target', location: 'Location update on Target', burn: 'Burn Notice', threat: 'Threat Notice' };
export const FIELD_LABEL = {
  name: 'Name', name_variations: 'Name variations', kunyah: 'Kunyah / call sign / nicknames', objective_name: 'Objective name', tribe: 'Tribe affiliation', religion: 'Religion',
  network: 'Terrorist network', role: 'Role in government / network', dob: 'Date of birth', pob: 'Place of birth', passport: 'Passport number', cnic: 'CNIC or ID number', visa: 'Visa number',
  bdl: 'Bed Down Location (BDL)', addresses: 'Addresses or alternate known locations', travel: 'Travel', vehicle: 'Car make / model', family: 'Family members', physical: 'Physical descriptors', notes: 'Additional notes' };
const GROUPS = [['Identity', ['name', 'name_variations', 'kunyah', 'objective_name']], ['Affiliation', ['network', 'role', 'tribe', 'religion']],
  ['Biodata', ['dob', 'pob', 'passport', 'cnic', 'visa', 'physical']], ['Locations & movement', ['bdl', 'addresses', 'travel', 'vehicle']], ['Family', ['family']], ['Notes', ['notes']]];
const SEL_LABEL = { phone: 'Phone', imsi: 'IMSI', imei: 'IMEI', pushtoken: 'Push token', email: 'E-mail', social: 'Social media handle', social_id: 'Platform ID', cma_account: 'CMA / mobile-money account', other: 'Other selector' };

export const toMgrs = (lat, lon, precision = 5) => { if (!Number.isFinite(+lat) || !Number.isFinite(+lon) || lat == null || lon == null) return null; try { return mgrsLib.forward([+lon, +lat], precision); } catch { return null; } };
export const J = (s, d) => { if (s == null || s === '') return d; if (typeof s !== 'string') return s; try { return JSON.parse(s); } catch { return d; } };

// card object from already-filtered ACCEPTED rows (hits newest first)
export function makeCard(entityId, fields, selectors, hits, ent) {
  const v = f => fields.filter(x => x.field === f).map(x => x.value).filter(Boolean);
  const name = v('name')[0] || ent?.name || entityId;
  return { entityId, fields, selectors, hits, ent, name, objective: v('objective_name')[0] || null, v };
}
export const memoLink = id => `#memo:${id}`;
export const prevList = rows => rows.map(m => ({ ...m, kind_label: KIND_LABEL[m.kind], link: memoLink(m.id) }));

function sourceRegistry() {
  const list = []; const idx = new Map();
  return { list, n(citation, url) { const c = (citation || '').trim() || 'citation missing', u = url || null; const k = c + '\u0001' + u; if (!idx.has(k)) { idx.set(k, list.length + 1); list.push({ n: list.length + 1, citation: c, url: u }); } return idx.get(k); } };
}
const MON = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
export const fmtCiteDate = iso => { if (!iso) return 'n.d.'; const d = new Date(iso); return isNaN(d) ? iso : `${d.getUTCDate()}/${MON[d.getUTCMonth()]}/${d.getUTCFullYear()}`; };
// book-style citation text from a cited row: "(SRC; D/MON/YYYY; trust n) Publication — detail"
export const citeText = r => !r ? '' : r.cit_src ? `(${r.cit_src}; ${fmtCiteDate(r.cit_date)}; trust ${r.cit_trust ?? '?'}) ${r.cit_pub || ''}${r.citation && r.citation !== r.cit_pub ? ' — ' + r.citation : ''}`.trim() : (r.citation || '');

function lastLocation(card) {
  const h = card.hits[0];
  if (h) { const mg = toMgrs(h.lat, h.lon, 5); return { hit_id: h.id, lat: h.lat, lon: h.lon, mgrs: mg, as_of: h.ts, hit_kind: h.kind, place: h.place || null, citation: citeText(h) || '', citation_url: h.citation_url || null,
    text: `${h.place ? h.place + ' — ' : ''}${(+h.lat).toFixed(5)}, ${(+h.lon).toFixed(5)}${mg ? ` (MGRS ${mg})` : ''} as of ${h.ts} [${h.kind}]` }; }
  const bdl = card.v('bdl')[0];
  return { hit_id: null, lat: null, lon: null, mgrs: null, as_of: null, hit_kind: null, place: bdl || null, citation: '', citation_url: null, text: bdl ? `${bdl} (Bed Down Location; no accepted geolocation hit)` : 'no accepted geolocation hit on record' };
}
function oneLiner(card, loc) {
  const p = []; p.push(card.name + (card.objective ? ` (${card.objective})` : ''));
  const net = card.v('network')[0], role = card.v('role')[0], tribe = card.v('tribe')[0];
  if (role || net) p.push(`is ${role ? role : 'associated'}${net ? ` ${role ? 'in' : 'with'} ${net}` : ''}`);
  if (tribe) p.push(`(tribe: ${tribe})`);
  p.push(`. Last known location: ${loc.text}.`);
  return p.join(' ').replace(' .', '.');
}

// ---- template builder: everything the client needs to render a prefilled draft. `prev` = prevList(previous memos, newest first)
export function buildTemplateData(card, prev, entityId, kind, user = 'analyst') {
  if (!KINDS.includes(kind)) throw Object.assign(new Error('bad kind'), { status: 400 });
  const loc = lastLocation(card);
  const profileMemo = prev.find(m => m.kind === 'profile') || null;
  const head = `${card.objective ? card.objective + ' / ' : ''}${card.name} (${entityId})`;
  const t = { kind, kind_label: KIND_LABEL[kind], classification: CLASSIFICATION, entity_id: entityId, name: card.name, objective_name: card.objective, card_link: `#card:${entityId}`,
    to_line: 'Targeting Cell — Watch Officer (DEMO)', cc_line: 'Analyst Lead; Collection Manager (DEMO)', subject: '', summary: '', body: '', sections: [], sources: [],
    refs: { memo_ids: [], profile_memo_id: profileMemo?.id || null, profile_memo_link: profileMemo ? memoLink(profileMemo.id) : null, card_link: `#card:${entityId}`, hit_id: loc.hit_id, lat: loc.lat, lon: loc.lon, mgrs: loc.mgrs, as_of: loc.as_of, hit_kind: loc.hit_kind, last_known_location: loc.text },
    previous_memos: prev, required: [], drafted_by: user, generated_at: new Date().toISOString() };
  const S = sourceRegistry();
  if (kind === 'profile') {
    t.subject = `PROFILE OF THE TARGET — ${head}`;
    const notes = card.v('notes').find(n => !/^(Nationality|Origin) \(/.test(n));
    t.summary = notes || oneLiner(card, loc);
    const groups = [];
    for (const [title, keys] of GROUPS) { const rows = [];
      for (const k of keys) { const items = card.fields.filter(f => f.field === k && f.value).map(f => ({ value: f.value, n: S.n(citeText(f), f.citation_url) })); if (items.length) rows.push({ field: k, label: FIELD_LABEL[k] || k, items }); }
      if (rows.length) groups.push({ title, rows }); }
    const selRows = []; const roots = card.selectors.filter(s => !s.parent_id);
    for (const s of roots) { const kids = card.selectors.filter(k => k.parent_id === s.id);
      selRows.push({ field: s.kind, label: `${SEL_LABEL[s.kind] || s.kind}${s.platform ? ' (' + s.platform + ')' : ''}`, items: [{ value: s.value, n: S.n(citeText(s), s.citation_url) }, ...kids.map(k => ({ value: `${SEL_LABEL[k.kind] || k.kind}: ${k.value}`, n: S.n(citeText(k), k.citation_url), paired: true }))] }); }
    if (selRows.length) groups.push({ title: 'Selectors (paired rows indented)', rows: selRows });
    if (loc.hit_id) groups.push({ title: 'Last known location', rows: [{ field: 'last_known_location', label: 'Latest accepted geolocation hit', items: [{ value: loc.text, n: S.n(loc.citation, loc.citation_url) }] }] });
    t.profile = groups; t.sources = S.list; t.body = profileBodyText(groups);
  } else if (kind === 'location') {
    t.subject = `LOCATION UPDATE — ${head}${loc.as_of ? ' — as of ' + loc.as_of : ''}`;
    t.summary = `Location update on ${card.name}${card.objective ? ' (' + card.objective + ')' : ''}. Refer to the target profile ${profileMemo ? `(memo #${profileMemo.id})` : '(baseball card)'} for identity, selectors and network context.`;
    t.location_line = loc.hit_id ? `${card.name} is located at ${(+loc.lat).toFixed(5)}, ${(+loc.lon).toFixed(5)} (MGRS ${loc.mgrs || 'n/a'}) as of ${loc.as_of} [${loc.hit_kind}, ${loc.citation || 'citation missing'}]`
      : `${card.name} is located at <lat>, <lon> (MGRS <mgrs>) as of <time> [<hit kind>, <citation>]`;
    t.location_editable = !loc.hit_id;
    if (loc.hit_id) t.sources = [{ n: 1, citation: loc.citation || 'citation missing', url: loc.citation_url }];
    t.body = ''; t.refs.memo_ids = profileMemo ? [profileMemo.id] : [];
  } else if (kind === 'burn') {
    t.subject = `BURN NOTICE — ${head}`;
    t.summary = `Burn notice on ${card.name}${card.objective ? ' (' + card.objective + ')' : ''}. ${prev.length} previous memo(s) on this individual are referenced below.`;
    t.body = ''; t.body_label = 'Why we should not engage with this individual'; t.required = ['body']; t.refs.memo_ids = prev.map(m => m.id);
  } else if (kind === 'threat') {
    t.subject = `THREAT NOTICE — IMMEDIATE ATTENTION — ${head}`;
    t.header = 'IMMEDIATE ATTENTION';
    t.summary = `Threat notice linked to the profile of ${card.name}${card.objective ? ' (' + card.objective + ')' : ''}, entity ${entityId}. Last known location: ${loc.text}.`;
    t.body = ''; t.body_label = 'Describe the threat'; t.required = ['body']; t.refs.memo_ids = profileMemo ? [profileMemo.id] : [];
    t.linked_profile = { entity_id: entityId, name: card.name, objective_name: card.objective, last_known_location: loc.text, card_link: `#card:${entityId}`, profile_memo_link: t.refs.profile_memo_link };
  }
  return t;
}

export function profileBodyText(groups) {
  return groups.map(g => `${g.title.toUpperCase()}\n` + g.rows.map(r => `  ${r.label}: ${r.items.map(i => `${i.paired ? '↳ ' : ''}${i.value} [${i.n}]`).join('; ')}`).join('\n')).join('\n\n');
}

// validate + normalise a memo POST body; returns { row } or { error }
export function normaliseMemo(b, entityId, user, prevRows) {
  const kind = b.kind;
  if (!KINDS.includes(kind)) return { error: 'kind must be one of ' + KINDS.join('/') };
  if (!String(b.subject || '').trim()) return { error: 'subject required' };
  if ((kind === 'burn' || kind === 'threat') && !String(b.body || '').trim()) return { error: kind === 'burn' ? '"Why we should not engage with this individual" is required' : 'threat description is required' };
  const sections = (Array.isArray(b.sections) ? b.sections : J(b.sections, [])).filter(s => s && (s.title || s.body)).map(s => ({ title: String(s.title || ''), body: String(s.body || '') }));
  const refs = { ...(typeof b.refs === 'object' && b.refs ? b.refs : J(b.refs, {})) }; refs.card_link = refs.card_link || `#card:${entityId}`;
  if (kind === 'burn' && !refs.previous_memos) refs.previous_memos = prevList(prevRows);
  const sources = Array.isArray(b.sources) ? b.sources : J(b.sources, []);
  return { row: { entity_id: entityId, kind, to_line: String(b.to_line || ''), cc_line: String(b.cc_line || ''), subject: String(b.subject).trim(), summary: String(b.summary || ''), body: String(b.body || ''), sections: JSON.stringify(sections), refs: JSON.stringify(refs), sources: JSON.stringify(sources), created_by: user } };
}
export const parseMemo = m => m && ({ ...m, sections: J(m.sections, []), refs: J(m.refs, {}), sources: J(m.sources, []) });

// plain-text e-mail rendering (the client has the same function for the clipboard)
export function memoText(m) {
  const refs = J(m.refs, {}), sections = J(m.sections, []), sources = J(m.sources, []);
  const L = [CLASSIFICATION, '', `To: ${m.to_line || ''}`, `CC: ${m.cc_line || ''}`, `Subject: ${m.subject || ''}`, `From: ${m.created_by || ''}`, `Date: ${m.created_at || ''}`, `Target: ${m.entity_id} (${refs.card_link || '#card:' + m.entity_id})`, ''];
  if (m.kind === 'threat') L.push('*** IMMEDIATE ATTENTION ***', '');
  if (m.summary) L.push(m.summary, '');
  if (m.kind === 'location' && refs.location_line) L.push(refs.location_line, '');
  if (m.body) L.push(m.kind === 'burn' ? 'WHY WE SHOULD NOT ENGAGE WITH THIS INDIVIDUAL:' : m.kind === 'threat' ? 'THREAT:' : '', m.body, '');
  if (m.kind === 'burn' && refs.previous_memos?.length) { L.push('PREVIOUS MEMOS ON THIS INDIVIDUAL:'); for (const p of refs.previous_memos) L.push(`  - [${p.kind_label || p.kind}] ${p.created_at} ${p.created_by}: ${p.subject} (${p.link || '#memo:' + p.id})`); L.push(''); }
  if (refs.profile_memo_link && m.kind !== 'burn') L.push(`Reference profile: ${refs.card_link || '#card:' + m.entity_id}${refs.profile_memo_link ? ' · ' + refs.profile_memo_link : ''}`, '');
  for (const s of sections) L.push(String(s.title || '').toUpperCase(), s.body || '', '');
  if (sources.length) { L.push('SOURCES'); for (const s of sources) L.push(`  [${s.n}] ${s.citation}${s.url ? ' — ' + s.url : ''}`); L.push(''); }
  L.push(CLASSIFICATION);
  return L.filter((x, i, a) => !(x === '' && a[i - 1] === '')).join('\n');
}
