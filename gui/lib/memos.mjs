// Memo module — four e-mail-style memo types (profile / location / burn / threat) drafted from a target's baseball card.
// Mount: app.use('/api', memosRouter(db, R, requireRole)). All data is fictional/synthetic; every memo carries UNCLASSIFIED // DEMO.
import { Router } from 'express';
import { KINDS, CLASSIFICATION, KIND_LABEL, toMgrs, J, makeCard, prevList, fmtCiteDate, citeText, buildTemplateData, profileBodyText, normaliseMemo, parseMemo, memoText } from './memo_core.mjs';
export { KINDS, CLASSIFICATION, KIND_LABEL, toMgrs, fmtCiteDate, citeText, buildTemplateData, profileBodyText, memoText };

export function ensureMemoTables(db) {
  db.exec(`CREATE TABLE IF NOT EXISTS memos(id INTEGER PRIMARY KEY, entity_id TEXT, kind TEXT CHECK(kind IN ('profile','location','burn','threat')), to_line TEXT, cc_line TEXT, subject TEXT, summary TEXT, body TEXT,
    sections TEXT, refs TEXT, sources TEXT, created_by TEXT, created_at TEXT DEFAULT (datetime('now')));
  CREATE INDEX IF NOT EXISTS memos_e ON memos(entity_id, created_at);
  CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, ts TEXT DEFAULT (datetime('now')), user TEXT, action TEXT, target TEXT, before TEXT, after TEXT);`);
}

const has = (R, t) => { try { return !!R.prepare('SELECT 1 FROM sqlite_master WHERE name=?').get(t); } catch { return false; } };
// ---- card readers (app.db tables written by server.mjs)
function cardOf(db, R, entityId) {
  const fields = db.prepare("SELECT * FROM card_fields WHERE entity_id=? AND status='accepted' ORDER BY field, id").all(entityId);
  const selectors = db.prepare("SELECT * FROM card_selectors WHERE entity_id=? AND status='accepted' ORDER BY COALESCE(parent_id,id), parent_id IS NOT NULL, id").all(entityId);
  const hits = db.prepare("SELECT * FROM card_hits WHERE entity_id=? AND status='accepted' ORDER BY ts DESC, id DESC").all(entityId);
  const ent = R && has(R, 'entities') ? R.prepare('SELECT id, name, kind, dataset, role FROM entities WHERE id=?').get(entityId) : null;
  return makeCard(entityId, fields, selectors, hits, ent);
}

const prevMemos = (db, entityId) => prevList(db.prepare('SELECT id, kind, subject, created_by, created_at FROM memos WHERE entity_id=? ORDER BY created_at DESC, id DESC').all(entityId));

// ---- template builder: everything the client needs to render a prefilled draft
export function buildTemplate(db, R, entityId, kind, user = 'analyst') { return buildTemplateData(cardOf(db, R, entityId), prevMemos(db, entityId), entityId, kind, user); }

export function memosRouter(db, R, requireRole) {
  ensureMemoTables(db);
  const audit = (user, action, target, before, after) => db.prepare('INSERT INTO audit(user,action,target,before,after) VALUES (?,?,?,?,?)').run(user || null, action, target || null, before == null ? null : JSON.stringify(before), after == null ? null : JSON.stringify(after));
  const parse = parseMemo;
  const r = Router();
  r.get('/targets/:id/memos', (req, res) => res.json(db.prepare('SELECT id, entity_id, kind, to_line, cc_line, subject, created_by, created_at FROM memos WHERE entity_id=? ORDER BY created_at DESC, id DESC').all(req.params.id).map(m => ({ ...m, kind_label: KIND_LABEL[m.kind] }))));
  r.get('/targets/:id/memo-template', (req, res) => { try { res.json(buildTemplate(db, R, req.params.id, String(req.query.kind || 'profile'), req.user?.username)); } catch (e) { res.status(e.status || 500).json({ error: e.message }); } });
  r.post('/targets/:id/memos', requireRole('analyst'), (req, res) => {
    const b = req.body || {}; const kind = b.kind; const prevRows = db.prepare('SELECT id, kind, subject, created_by, created_at FROM memos WHERE entity_id=? ORDER BY created_at DESC, id DESC').all(req.params.id);
    const nm = normaliseMemo(b, req.params.id, req.user.username, prevRows); if (nm.error) return res.status(400).json({ error: nm.error }); const row = nm.row; const { sections, refs, sources } = parseMemo(row);
    const ins = db.prepare('INSERT INTO memos(entity_id,kind,to_line,cc_line,subject,summary,body,sections,refs,sources,created_by) VALUES (@entity_id,@kind,@to_line,@cc_line,@subject,@summary,@body,@sections,@refs,@sources,@created_by)').run(row);
    const saved = parse(db.prepare('SELECT * FROM memos WHERE id=?').get(ins.lastInsertRowid));
    audit(req.user.username, 'memo_create', req.params.id, null, { id: saved.id, kind, subject: saved.subject, to_line: saved.to_line, cc_line: saved.cc_line, summary: saved.summary, body: saved.body, sections, refs, sources });
    res.json(saved); });
  r.get('/memos/:id', (req, res) => { const m = parse(db.prepare('SELECT * FROM memos WHERE id=?').get(req.params.id)); if (!m) return res.status(404).json({ error: 'not found' }); res.json({ ...m, kind_label: KIND_LABEL[m.kind], classification: CLASSIFICATION, text: memoText(m) }); });
  return r;
}
export default memosRouter;
