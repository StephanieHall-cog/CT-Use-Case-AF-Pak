// fbi.gov blocks server-side fetches (403); pull profile photos through the real browser (CDP) into standalone/photos.json for build_standalone.mjs
const { chromium } = require('playwright'); const fs = require('fs'); const Database = require('better-sqlite3');
(async () => {
  const db = new Database(process.argv[2] || '../db/afpak_demo.sqlite', { readonly: true }); const urls = db.prepare("SELECT DISTINCT photo_url u FROM profiles WHERE photo_url LIKE 'http%'").all().map(x => x.u);
  const out = fs.existsSync('standalone/photos.json') ? JSON.parse(fs.readFileSync('standalone/photos.json', 'utf8')) : {};
  const b = await chromium.connectOverCDP(process.env.CDP || 'http://localhost:29229'); const pg = await b.contexts()[0].newPage(); await pg.goto('https://www.fbi.gov/wanted/terrorism', { waitUntil: 'domcontentloaded' }); await pg.waitForTimeout(1500);
  for (const u of urls) { if (out[u]) continue; try { out[u] = await pg.evaluate(async u => { const r = await fetch(u); if (!r.ok) throw new Error(r.status); const bl = await r.blob(); return await new Promise(res => { const fr = new FileReader(); fr.onload = () => res(fr.result); fr.readAsDataURL(bl); }); }, u); fs.writeFileSync('standalone/photos.json', JSON.stringify(out)); console.log('ok', u); } catch (e) { console.log('skip', u, e.message); } }
  fs.writeFileSync('standalone/photos.json', JSON.stringify(out)); console.log(Object.keys(out).length, 'photos cached'); await pg.close(); process.exit(0);
})().catch(e => { console.error(e.message); process.exit(1); });
