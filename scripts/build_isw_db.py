"""Load ISW Map Room digitisations (isw/maps/*.json, source `isw_maps`) into the SQLite build.

Called from build_db.py after the podcast tables exist; also runnable standalone against db/afpak.sqlite.
Steps per map: gazetteer-resolve the labelled anchor places -> weighted affine fit (image % -> lon / mercator-lat) ->
lat/lon for every plot (direct gazetteer hit when the plot names a place and agrees with the fit, else the fit).
Also geocodes existing podcast place entities into place_coords. Nothing here is merged into podcast entities unless
the alias resolver gives an exact existing id; otherwise the raw text is kept on the row.
"""
import csv, glob, gzip, json, math, os, re, sqlite3, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize import Resolver, fold

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
GAZ = os.path.join(ROOT, "isw", "gazetteer_afpak.tsv.gz")
SOURCE = "isw_maps"

DDL = """
CREATE TABLE IF NOT EXISTS map_sources(id TEXT PRIMARY KEY, source TEXT, url TEXT, title TEXT, page_date TEXT, isw_map_id TEXT, as_of_date TEXT,
  period_start TEXT, period_end TEXT, date_precision TEXT, map_type TEXT, geographic_extent TEXT, producer TEXT, cartographer TEXT, caption_text TEXT,
  tags TEXT, image_url TEXT, image_local TEXT, image_w INTEGER, image_h INTEGER, extraction_model TEXT, n_anchors INTEGER, n_anchors_used INTEGER,
  georef_rms_km REAL, image_corners TEXT, n_plots INTEGER);
CREATE TABLE IF NOT EXISTS map_legend(map_id TEXT, label TEXT, symbol TEXT, kind TEXT);
CREATE TABLE IF NOT EXISTS map_anchors(map_id TEXT, name TEXT, kind TEXT, country TEXT, x_pct REAL, y_pct REAL, geoname_id INTEGER, lat REAL, lon REAL,
  used_in_fit INTEGER, residual_km REAL);
CREATE TABLE IF NOT EXISTS map_plots(id INTEGER PRIMARY KEY AUTOINCREMENT, map_id TEXT, source TEXT, legend_class TEXT, marker TEXT, x_pct REAL, y_pct REAL,
  extent_pct REAL, label TEXT, place_name TEXT, admin_area TEXT, country TEXT, event_type TEXT, date TEXT, date_precision TEXT, description TEXT,
  confidence TEXT, lat REAL, lon REAL, geo_method TEXT, geo_precision_km REAL, geoname_id INTEGER, place_entity_id TEXT, event_id INTEGER, dataset TEXT DEFAULT 'real');
CREATE TABLE IF NOT EXISTS map_plot_actors(plot_id INTEGER, actor_text TEXT, entity_id TEXT, PRIMARY KEY(plot_id, actor_text));
CREATE TABLE IF NOT EXISTS map_text(map_id TEXT, kind TEXT, name TEXT, role TEXT, affiliation TEXT, place TEXT, x_pct REAL, y_pct REAL, entity_id TEXT);
CREATE TABLE IF NOT EXISTS place_coords(entity_id TEXT PRIMARY KEY, lat REAL, lon REAL, geoname_id INTEGER, feature_code TEXT, admin1 TEXT, method TEXT, confidence TEXT);
CREATE INDEX IF NOT EXISTS i_plots_map ON map_plots(map_id); CREATE INDEX IF NOT EXISTS i_plots_date ON map_plots(date);
"""

FCODE_W = {"PCLI": 0, "PPLC": 6, "PPLA": 5, "ADM1": 4, "PPLA2": 4, "ADM2": 3, "PPLA3": 2, "ADM3": 2, "PPL": 1, "PPLX": 0, "PPLL": 0}
KIND_PREF = {"province": {"ADM1": 5, "PPLA": 2}, "district": {"ADM2": 5, "ADM3": 3, "PPLA2": 3}, "city": {"PPLC": 4, "PPLA": 4, "PPLA2": 3, "PPL": 1},
             "town": {"PPL": 3, "PPLA2": 3, "PPLA3": 3}, "region": {"ADM1": 3, "ADM2": 2}}
COUNTRY_ALIAS = {"afghanistan": "AF", "pakistan": "PK"}


def fold_place(s):
    s = fold(s)
    t = re.sub(r"\b(agency|tehsil|tribal|afg|pak)\b", " ", s).strip() if s else s
    return t or s


class Gazetteer:
    def __init__(self, path=GAZ, extra=None):
        self.idx = {}; self.rows = {}
        for p in [path] + ([extra] if extra and os.path.exists(extra) else []):
            op = gzip.open if p.endswith(".gz") else open
            with op(p, "rt", encoding="utf-8") as fh:
                for line in fh:
                    f = line.rstrip("\n").split("\t")
                    if len(f) < 11: continue
                    row = dict(id=int(f[0]), name=f[1], ascii=f[2], lat=float(f[4]), lon=float(f[5]), fcode=f[6], cc=f[7], adm1=f[8], adm2=f[9], pop=int(f[10] or 0))
                    if row["id"] in self.rows: continue
                    self.rows[row["id"]] = row
                    for n in {f[1], f[2], *f[3].split(",")}:
                        k = fold_place(n)
                        if k: self.idx.setdefault(k, set()).add(row["id"])

    def lookup(self, name, country=None, kind=None, admin_area=None, near=None):
        """Best gazetteer row for a printed place name. Returns (row, score, ambiguous)."""
        if not name: return None, 0, False
        k = fold_place(name)
        ids = set(self.idx.get(k, ()))
        if not ids and k:  # try without trailing qualifiers like 'valley', 'pass'
            k2 = re.sub(r"\b(valley|pass|area|bazaar|bazar|camp|base|airport|airfield|dam|bridge|border crossing)\b", " ", k).strip()
            if k2 and k2 != k: ids = set(self.idx.get(k2, ()))
        if not ids: return None, 0, False
        cands = []
        for i in ids:
            r = self.rows[i]; s = FCODE_W.get(r["fcode"], 0) + min(3, math.log10(r["pop"] + 1))
            if country: s += 5 if r["cc"] == country else -3
            if kind in KIND_PREF: s += KIND_PREF[kind].get(r["fcode"], 0)
            if admin_area:
                fa = fold_place(admin_area)
                if fa and (fa in fold_place(r["adm1"]) or fa in fold_place(r["adm2"]) or fa == fold_place(r["name"])): s += 4
            if near is not None:
                d = hav(near[0], near[1], r["lat"], r["lon"]); s += 4 if d < 25 else (2 if d < 75 else (-3 if d > 250 else 0))
            if fold_place(r["name"]) == k or fold_place(r["ascii"]) == k: s += 1
            cands.append((s, r))
        cands.sort(key=lambda c: -c[0])
        best = cands[0]; amb = len(cands) > 1 and cands[1][0] >= best[0] - 1 and hav(best[1]["lat"], best[1]["lon"], cands[1][1]["lat"], cands[1][1]["lon"]) > 40
        return best[1], best[0], amb


def hav(lat1, lon1, lat2, lon2):
    p = math.pi / 180; a = 0.5 - math.cos((lat2 - lat1) * p) / 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    return 12742 * math.asin(math.sqrt(a))


def merc(lat): return math.log(math.tan(math.pi / 4 + math.radians(max(-85, min(85, lat))) / 2))
def unmerc(y): return math.degrees(2 * math.atan(math.exp(y)) - math.pi / 2)


class Georef:
    """Weighted affine image-% -> (lon, mercator-lat); robust to a few mislabelled anchors."""
    def __init__(self, anchors):
        # anchors: list of dict(x,y,lat,lon,w)
        self.A = None; self.rms = None; self.used = []
        pts = [a for a in anchors if a.get("lat") is not None]
        # labels stacked in a column (same x, >=3 of them) are a printed list/legend, not map positions
        for a in list(pts):
            col = [b for b in pts if abs(b["x"] - a["x"]) <= 1.5 and b is not a]
            if len(col) >= 3 and a.get("w", 1) < 0.8: a["rejected"] = -1; pts.remove(a)
        while len(pts) >= 3:
            X = np.array([[a["x"], a["y"], 1.0] for a in pts]); W = np.sqrt(np.array([a["w"] for a in pts]))
            Y = np.array([[a["lon"], merc(a["lat"])] for a in pts])
            if np.linalg.matrix_rank(X) < 3: break
            A, *_ = np.linalg.lstsq(X * W[:, None], Y * W[:, None], rcond=None)
            pred = X @ A; res = [hav(a["lat"], a["lon"], unmerc(pred[i][1]), pred[i][0]) for i, a in enumerate(pts)]
            med = float(np.median(res)); worst = int(np.argmax(res))
            if len(pts) > 4 and (res[worst] > max(15.0, 3 * med) or (res[worst] > 60.0 and med > 30.0)):
                pts[worst]["rejected"] = res[worst]; pts.pop(worst); continue
            self.A = A; self.used = pts; self.res = res
            good = [r for r, a in zip(res, pts) if a["w"] >= 0.8]  # precision estimate from town/city anchors only
            self.rms = float(np.sqrt(np.mean(np.square(good if len(good) >= 3 else res)))); break

    def to_ll(self, x, y):
        if self.A is None: return None, None
        lon, my = (np.array([x, y, 1.0]) @ self.A).tolist(); return unmerc(my), lon

    def corners(self):
        if self.A is None: return None
        return [list(self.to_ll(x, y)) for x, y in ((0, 0), (100, 0), (100, 100), (0, 100))]


def load_isw(con, R=None, gaz=None, verbose=True):
    R = R or Resolver(); gaz = gaz or Gazetteer(extra=os.path.join(ROOT, "isw", "gazetteer_extra.tsv"))
    con.executescript(DDL)
    cols = {r[1] for r in con.execute("PRAGMA table_info(events)")}
    if "source" not in cols: con.execute("ALTER TABLE events ADD COLUMN source TEXT DEFAULT 'podcast'")
    if "map_plot_id" not in cols: con.execute("ALTER TABLE events ADD COLUMN map_plot_id INTEGER")
    ent_ids = {r[0] for r in con.execute("SELECT id FROM entities")}
    man = {m["slug"]: m for m in json.load(open(os.path.join(ROOT, "isw", "manifest.json")))}
    from build_db import eid  # deterministic ids shared with the podcast build
    unmatched_actors, unmatched_places, stats = {}, {}, dict(maps=0, plots=0, geocoded=0, fit_ok=0)
    for path in sorted(glob.glob(os.path.join(ROOT, "isw", "maps", "*.json"))):
        d = json.load(open(path)); slug = d["source"]["slug"]; m = man.get(slug, d["source"]); mp = d.get("map", {}) or {}
        # ---- anchors -> georeference (two passes: provinces/capitals first, then towns resolved near the first fit)
        W = {"city": 1.0, "town": 1.0, "base": 0.8, "district": 0.5, "province": 0.3, "region": 0.2}
        anchors = []
        for a in d.get("anchors", []):
            kind = (a.get("kind") or "other").lower(); cc = a.get("country")
            anchors.append(dict(name=a.get("name"), kind=kind, country=cc if cc in ("AF", "PK") else None, x=a.get("x_pct"), y=a.get("y_pct"), lat=None, lon=None, gid=None, w=0.0))
        usable = [a for a in anchors if a["kind"] in W and a["x"] is not None and a["name"]]
        for a in usable:
            row, _, amb = gaz.lookup(a["name"], country=a["country"], kind=a["kind"])
            if row and not amb and (a["kind"] == "province" or row["fcode"] in ("PPLC", "PPLA", "ADM1")):
                a.update(lat=row["lat"], lon=row["lon"], gid=row["id"], w=W[a["kind"]])
        G0 = Georef([dict(a) for a in usable if a["w"] > 0])
        for a in usable:
            near = G0.to_ll(a["x"], a["y"]) if G0.A is not None else (None, None)
            row, _, amb = gaz.lookup(a["name"], country=a["country"], kind=a["kind"], near=near if near[0] is not None else None)
            ok = row is not None and (not amb or near[0] is not None)
            if ok and near[0] is not None and hav(near[0], near[1], row["lat"], row["lon"]) > max(60.0, 4 * (G0.rms or 15)): ok = False
            if ok: a.update(lat=row["lat"], lon=row["lon"], gid=row["id"], w=W[a["kind"]])
            else: a.update(lat=None, lon=None, gid=None, w=0.0)
        G = Georef([a for a in anchors if a["w"] > 0])
        if G.A is not None: stats["fit_ok"] += 1
        used_ids = {id(a) for a in G.used}
        con.execute("INSERT OR REPLACE INTO map_sources VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            slug, SOURCE, m.get("url"), m.get("title"), m.get("page_date"), m.get("isw_map_id"), mp.get("as_of_date"), mp.get("period_start"), mp.get("period_end"),
            mp.get("date_precision"), mp.get("map_type"), mp.get("geographic_extent"), mp.get("producer"), mp.get("cartographer"), mp.get("caption_text"),
            "; ".join(m.get("tags") or []), m.get("image_url"), m.get("thumb"), (d.get("_extraction", {}).get("image_px") or [None, None])[0],
            (d.get("_extraction", {}).get("image_px") or [None, None])[1], d.get("_extraction", {}).get("model"), len(anchors), len(G.used),
            round(G.rms, 1) if G.rms is not None else None, json.dumps(G.corners()), len(d.get("plots", []))))
        for a in anchors:
            res = G.res[G.used.index(a)] if id(a) in used_ids else a.get("rejected")
            con.execute("INSERT INTO map_anchors VALUES(?,?,?,?,?,?,?,?,?,?,?)", (slug, a["name"], a["kind"], a["country"], a["x"], a["y"], a["gid"], a["lat"], a["lon"], int(id(a) in used_ids), round(res, 1) if res is not None else None))
        for l in d.get("legend", []) or []:
            con.execute("INSERT INTO map_legend VALUES(?,?,?,?)", (slug, l.get("label"), l.get("symbol"), l.get("kind")))
        # ---- plots
        period_date = mp.get("period_end") or mp.get("as_of_date") or _iso(m.get("page_date"))
        period_prec = "day" if mp.get("period_end") or mp.get("as_of_date") else ("day" if _iso(m.get("page_date")) else None)
        for p in d.get("plots", []) or []:
            x, y = p.get("x_pct"), p.get("y_pct"); lat = lon = None; method = None; prec = None; gid = None
            alat, alon = G.to_ll(x, y) if (G.A is not None and x is not None) else (None, None)
            cc = p.get("country") or COUNTRY_ALIAS.get(fold(p.get("admin_area") or ""))
            if p.get("place_name"):
                row, _, amb = gaz.lookup(p["place_name"], country=cc if cc in ("AF", "PK") else None, admin_area=p.get("admin_area"), near=(alat, alon) if alat is not None else None)
                if row and (alat is None or hav(alat, alon, row["lat"], row["lon"]) <= max(40.0, 5 * (G.rms or 8))):
                    lat, lon, gid = row["lat"], row["lon"], row["id"]; method = "gazetteer" + ("_ambiguous" if amb else ""); prec = 5.0 if p.get("marker") == "point" else 15.0
            if lat is None and alat is not None:
                lat, lon = alat, alon; method = "affine" if p.get("marker") == "point" else "affine_centroid"; prec = round(max(2.0, G.rms or 10), 1)
            if lat is not None: stats["geocoded"] += 1
            place_ent = None
            if p.get("place_name"):
                canon = R.resolve("places", p["place_name"]); pid = eid("places", canon)
                if pid in ent_ids: place_ent = pid
                else: unmatched_places[p["place_name"]] = unmatched_places.get(p["place_name"], 0) + 1
            date = p.get("date") or period_date; dprec = "day" if p.get("date") else (period_prec if period_date else None)
            cur = con.execute("INSERT INTO map_plots(map_id,source,legend_class,marker,x_pct,y_pct,extent_pct,label,place_name,admin_area,country,event_type,date,date_precision,description,confidence,lat,lon,geo_method,geo_precision_km,geoname_id,place_entity_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                slug, SOURCE, p.get("legend_class"), p.get("marker"), x, y, p.get("extent_pct"), p.get("label"), p.get("place_name"), p.get("admin_area"), cc, p.get("event_type"),
                date, dprec, p.get("description"), p.get("confidence"), lat, lon, method, prec, gid, place_ent))
            plot_id = cur.lastrowid
            desc = (p.get("description") or p.get("legend_class") or "map plot") + f" [ISW map: {m.get('title')}]"
            ev = con.execute("INSERT INTO events(date,date_precision,type,description,place_id,place_text,episode_idx,timestamp,dataset,source,map_plot_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (
                date, dprec, p.get("event_type") or "other", desc, place_ent, p.get("place_name") or p.get("admin_area"), None, None, "real", SOURCE, plot_id)).lastrowid
            con.execute("UPDATE map_plots SET event_id=? WHERE id=?", (ev, plot_id))
            for act in dict.fromkeys(p.get("actors") or []):
                canon = R.resolve("organizations", act); oid = eid("organizations", canon); ent = oid if oid in ent_ids else None
                if not ent: unmatched_actors[act] = unmatched_actors.get(act, 0) + 1
                con.execute("INSERT OR IGNORE INTO map_plot_actors VALUES(?,?,?)", (plot_id, act, ent))
                if ent: con.execute("INSERT OR IGNORE INTO event_actors VALUES(?,?)", (ev, ent))
            stats["plots"] += 1
        for per in d.get("named_persons", []) or []:
            canon = R.resolve("persons", per.get("name")); pid = eid("persons", canon)
            con.execute("INSERT INTO map_text VALUES(?,?,?,?,?,?,?,?,?)", (slug, "person", per.get("name"), per.get("role"), per.get("affiliation"), per.get("place"), per.get("x_pct"), per.get("y_pct"), pid if pid in ent_ids else None))
        for o in d.get("named_orgs", []) or []:
            canon = R.resolve("organizations", o); oid = eid("organizations", canon)
            con.execute("INSERT INTO map_text VALUES(?,?,?,?,?,?,?,?,?)", (slug, "org", o, None, None, None, None, None, oid if oid in ent_ids else None))
        for t in d.get("text_blocks", []) or []:
            con.execute("INSERT INTO map_text VALUES(?,?,?,?,?,?,?,?,?)", (slug, "text", t, None, None, None, None, None, None))
        stats["maps"] += 1
    # ---- geocode podcast places
    for pid, name, country, parent, ptype in con.execute("SELECT id, name, country, parent_place, place_type FROM entities WHERE kind='place' AND dataset='real'").fetchall():
        cc = {"afghanistan": "AF", "pakistan": "PK"}.get(fold(country or ""), None)
        row, score, amb = gaz.lookup(name, country=cc, kind=(ptype or "").lower() if ptype in ("province", "district", "city", "town") else None, admin_area=parent)
        if row and (cc or row["cc"] in ("AF", "PK")):
            con.execute("INSERT OR REPLACE INTO place_coords VALUES(?,?,?,?,?,?,?,?)", (pid, row["lat"], row["lon"], row["id"], row["fcode"], row["adm1"], "gazetteer", "low" if amb else ("high" if score >= 8 else "medium")))
    con.commit()
    if verbose:
        print("isw:", stats, "| place_coords:", con.execute("SELECT count(*) FROM place_coords").fetchone()[0])
        print("  unmatched actors:", sorted(unmatched_actors.items(), key=lambda kv: -kv[1])[:25])
        print("  unmatched places:", len(unmatched_places), sorted(unmatched_places.items(), key=lambda kv: -kv[1])[:15])
    return stats


def _iso(s):
    if not s: return None
    if re.match(r"\d{4}-\d{2}-\d{2}", s): return s[:10]
    import datetime
    for f in ("%B %d, %Y", "%b %d, %Y"):
        try: return datetime.datetime.strptime(s.strip(), f).strftime("%Y-%m-%d")
        except ValueError: pass
    return None


def export_isw(con, outdir):
    def dump(q, name):
        cur = con.execute(q); cols = [c[0] for c in cur.description]; rows = cur.fetchall()
        with open(os.path.join(outdir, name + ".csv"), "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(cols); w.writerows(rows)
    dump("SELECT * FROM map_sources ORDER BY coalesce(as_of_date, period_end, page_date)", "isw_maps")
    dump("""SELECT p.*, group_concat(a.actor_text, '; ') AS actors FROM map_plots p LEFT JOIN map_plot_actors a ON a.plot_id=p.id GROUP BY p.id ORDER BY p.map_id, p.id""", "isw_plots")
    dump("SELECT pc.*, e.name, e.country, e.parent_place FROM place_coords pc JOIN entities e ON e.id=pc.entity_id ORDER BY e.name", "place_coords")
    feats = []
    for r in con.execute("""SELECT p.id,p.map_id,m.title,m.url,m.image_local,p.legend_class,p.marker,p.event_type,p.date,p.date_precision,p.description,p.place_name,p.admin_area,p.country,
                               p.confidence,p.lat,p.lon,p.geo_method,p.geo_precision_km,p.place_entity_id,p.event_id,group_concat(a.actor_text,'; '),group_concat(a.entity_id,';'),p.x_pct,p.y_pct,p.extent_pct
                            FROM map_plots p JOIN map_sources m ON m.id=p.map_id LEFT JOIN map_plot_actors a ON a.plot_id=p.id WHERE p.lat IS NOT NULL GROUP BY p.id"""):
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(r[16], 5), round(r[15], 5)]},
                      "properties": dict(plot_id=r[0], map_id=r[1], map_title=r[2], map_url=r[3], image=r[4], legend_class=r[5], marker=r[6], event_type=r[7], date=r[8], date_precision=r[9],
                                         description=r[10], place_name=r[11], admin_area=r[12], country=r[13], confidence=r[14], geo_method=r[17], geo_precision_km=r[18],
                                         place_entity_id=r[19], event_id=r[20], actors=(r[21] or "").split("; ") if r[21] else [], actor_entity_ids=[x for x in (r[22] or "").split(";") if x],
                                         x_pct=r[23], y_pct=r[24], extent_pct=r[25], source=SOURCE)})
    json.dump({"type": "FeatureCollection", "features": feats}, open(os.path.join(outdir, "isw_plots.geojson"), "w"), ensure_ascii=False)
    maps = [dict(zip([c[0] for c in con.execute("SELECT * FROM map_sources").description], r)) for r in con.execute("SELECT * FROM map_sources ORDER BY coalesce(as_of_date, period_end, page_date)")]
    for mm in maps: mm["image_corners"] = json.loads(mm["image_corners"]) if mm.get("image_corners") else None; mm["legend"] = [dict(label=a, symbol=b, kind=c) for a, b, c in con.execute("SELECT label,symbol,kind FROM map_legend WHERE map_id=?", (mm["id"],))]
    json.dump(maps, open(os.path.join(outdir, "isw_maps.json"), "w"), indent=0, ensure_ascii=False)
    pc = [dict(entity_id=r[0], name=r[1], lat=r[2], lon=r[3], confidence=r[4]) for r in con.execute("SELECT pc.entity_id, e.name, pc.lat, pc.lon, pc.confidence FROM place_coords pc JOIN entities e ON e.id=pc.entity_id")]
    json.dump(pc, open(os.path.join(outdir, "place_coords.json"), "w"), ensure_ascii=False)
    return len(feats)


if __name__ == "__main__":
    dbp = os.path.join(ROOT, "db", "afpak.sqlite"); con = sqlite3.connect(dbp)
    for t in ("map_sources", "map_legend", "map_anchors", "map_plots", "map_plot_actors", "map_text", "place_coords"): con.execute(f"DROP TABLE IF EXISTS {t}")
    con.execute("DELETE FROM events WHERE source='isw_maps'") if "source" in {r[1] for r in con.execute("PRAGMA table_info(events)")} else None
    load_isw(con); print("geojson features:", export_isw(con, os.path.join(ROOT, "db", "exports")))
