// Memo module for the target baseball card — window.Memos.open(CARD) / window.Memos.list(CARD, el).
// Four e-mail-style templates (Profile of the Target / Location update / Burn Notice / Threat Notice), prefilled server-side
// from GET /api/targets/:id/memo-template?kind=, saved with POST /api/targets/:id/memos, read back via GET /api/memos/:id.
(function () {
  'use strict';
  const CLS = 'UNCLASSIFIED // DEMO';
  const KINDS = [['profile', 'Profile of the Target', 'Auto-populated from the card\'s accepted fields with citations; editable summary; add free-text sections.'],
    ['location', 'Location update on Target', 'References the profile; summary + free text; auto line from the latest accepted geolocation hit.'],
    ['burn', 'Burn Notice', 'Lists every previous memo on this individual; requires "Why we should not engage".'],
    ['threat', 'Threat Notice', 'IMMEDIATE ATTENTION header; requires a threat description; linked to the profile.']];
  const KL = Object.fromEntries(KINDS.map(k => [k[0], k[1]]));
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const api = async (p, o = {}) => { const r = await fetch(p, { headers: { 'content-type': 'application/json' }, ...o, body: o.body ? JSON.stringify(o.body) : undefined }); const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error(j.error || ('HTTP ' + r.status)); return j; };
  const $ = (s, r = document) => r.querySelector(s);
  const fmtTs = t => (t || '').replace('T', ' ').replace(/\.\d+Z?$/, '');
  const me = () => { try { return (typeof ME !== 'undefined' && ME) || window.ME || null; } catch { return null; } };
  const canEdit = () => ['analyst', 'instructor', 'admin'].includes(me()?.role);

  const css = `
  #memoHost .mm{position:fixed;inset:0;background:#000b;z-index:40;display:flex;align-items:stretch;justify-content:center;padding:18px}
  #memoHost .mbox{background:var(--bg);border:1px solid var(--line);border-radius:8px;width:min(1100px,100%);display:flex;flex-direction:column;min-height:0;color:var(--text)}
  #memoHost .mhead{display:flex;align-items:center;gap:10px;padding:8px 12px;background:var(--panel);border-bottom:1px solid var(--line);border-radius:8px 8px 0 0}
  #memoHost .mhead h2{margin:0;font-size:15px}#memoHost .mbody{flex:1;overflow:auto;padding:12px 14px}
  #memoHost .mfoot{display:flex;gap:8px;align-items:center;padding:8px 12px;border-top:1px solid var(--line);background:var(--panel);border-radius:0 0 8px 8px}
  .mcls{background:#2e7d32;color:#fff;text-align:center;font-weight:700;font-size:11px;padding:3px;border-radius:4px;letter-spacing:.5px}
  .mkinds{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:8px 0}.mkinds button{text-align:left;padding:6px 8px;line-height:1.3}.mkinds button.on{border-color:var(--acc);background:#12304a}.mkinds small{display:block;color:var(--mute);font-size:10px;margin-top:2px}
  .mhdr{display:grid;grid-template-columns:90px 1fr;gap:6px 8px;align-items:center;margin:8px 0}.mhdr label{color:var(--mute);font-size:11px;text-transform:uppercase;letter-spacing:.4px}.mhdr input{width:100%}
  .mblk{border:1px solid var(--line);border-radius:6px;background:var(--panel);margin:10px 0}.mblk .bh{display:flex;justify-content:space-between;align-items:center;padding:5px 8px;background:var(--panel2);border-radius:6px 6px 0 0;font-weight:600;font-size:12px}.mblk .bb{padding:8px}
  .mblk textarea{width:100%;min-height:70px;resize:vertical}.mblk textarea.big{min-height:120px}.req{color:var(--bad);font-weight:700}
  .mprof table{width:100%;border-collapse:collapse}.mprof th{text-align:left;color:var(--mute);font-size:11px;text-transform:uppercase;padding:6px 6px 2px;border-bottom:1px solid var(--line)}.mprof td{padding:3px 6px;vertical-align:top;border-bottom:1px solid var(--line);font-size:12px}.mprof td.l{color:var(--mute);width:220px}.mprof .pr{display:block;margin-left:14px;color:#cdd}
  .cit{color:var(--acc);font-size:10px;vertical-align:super;margin-left:2px;cursor:pointer;text-decoration:none}
  .msrc ol{margin:4px 0 0 18px;padding:0;font-size:12px}.msrc li{margin:2px 0}.msrc a{color:var(--acc)}
  .msec{border-top:1px dashed var(--line);padding:6px 0}.msec input{width:100%;margin-bottom:4px;font-weight:600}
  .mimm{background:#4a1515;border:1px solid var(--bad);color:#ffd6d6;text-align:center;font-weight:800;letter-spacing:2px;padding:6px;border-radius:4px;margin:8px 0}
  .mloc{font-family:ui-monospace,monospace;font-size:12px;background:var(--panel2);border:1px solid var(--line);padding:6px 8px;border-radius:4px}.mloc input{width:100%;font-family:ui-monospace,monospace}
  .mbadge{display:inline-block;padding:1px 7px;border-radius:10px;font-size:10px;font-weight:700;letter-spacing:.3px;text-transform:uppercase;border:1px solid var(--line);background:var(--panel2);color:var(--text)}
  .mbadge.profile{background:#12304a;border-color:var(--acc);color:#cfe8ff}.mbadge.location{background:#143d2a;border-color:#35c27a;color:#c9f5dc}.mbadge.burn{background:#4a3410;border-color:var(--warn);color:#ffe2b0}.mbadge.threat{background:#4a1515;border-color:var(--bad);color:#ffd6d6}
  .mlist{display:grid;grid-template-columns:360px 1fr;gap:12px;min-height:420px}.mlist .ml{border:1px solid var(--line);border-radius:6px;background:var(--panel);overflow:auto;max-height:70vh}
  .mlist .mi{padding:8px 10px;border-bottom:1px solid var(--line);cursor:pointer}.mlist .mi:hover{background:var(--panel2)}.mlist .mi.on{background:#12304a;border-left:3px solid var(--acc)}.mlist .mi .s{font-weight:600;margin:3px 0 2px;font-size:12px}.mlist .mi .m{color:var(--mute);font-size:11px}
  .mread{border:1px solid var(--line);border-radius:6px;background:var(--panel);padding:12px;overflow:auto;max-height:70vh}.mread .rh{display:flex;gap:6px;align-items:center;margin-bottom:8px}.mread .rh h3{margin:0;flex:1;font-size:14px}
  .mread .hdr{display:grid;grid-template-columns:80px 1fr;gap:2px 8px;font-size:12px;margin:8px 0;padding:8px;background:var(--panel2);border-radius:4px}.mread .hdr b{color:var(--mute);font-weight:600;text-transform:uppercase;font-size:10px}
  .mread .sum{font-size:13px;line-height:1.5;margin:10px 0}.mread .bodyt{white-space:pre-wrap;font-size:12.5px;line-height:1.5;margin:8px 0}.mread h4{margin:12px 0 4px;font-size:11px;color:var(--mute);text-transform:uppercase;letter-spacing:.4px}
  .mtoast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#143d2a;border:1px solid #35c27a;color:#c9f5dc;padding:8px 14px;border-radius:6px;z-index:50;font-size:12px}
  .mprint{color:var(--mute);font-size:11px}`;
  function host() { let h = $('#memoHost'); if (!h) { const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st); h = document.createElement('div'); h.id = 'memoHost'; document.body.appendChild(h); } return h; }
  function toast(msg) { const t = document.createElement('div'); t.className = 'mtoast'; t.textContent = msg; document.body.appendChild(t); setTimeout(() => t.remove(), 2600); }
  async function copy(text) { try { await navigator.clipboard.writeText(text); toast('Copied to clipboard'); } catch { const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove(); toast('Copied to clipboard'); } }
  const srcList = srcs => srcs?.length ? `<div class="msrc"><ol>${srcs.map(s => `<li id="src-${s.n}"><b>[${s.n}]</b> ${esc(s.citation)}${s.url ? ` — <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)} ↗</a>` : ''}</li>`).join('')}</ol></div>` : '<div class="hint">no sources recorded</div>';
  const citeify = s => esc(s).replace(/\[(\d+)\]/g, '<a class="cit" href="#src-$1" title="source $1">[$1]</a>');
  function profCells(items) { return items.map(i => `${i.paired ? '<span class="pr">↳ ' : ''}${esc(i.value)}<a class="cit" href="#src-${i.n}">[${i.n}]</a>${i.paired ? '</span>' : '; '}`).join('').replace(/; $/, ''); }
  const profTable2 = groups => `<div class="mprof"><table>${(groups || []).map(g => `<tr><th colspan="2">${esc(g.title)}</th></tr>${g.rows.map(r => `<tr><td class="l">${esc(r.label)}</td><td>${profCells(r.items)}</td></tr>`).join('')}`).join('')}</table></div>`;

  // ---- plain-text e-mail rendering (mirrors lib/memos.mjs memoText)
  function emailText(m) {
    const refs = m.refs || {}, sections = m.sections || [], sources = m.sources || [];
    const L = [CLS, '', `To: ${m.to_line || ''}`, `CC: ${m.cc_line || ''}`, `Subject: ${m.subject || ''}`, `From: ${m.created_by || me()?.username || ''}`, `Date: ${m.created_at || new Date().toISOString().slice(0, 19).replace('T', ' ')}`, `Target: ${m.entity_id} (${refs.card_link || '#card:' + m.entity_id})`, ''];
    if (m.kind === 'threat') L.push('*** IMMEDIATE ATTENTION ***', '');
    if (m.summary) L.push(m.summary, '');
    if (m.kind === 'location' && refs.location_line) L.push(refs.location_line, '');
    if (m.body) L.push(m.kind === 'burn' ? 'WHY WE SHOULD NOT ENGAGE WITH THIS INDIVIDUAL:' : m.kind === 'threat' ? 'THREAT:' : '', m.body, '');
    if (m.kind === 'burn' && refs.previous_memos?.length) { L.push('PREVIOUS MEMOS ON THIS INDIVIDUAL:'); for (const p of refs.previous_memos) L.push(`  - [${p.kind_label || KL[p.kind] || p.kind}] ${p.created_at} ${p.created_by}: ${p.subject} (${p.link || '#memo:' + p.id})`); L.push(''); }
    if (refs.profile_memo_link && m.kind !== 'burn') L.push(`Reference profile: ${refs.card_link || '#card:' + m.entity_id} · ${refs.profile_memo_link}`, '');
    for (const s of sections) L.push(String(s.title || '').toUpperCase(), s.body || '', '');
    if (sources.length) { L.push('SOURCES'); for (const s of sources) L.push(`  [${s.n}] ${s.citation}${s.url ? ' — ' + s.url : ''}`); L.push(''); }
    L.push(CLS);
    return L.filter((x, i, a) => !(x === '' && a[i - 1] === '')).join('\n');
  }

  // ---- draft dialog
  async function open(CARD, kind = 'profile') {
    const h = host(); const eid = CARD.entity.id;
    h.innerHTML = `<div class="mm"><div class="mbox"><div class="mhead"><h2>Draft memo</h2><span class="hint">${esc(CARD.fields?.find(f => f.field === 'objective_name' && f.status === 'accepted')?.value || '')} · ${esc(CARD.fields?.find(f => f.field === 'name' && f.status === 'accepted')?.value || CARD.entity.name)} · <span class="chip">${esc(eid)}</span></span><span style="flex:1"></span><button class="sm" id="mclose">✕ close</button></div><div class="mbody" id="mbody"><div class="hint">Loading template…</div></div><div class="mfoot" id="mfoot"></div></div></div>`;
    $('#mclose', h).onclick = () => { h.innerHTML = ''; };
    $('.mm', h).onclick = e => { if (e.target === e.currentTarget) h.innerHTML = ''; };
    await render(kind);
    async function render(k) {
      let T; try { T = await api(`/api/targets/${encodeURIComponent(eid)}/memo-template?kind=${k}`); } catch (e) { $('#mbody', h).innerHTML = `<div style="color:var(--bad)">${esc(e.message)}</div>`; return; }
      // client-side MGRS fill-in when the server left it blank (mgrs library is loaded globally by the page)
      if (T.refs && T.refs.lat != null && !T.refs.mgrs && window.mgrs) { try { T.refs.mgrs = mgrs.forward([T.refs.lon, T.refs.lat], 5); if (T.location_line) T.location_line = T.location_line.replace('MGRS n/a', 'MGRS ' + T.refs.mgrs); } catch { } }
      const kindsHtml = `<div class="mkinds">${KINDS.map(([id, label, help]) => `<button data-k="${id}" class="${id === k ? 'on' : ''}">${esc(label)}<small>${esc(help)}</small></button>`).join('')}</div>`;
      const hdr = `<div class="mcls">${CLS}</div>${kindsHtml}<div class="mhdr"><label>To</label><input id="m_to" value="${esc(T.to_line)}"><label>CC</label><input id="m_cc" value="${esc(T.cc_line)}"><label>Subject</label><input id="m_subj" value="${esc(T.subject)}"><label>From</label><div class="hint">${esc(me()?.username || T.drafted_by || '')} · ${esc(new Date().toISOString().slice(0, 16).replace('T', ' '))}Z · target <a href="${esc(T.card_link)}">${esc(T.card_link)}</a></div></div>`;
      let main = '';
      if (k === 'profile') {
        main = `<div class="mblk"><div class="bh">Summary <span class="hint">editable — seeded from the card's notes or a generated one-liner</span></div><div class="bb"><textarea id="m_sum">${esc(T.summary)}</textarea></div></div>
        <div class="mblk"><div class="bh">Profile of the Target — accepted card fields <span class="hint">every value is followed by its citation [n]; see Sources below</span></div><div class="bb">${T.profile?.length ? profTable2(T.profile) : '<div class="hint">no accepted fields on this card yet</div>'}</div></div>
        <div class="mblk"><div class="bh">Additional sections <button class="sm" id="m_addsec">+ add section</button></div><div class="bb" id="m_secs"><div class="hint" id="m_nosec">none — click "+ add section" for free-text fields (title + body), any number.</div></div></div>
        <div class="mblk"><div class="bh">Sources</div><div class="bb">${srcList(T.sources)}</div></div>`;
      } else if (k === 'location') {
        main = `<div class="mblk"><div class="bh">Reference</div><div class="bb">Profile: <a href="${esc(T.card_link)}">${esc(T.card_link)}</a>${T.refs.profile_memo_link ? ` · most recent Profile memo <a href="${esc(T.refs.profile_memo_link)}" class="memo-link" data-id="${T.refs.profile_memo_id}">${esc(T.refs.profile_memo_link)}</a>` : ' · <span class="hint">no Profile memo saved yet for this target</span>'}</div></div>
        <div class="mblk"><div class="bh">Summary <span class="hint">editable</span></div><div class="bb"><textarea id="m_sum">${esc(T.summary)}</textarea></div></div>
        <div class="mblk"><div class="bh">Location line <span class="hint">${T.location_editable ? 'no accepted geolocation hit — fill in the placeholder' : `auto from the latest accepted hit (#${T.refs.hit_id}, ${esc(T.refs.hit_kind)}); editable`}</span></div><div class="bb"><div class="mloc"><input id="m_loc" value="${esc(T.location_line)}"></div></div></div>
        <div class="mblk"><div class="bh">Update <span class="hint">free text</span></div><div class="bb"><textarea id="m_body" class="big" placeholder="Pattern of life, confidence, collection gaps, recommended actions…">${esc(T.body)}</textarea></div></div>
        <div class="mblk"><div class="bh">Sources</div><div class="bb">${srcList(T.sources)}</div></div>`;
      } else if (k === 'burn') {
        main = `<div class="mblk"><div class="bh">Summary <span class="hint">editable</span></div><div class="bb"><textarea id="m_sum">${esc(T.summary)}</textarea></div></div>
        <div class="mblk"><div class="bh">Previous memos on this individual (${T.previous_memos.length})</div><div class="bb">${T.previous_memos.length ? `<table><tr><th>type</th><th>date</th><th>author</th><th>subject</th><th>link</th></tr>${T.previous_memos.map(p => `<tr><td><span class="mbadge ${p.kind}">${esc(p.kind_label)}</span></td><td>${esc(fmtTs(p.created_at))}</td><td>${esc(p.created_by)}</td><td>${esc(p.subject)}</td><td><a href="${esc(p.link)}" class="memo-link" data-id="${p.id}">${esc(p.link)}</a></td></tr>`).join('')}</table>` : '<div class="hint">no previous memos on this individual</div>'}</div></div>
        <div class="mblk"><div class="bh">Why we should not engage with this individual <span class="req">* required</span></div><div class="bb"><textarea id="m_body" class="big" placeholder="Required: reasons not to engage (compromise, deconfliction, legal/policy, source protection…)">${esc(T.body)}</textarea></div></div>`;
      } else if (k === 'threat') {
        const lp = T.linked_profile || {};
        main = `<div class="mimm">⚠ IMMEDIATE ATTENTION ⚠</div>
        <div class="mblk"><div class="bh">Linked profile</div><div class="bb"><div class="mhdr" style="margin:0"><label>Entity</label><div><a href="${esc(lp.card_link)}">${esc(lp.entity_id)}</a></div><label>Name</label><div>${esc(lp.name)}</div><label>Objective</label><div>${esc(lp.objective_name || '—')}</div><label>Last known</label><div>${esc(lp.last_known_location)}</div>${lp.profile_memo_link ? `<label>Profile memo</label><div><a href="${esc(lp.profile_memo_link)}" class="memo-link" data-id="${T.refs.profile_memo_id}">${esc(lp.profile_memo_link)}</a></div>` : ''}</div></div></div>
        <div class="mblk"><div class="bh">Summary <span class="hint">editable</span></div><div class="bb"><textarea id="m_sum">${esc(T.summary)}</textarea></div></div>
        <div class="mblk"><div class="bh">Describe the threat <span class="req">* required</span></div><div class="bb"><textarea id="m_body" class="big" placeholder="Required: nature of the threat, who/what is threatened, timing, indicators, source confidence, recommended immediate actions…">${esc(T.body)}</textarea></div></div>`;
      }
      $('#mbody', h).innerHTML = hdr + main;
      $('#mfoot', h).innerHTML = `${canEdit() ? '<button class="pri" id="m_save">Save memo</button>' : '<span class="hint">analyst role required to save</span>'}<button id="m_copy">Copy as e-mail text</button><span id="m_msg" class="hint"></span><span style="flex:1"></span><span class="hint">${CLS}</span>`;
      h.querySelectorAll('.mkinds button').forEach(b => b.onclick = () => render(b.dataset.k));
      h.querySelectorAll('.memo-link').forEach(a => a.onclick = e => { e.preventDefault(); readerPopup(+a.dataset.id); });
      const secs = [];
      if (k === 'profile') $('#m_addsec', h).onclick = () => { $('#m_nosec', h)?.remove(); const d = document.createElement('div'); d.className = 'msec'; d.innerHTML = `<input placeholder="Section title (e.g. Assessment, Pattern of life, Collection gaps)"><textarea placeholder="Free text…"></textarea><div style="text-align:right"><button class="sm m_rm">remove</button></div>`; $('#m_secs', h).appendChild(d); d.querySelector('.m_rm').onclick = () => d.remove(); d.querySelector('input').focus(); };
      const collect = () => {
        const sections = [...h.querySelectorAll('#m_secs .msec')].map(d => ({ title: d.querySelector('input').value.trim(), body: d.querySelector('textarea').value.trim() })).filter(s => s.title || s.body);
        const refs = { ...T.refs }; if (k === 'profile') refs.profile_groups = T.profile; if (k === 'location') refs.location_line = $('#m_loc', h).value.trim(); if (k === 'burn') refs.previous_memos = T.previous_memos; if (k === 'threat') refs.linked_profile = T.linked_profile;
        return { kind: k, entity_id: eid, to_line: $('#m_to', h).value.trim(), cc_line: $('#m_cc', h).value.trim(), subject: $('#m_subj', h).value.trim(), summary: $('#m_sum', h)?.value.trim() || '', body: k === 'profile' ? T.body : ($('#m_body', h)?.value.trim() || ''), sections, refs, sources: T.sources || [] };
      };
      $('#m_copy', h).onclick = () => copy(emailText(collect()));
      const save = $('#m_save', h); if (save) save.onclick = async () => {
        const m = collect(); const msg = $('#m_msg', h);
        if (!m.subject) return msg.textContent = 'Subject is required.';
        if ((k === 'burn' || k === 'threat') && !m.body) { msg.textContent = k === 'burn' ? '"Why we should not engage with this individual" is required.' : 'The threat description is required.'; $('#m_body', h).focus(); return; }
        save.disabled = true; msg.textContent = 'Saving…';
        try { const saved = await api(`/api/targets/${encodeURIComponent(eid)}/memos`, { method: 'POST', body: m }); h.innerHTML = ''; toast(`${KL[k]} saved as memo #${saved.id}`);
          const tab = document.querySelector('#ctabs button[data-t="6"]'); if (tab) tab.click(); else { const el = $('#memoList'); if (el) list(CARD, el, saved.id); } }
        catch (e) { save.disabled = false; msg.textContent = 'Save failed: ' + e.message; }
      };
    }
  }

  // ---- reader rendering (shared by the Memos tab pane, the popup and print)
  function renderMemo(m, forPrint = false) {
    const refs = m.refs || {}; const prof = refs.profile_groups || null;
    const hdr = `<div class="mcls">${CLS}</div><div class="hdr"><b>To</b><span>${esc(m.to_line)}</span><b>CC</b><span>${esc(m.cc_line)}</span><b>Subject</b><span><strong>${esc(m.subject)}</strong></span><b>From</b><span>${esc(m.created_by)}</span><b>Date</b><span>${esc(fmtTs(m.created_at))}</span><b>Target</b><span><a href="${esc(refs.card_link || '#card:' + m.entity_id)}">${esc(m.entity_id)}</a>${refs.profile_memo_link && m.kind !== 'profile' ? ` · profile memo <a href="${esc(refs.profile_memo_link)}" class="memo-link" data-id="${refs.profile_memo_id}">${esc(refs.profile_memo_link)}</a>` : ''}</span><b>Type</b><span><span class="mbadge ${m.kind}">${esc(m.kind_label || KL[m.kind])}</span></span></div>`;
    let body = '';
    if (m.kind === 'threat') body += `<div class="mimm">⚠ IMMEDIATE ATTENTION ⚠</div>`;
    if (m.summary) body += `<div class="sum">${citeify(m.summary)}</div>`;
    if (m.kind === 'threat' && refs.linked_profile) { const lp = refs.linked_profile; body += `<h4>Linked profile</h4><div class="hdr"><b>Entity</b><span><a href="${esc(lp.card_link)}">${esc(lp.entity_id)}</a></span><b>Name</b><span>${esc(lp.name)}</span><b>Objective</b><span>${esc(lp.objective_name || '—')}</span><b>Last known</b><span>${esc(lp.last_known_location)}</span></div>`; }
    if (m.kind === 'location' && refs.location_line) body += `<h4>Location</h4><div class="mloc">${esc(refs.location_line)}</div>`;
    if (m.kind === 'profile') body += `<h4>Profile of the Target</h4>${prof ? profTable2(prof) : `<div class="bodyt">${citeify(m.body)}</div>`}`;
    else if (m.body) body += `<h4>${m.kind === 'burn' ? 'Why we should not engage with this individual' : m.kind === 'threat' ? 'Threat' : 'Update'}</h4><div class="bodyt">${citeify(m.body)}</div>`;
    if (m.kind === 'burn') body += `<h4>Previous memos on this individual (${(refs.previous_memos || []).length})</h4>${(refs.previous_memos || []).length ? `<table><tr><th>type</th><th>date</th><th>author</th><th>subject</th><th>link</th></tr>${refs.previous_memos.map(p => `<tr><td><span class="mbadge ${p.kind}">${esc(p.kind_label || KL[p.kind])}</span></td><td>${esc(fmtTs(p.created_at))}</td><td>${esc(p.created_by)}</td><td>${esc(p.subject)}</td><td><a href="${esc(p.link || '#memo:' + p.id)}" class="memo-link" data-id="${p.id}">${esc(p.link || '#memo:' + p.id)}</a></td></tr>`).join('')}</table>` : '<div class="hint">none</div>'}`;
    for (const s of m.sections || []) body += `<h4>${esc(s.title || 'Section')}</h4><div class="bodyt">${citeify(s.body)}</div>`;
    if (m.sources?.length) body += `<h4>Sources</h4>${srcList(m.sources)}`;
    body += `<div class="mcls" style="margin-top:12px">${CLS}</div>`;
    return hdr + body;
  }
  function printMemo(m) {
    const w = window.open('', '_blank', 'width=900,height=1000'); if (!w) return alert('Pop-up blocked — allow pop-ups to print.');
    w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${esc(m.subject)}</title><style>:root{--bg:#fff;--panel:#fff;--panel2:#f3f4f6;--line:#d0d5dc;--text:#111;--mute:#555;--acc:#0b5cad;--warn:#b26a00;--bad:#b00020}body{font:12.5px/1.45 system-ui,Segoe UI,Roboto,sans-serif;color:#111;margin:24px;max-width:800px}${css.replace(/#memoHost /g, '')}.mcls{background:#2e7d32}a{color:#0b5cad}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:3px 6px;border-bottom:1px solid #ddd;font-size:12px;vertical-align:top}.hint{color:#555;font-size:11px}</style></head><body><div class="mread" style="border:none;max-height:none">${renderMemo(m, true)}</div><script>setTimeout(()=>window.print(),300)<\/script></body></html>`);
    w.document.close();
  }
  function wireReader(root, onOpen) { root.querySelectorAll('.memo-link').forEach(a => a.onclick = e => { e.preventDefault(); onOpen(+a.dataset.id); }); root.querySelectorAll('a.cit').forEach(a => a.onclick = e => { e.preventDefault(); root.querySelector(a.getAttribute('href'))?.scrollIntoView({ block: 'center' }); }); }
  async function readerPopup(id) {
    const m = await api('/api/memos/' + id); const h = host(); const d = document.createElement('div'); d.className = 'mm'; d.style.zIndex = 45;
    d.innerHTML = `<div class="mbox" style="width:min(900px,100%)"><div class="mhead"><h2>Memo #${m.id}</h2><span class="mbadge ${m.kind}">${esc(m.kind_label)}</span><span style="flex:1"></span><button class="sm r_copy">Copy</button><button class="sm r_print">Print</button><button class="sm r_close">✕ close</button></div><div class="mbody mread" style="border:none;max-height:none">${renderMemo(m)}</div></div>`;
    h.appendChild(d); d.querySelector('.r_close').onclick = () => d.remove(); d.onclick = e => { if (e.target === d) d.remove(); };
    d.querySelector('.r_copy').onclick = () => copy(m.text || emailText(m)); d.querySelector('.r_print').onclick = () => printMemo(m); wireReader(d, readerPopup);
  }

  // ---- Memos tab: list (newest first) + reader pane
  async function list(CARD, el, openId = null) {
    const eid = CARD.entity.id; host();
    let memos; try { memos = await api(`/api/targets/${encodeURIComponent(eid)}/memos`); } catch (e) { el.innerHTML = `<div style="color:var(--bad)">${esc(e.message)}</div>`; return; }
    el.classList.remove('hint');
    el.innerHTML = `<div style="display:flex;gap:8px;align-items:center;margin-bottom:8px"><b>Memos on this target (${memos.length})</b><span class="hint">newest first · click a memo to read it in the pane · ${CLS} on every memo</span><span style="flex:1"></span>${canEdit() ? `<button class="sm" id="ml_new">Draft memo</button>` : ''}</div>
      <div class="mlist"><div class="ml" id="ml_list">${memos.length ? memos.map(m => `<div class="mi" data-id="${m.id}"><span class="mbadge ${m.kind}">${esc(m.kind_label || KL[m.kind])}</span> <span class="hint">#${m.id}</span><div class="s">${esc(m.subject)}</div><div class="m">${esc(m.created_by)} · ${esc(fmtTs(m.created_at))}</div></div>`).join('') : '<div class="hint" style="padding:10px">No memos yet. Use "Draft memo" (card header) to create a Profile, Location update, Burn Notice or Threat Notice.</div>'}</div>
      <div class="mread" id="ml_read"><div class="hint">Select a memo on the left to read it here.</div></div></div>`;
    const nb = $('#ml_new', el); if (nb) nb.onclick = () => open(CARD);
    const show = async id => {
      el.querySelectorAll('.mi').forEach(x => x.classList.toggle('on', +x.dataset.id === id));
      const pane = $('#ml_read', el); pane.innerHTML = '<div class="hint">Loading…</div>';
      let m; try { m = await api('/api/memos/' + id); } catch (e) { pane.innerHTML = `<div style="color:var(--bad)">${esc(e.message)}</div>`; return; }
      pane.innerHTML = `<div class="rh"><h3>${esc(m.subject)}</h3><button class="sm" id="r_copy" title="Copy as e-mail text">Copy</button><button class="sm" id="r_print">Print</button></div>${renderMemo(m)}`;
      $('#r_copy', pane).onclick = () => copy(m.text || emailText(m)); $('#r_print', pane).onclick = () => printMemo(m);
      wireReader(pane, id2 => id2 === id ? pane.scrollTo(0, 0) : (el.querySelector(`.mi[data-id="${id2}"]`) ? show(id2) : readerPopup(id2)));
    };
    el.querySelectorAll('.mi').forEach(x => x.onclick = () => show(+x.dataset.id));
    if (openId && memos.some(m => m.id === openId)) show(openId); else if (memos.length) show(memos[0].id);
  }

  window.Memos = { open, list, emailText, renderMemo, read: readerPopup, KINDS: KINDS.map(k => k[0]) };
})();
