import { randomBytes, scryptSync, timingSafeEqual } from 'crypto';
const audit = (db, user, action, target) => { try { db.prepare('INSERT INTO audit(user,action,target) VALUES (?,?,?)').run(user || null, action, target || null); } catch {} };

export const ROLES = ['viewer', 'analyst', 'instructor', 'admin'];
const RANK = Object.fromEntries(ROLES.map((r, i) => [r, i]));
const SESSION_HOURS = 12;

export function hashPassword(pw, salt = randomBytes(16).toString('hex')) {
  return { salt, hash: scryptSync(String(pw), salt, 64).toString('hex') };
}
export function verifyPassword(pw, salt, hash) {
  const h = scryptSync(String(pw), salt, 64);
  const b = Buffer.from(hash, 'hex');
  return h.length === b.length && timingSafeEqual(h, b);
}

export function createUser(db, username, password, role = 'viewer') {
  if (!ROLES.includes(role)) throw new Error('bad role');
  if (!/^[a-z0-9_.-]{3,32}$/i.test(username)) throw new Error('bad username');
  if (String(password).length < 8) throw new Error('password too short (8+)');
  const { salt, hash } = hashPassword(password);
  db.prepare('INSERT INTO users(username,pass_hash,salt,role) VALUES (?,?,?,?)').run(username.toLowerCase(), hash, salt, role);
}

export function login(db, username, password, ip) {
  const u = db.prepare('SELECT * FROM users WHERE username=?').get(String(username || '').toLowerCase());
  if (!u || !verifyPassword(password, u.salt, u.pass_hash)) { audit(db, username, 'login_fail', ip); return null; }
  const token = randomBytes(32).toString('base64url');
  const exp = new Date(Date.now() + SESSION_HOURS * 3600e3).toISOString();
  db.prepare('INSERT INTO sessions(token,user_id,created_at,expires_at) VALUES (?,?,datetime(\'now\'),?)').run(token, u.id, exp);
  db.prepare('UPDATE users SET last_login=datetime(\'now\') WHERE id=?').run(u.id);
  db.prepare('DELETE FROM sessions WHERE expires_at < datetime(\'now\')').run();
  audit(db, u.username, 'login', ip);
  return { token, user: { id: u.id, username: u.username, role: u.role } };
}

export function logout(db, token) { db.prepare('DELETE FROM sessions WHERE token=?').run(token); }

export function sessionUser(db, token) {
  if (!token) return null;
  return db.prepare(`SELECT u.id, u.username, u.role FROM sessions s JOIN users u ON u.id=s.user_id
     WHERE s.token=? AND s.expires_at > datetime('now')`).get(token) || null;
}

export function parseCookies(h = '') {
  return Object.fromEntries(h.split(';').map(s => s.trim().split('=')).filter(p => p[0]).map(([k, ...v]) => [k, decodeURIComponent(v.join('='))]));
}

export function requireRole(min) {
  return (req, res, next) => {
    if (!req.user) return res.status(401).json({ error: 'auth required' });
    if (RANK[req.user.role] < RANK[min]) return res.status(403).json({ error: `${min} role required` });
    next();
  };
}
export function atLeast(role, min) { return RANK[role] >= RANK[min]; }
