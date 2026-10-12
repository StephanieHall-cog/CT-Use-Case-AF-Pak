#!/usr/bin/env python3
"""Merge per-episode extraction JSON (raw/extractions/*.json) and per-document extraction JSON (raw/documents/extractions/*.json)
into db/afpak.sqlite + db/exports/*.
Usage: python3 scripts/build_db.py [--synthetic synthetic/*.json]
Every row carries provenance (episode idx OR doc_id, timestamp/page, quote) and a `dataset` column: 'real' or 'synthetic'.
"""
import json, glob, os, sqlite3, csv, argparse, re, hashlib
from normalize import Resolver, fold

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESENTERS = {fold(x) for x in ["Bill Roggio","Thomas Joscelyn","Tom Joscelyn","Caleb Weiss","Joe Truzman","David Daoud","Behnam Ben Taleblu","Ahmad Sharawi","Preston Stewart"]}

DDL = """
CREATE TABLE episodes(idx INTEGER PRIMARY KEY, guid TEXT, title TEXT, published TEXT, duration_s INTEGER, audio_url TEXT, description TEXT, transcript_path TEXT);
CREATE TABLE documents(doc_id TEXT PRIMARY KEY, kind TEXT, title TEXT, authors TEXT, publisher TEXT, published TEXT, url TEXT, pages INTEGER, note TEXT, text_path TEXT);
CREATE TABLE entities(id TEXT PRIMARY KEY, kind TEXT, name TEXT, dataset TEXT DEFAULT 'real',
  role TEXT, nationality TEXT, status TEXT, status_detail TEXT, org_type TEXT, country TEXT, place_type TEXT, parent_place TEXT,
  n_episodes INTEGER DEFAULT 0, n_documents INTEGER DEFAULT 0, first_mentioned TEXT, last_mentioned TEXT, is_presenter_or_guest INTEGER DEFAULT 0, notes TEXT, sources TEXT DEFAULT 'podcast');
CREATE TABLE aliases(entity_id TEXT, alias TEXT, source TEXT, PRIMARY KEY(entity_id, alias));
CREATE TABLE memberships(entity_id TEXT, org_id TEXT, episode_idx INTEGER, doc_id TEXT DEFAULT '', PRIMARY KEY(entity_id, org_id, episode_idx, doc_id));
CREATE TABLE mentions(id INTEGER PRIMARY KEY AUTOINCREMENT, entity_id TEXT, episode_idx INTEGER, timestamp TEXT, quote TEXT, role_in_episode TEXT, locations TEXT, doc_id TEXT);
CREATE TABLE relationships(id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT, target_id TEXT, type TEXT, detail TEXT, date TEXT, confidence TEXT,
  episode_idx INTEGER, timestamp TEXT, quote TEXT, dataset TEXT DEFAULT 'real', doc_id TEXT, source TEXT DEFAULT 'podcast');
CREATE TABLE profiles(id INTEGER PRIMARY KEY AUTOINCREMENT, entity_id TEXT, source TEXT, reference TEXT, list_name TEXT, category TEXT, name TEXT, name_original_script TEXT,
  title TEXT, designation TEXT, nationality TEXT, dob TEXT, pob TEXT, addresses TEXT, documents TEXT, physical TEXT, languages TEXT, reward_text TEXT,
  listed_on TEXT, last_updated TEXT, status TEXT, summary TEXT, narrative TEXT, url TEXT, photo_url TEXT, interpol_link TEXT, raw TEXT);
CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, date_precision TEXT, type TEXT, description TEXT, place_id TEXT, place_text TEXT,
  episode_idx INTEGER, timestamp TEXT, dataset TEXT DEFAULT 'real', doc_id TEXT);
CREATE TABLE event_geo(event_id INTEGER PRIMARY KEY, lat REAL, lon REAL, precision_km REAL, method TEXT, dataset TEXT DEFAULT 'real');
CREATE TABLE sites(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, kind TEXT, operator TEXT, status TEXT, place TEXT, lat REAL, lon REAL, precision_km REAL, verified INTEGER DEFAULT 0, source TEXT, note TEXT, dataset TEXT DEFAULT 'real');
CREATE TABLE target_cards(entity_id TEXT PRIMARY KEY, objective_name TEXT, kunyas TEXT, name_variants TEXT, tribe TEXT, sub_tribe TEXT, network TEXT, role_current TEXT, role_history TEXT,
  priority TEXT, status TEXT, dob TEXT, pob TEXT, home_area TEXT, summary TEXT, last_hit_id INTEGER, dataset TEXT DEFAULT 'synthetic');
CREATE TABLE selectors(id TEXT PRIMARY KEY, entity_id TEXT, kind TEXT, value TEXT, label TEXT, provider TEXT, platform TEXT, country TEXT, first_seen TEXT, last_seen TEXT, confidence TEXT, dataset TEXT DEFAULT 'synthetic');
CREATE TABLE selector_links(a_id TEXT, b_id TEXT, relation TEXT, evidence TEXT, confidence TEXT, dataset TEXT DEFAULT 'synthetic', PRIMARY KEY(a_id, b_id, relation));
CREATE TABLE location_hits(id INTEGER PRIMARY KEY AUTOINCREMENT, entity_id TEXT, selector_id TEXT, kind TEXT, ts TEXT, lat REAL, lon REAL, precision_km REAL, place TEXT, detail TEXT, confidence TEXT, dataset TEXT DEFAULT 'synthetic');
CREATE INDEX i_hit_e ON location_hits(entity_id, ts);
CREATE TABLE event_actors(event_id INTEGER, entity_id TEXT, PRIMARY KEY(event_id, entity_id));
CREATE TABLE claims(id INTEGER PRIMARY KEY AUTOINCREMENT, episode_idx INTEGER, claim TEXT, doc_id TEXT);
CREATE TABLE sources_cited(id INTEGER PRIMARY KEY AUTOINCREMENT, episode_idx INTEGER, source TEXT, doc_id TEXT);
CREATE TABLE person_status_history(entity_id TEXT, status TEXT, detail TEXT, episode_idx INTEGER, published TEXT, doc_id TEXT);
CREATE INDEX i_rel_s ON relationships(source_id); CREATE INDEX i_rel_t ON relationships(target_id);
CREATE INDEX i_men_e ON mentions(entity_id); CREATE INDEX i_ev_d ON events(date); CREATE INDEX i_rel_doc ON relationships(doc_id);
"""

def eid(kind, name, dataset="real"):
    p = {"persons":"P","organizations":"O","places":"L"}[kind]
    h = hashlib.sha1(f"{dataset}|{kind}|{fold(name)}".encode()).hexdigest()[:10]
    return f"{'S' if dataset=='synthetic' else ''}{p}-{h}"

PARTICLES = {"al", "el", "bin", "ibn", "ul", "ur", "abd", "ud", "din", "and", "of", "the"}
def smart_title(s):
    out = []
    for i, w in enumerate(s.split()):
        parts = [p.lower() for p in w.split("-")]
        parts = [p if (p in PARTICLES and i > 0) else p.capitalize() for p in parts]
        out.append("-".join(parts))
    return " ".join(out)

def load_profiles(con, ents, ent):
    """Attach external biodata (UN 1988 Sanctions List, FBI Most Wanted/Seeking Information – Terrorism) to the real dataset.
    Identity matches to podcast-derived people are curated in scripts/profile_matches.json; everything else becomes its own entity.
    Family / associate links stated in the UN COMMENTS field become relationships with source='un_1988' and the sentence as the quote."""
    matches = json.load(open(f"{ROOT}/scripts/profile_matches.json")) if os.path.exists(f"{ROOT}/scripts/profile_matches.json") else {}
    def ins(entity_id, source, ref, rec, **f):
        con.execute("""INSERT INTO profiles(entity_id,source,reference,list_name,category,name,name_original_script,title,designation,nationality,dob,pob,addresses,documents,physical,
                       languages,reward_text,listed_on,last_updated,status,summary,narrative,url,photo_url,interpol_link,raw) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (entity_id, source, ref, f.get("list_name"), f.get("category"), rec.get("name"), f.get("name_original_script"), f.get("title"), f.get("designation"), f.get("nationality"),
                     f.get("dob"), f.get("pob"), f.get("addresses"), f.get("documents"), f.get("physical"), f.get("languages"), f.get("reward_text"), f.get("listed_on"), f.get("last_updated"),
                     f.get("status"), f.get("summary"), f.get("narrative"), f.get("url"), f.get("photo_url"), f.get("interpol_link"), json.dumps(rec, ensure_ascii=False)))
    def attach(kind, rec_name, aliases, source, curated, **fields):
        canon = curated or smart_title(rec_name)
        i = ent(kind, canon, "real", None, **fields)
        if not i: return None
        ents[i]["sources"].add(source)
        for al in [rec_name] + list(aliases):
            if al and fold(al) != fold(ents[i]["name"]): ents[i]["aliases"].setdefault(al.strip(), source)
        return i
    # ---- UN 1988 (Taliban) sanctions list ----
    unp = f"{ROOT}/raw/sanctions/un_1988.json"
    if os.path.exists(unp):
        recs = json.load(open(unp)); by_ref = {}
        for r in recs:
            kind = "persons" if r["kind"] == "persons" else "organizations"
            nm = re.sub(r"\s*\(HQN\)$", "", r["name"])
            i = attach(kind, nm, [a["name"] for a in r["aliases"]] + ([r["name_original_script"]] if r.get("name_original_script") else []), "un_1988",
                       matches.get("un_1988", {}).get(r["reference_number"]),
                       role=r.get("designation") or r.get("title"), nationality=r.get("nationality"), notes=f"UN 1988 List {r['reference_number']}")
            if not i: continue
            by_ref[r["reference_number"]] = i
            narr = r.get("narrative") or {}
            ins(i, "un_1988", r["reference_number"], r, list_name="UN Security Council 1988 (Taliban) Sanctions List", category="entity" if kind == "organizations" else "individual",
                name_original_script=r.get("name_original_script"), title=r.get("title"), designation=r.get("designation"), nationality=r.get("nationality"),
                dob="; ".join(r.get("dob", [])), pob="; ".join(r.get("pob", [])), addresses="; ".join(r.get("addresses", [])), documents="; ".join(r.get("documents", [])),
                listed_on=r.get("listed_on"), last_updated=r.get("last_updated"), summary=r.get("comments"), narrative=narr.get("text"), url=narr.get("url"),
                interpol_link=r.get("interpol_link"), status="deceased (reported)" if re.search(r"deceased", r.get("comments", ""), re.I) else None)
        for r in recs:
            si = by_ref.get(r["reference_number"])
            for l in r.get("links", []):
                ti = by_ref.get(l["target_ref"])
                if not si or not ti or si == ti: continue
                a, b = (ti, si) if l.get("reverse") else (si, ti)
                con.execute("INSERT INTO relationships(source_id,target_id,type,detail,confidence,quote,dataset,source) VALUES(?,?,?,?,?,?,?,?)",
                            (a, b, l["type"], f"UN 1988 List {r['reference_number']} → {l['target_ref']}", "stated", l["quote"], "real", "un_1988"))
    # ---- FBI Most Wanted Terrorists / Seeking Information – Terrorism / Domestic Terrorism ----
    fbp = f"{ROOT}/raw/sanctions/fbi_wanted.json"
    if os.path.exists(fbp):
        for r in json.load(open(fbp)):
            i = None
            if r["kind"] == "persons":
                i = attach("persons", r["name"], r.get("aliases", []), "fbi_wanted", matches.get("fbi_wanted", {}).get(r["uid"]),
                           nationality=r.get("nationality"), notes=f"FBI {r['category']}")
                if not i: continue
            summary = "\n\n".join(x for x in (r.get("description"), r.get("caution"), r.get("details"), r.get("remarks"), r.get("additional_information")) if x)
            ins(i, "fbi_wanted", r["uid"], r, list_name="FBI Wanted – Terrorism", category=r["category"], nationality=r.get("nationality"), dob="; ".join(r.get("dob", [])), pob=r.get("pob"),
                addresses="; ".join(r.get("possible_countries", [])), physical=json.dumps(r.get("physical", {})), languages="; ".join(r.get("languages", [])),
                reward_text=r.get("reward_text"), listed_on=(r.get("publication") or "")[:10], last_updated=(r.get("modified") or "")[:10], status=r.get("warning_message"),
                summary=summary, url=r.get("url"), photo_url=r.get("photo_url"))

def load_targets(con, ents, files):
    """Target-tracking layer: public-reference `sites` (always) and, for synthetic files with scenario_kind='targets',
    baseball-card fields, selectors (phone/IMSI/IMEI/e-mail/social/CMA/vehicle), selector correlations and location hits.
    Selector/hit rows attach to the SYNTHETIC person ids only (eid(..., 'synthetic')); never to a real person."""
    sp = f"{ROOT}/synthetic/sites_reference.json"
    if os.path.exists(sp):
        for r in json.load(open(sp)):
            con.execute("INSERT INTO sites(name,kind,operator,status,place,lat,lon,precision_km,verified,source,note,dataset) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (r["name"], r["kind"], r.get("operator"), r.get("status"), r.get("place"), r["lat"], r["lon"], r.get("precision_km"), r.get("verified", 0), r.get("source", "public_reference"), r.get("note"), "real"))
    for f, dataset in files:
        d = json.load(open(f))
        if d.get("scenario_kind") != "targets" or dataset != "synthetic": continue
        R = Resolver(); byname = {}
        for c in d.get("target_cards", []): byname[c["entity"]] = eid("persons", R.resolve("persons", c["name"]), "synthetic")
        for c in d.get("target_cards", []):
            i = byname[c["entity"]]
            if i not in ents: continue
            con.execute("""INSERT OR REPLACE INTO target_cards(entity_id,objective_name,kunyas,name_variants,tribe,sub_tribe,network,role_current,role_history,priority,status,dob,pob,home_area,summary,dataset)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (i, c.get("objective_name"), json.dumps(c.get("kunyas", [])), json.dumps(c.get("name_variants", [])), c.get("tribe"), c.get("sub_tribe"), c.get("network"),
                        c.get("role_current"), json.dumps(c.get("role_history", [])), c.get("priority"), c.get("status"), c.get("dob"), c.get("pob"), c.get("home_area"), c.get("summary"), "synthetic"))
        for sel in d.get("selectors", []):
            i = byname.get(sel["entity"])
            if not i: continue
            con.execute("INSERT OR REPLACE INTO selectors(id,entity_id,kind,value,label,provider,platform,country,first_seen,last_seen,confidence,dataset) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (sel["id"], i, sel["kind"], sel["value"], sel.get("label"), sel.get("provider"), sel.get("platform"), sel.get("country"), sel.get("first_seen"), sel.get("last_seen"), sel.get("confidence"), "synthetic"))
        for l in d.get("selector_links", []):
            con.execute("INSERT OR IGNORE INTO selector_links VALUES(?,?,?,?,?,?)", (l["a"], l["b"], l["relation"], l.get("evidence"), l.get("confidence"), "synthetic"))
        for h in d.get("location_hits", []):
            i = byname.get(h["entity"])
            if not i: continue
            con.execute("INSERT INTO location_hits(entity_id,selector_id,kind,ts,lat,lon,precision_km,place,detail,confidence,dataset) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (i, h.get("selector"), h["kind"], h["ts"], h["lat"], h["lon"], h.get("precision_km"), h.get("place"), h.get("detail"), h.get("confidence"), "synthetic"))
        con.execute("UPDATE target_cards SET last_hit_id=(SELECT id FROM location_hits h WHERE h.entity_id=target_cards.entity_id ORDER BY ts DESC LIMIT 1)")
        for (sid_,) in con.execute("SELECT id FROM selectors").fetchall():
            con.execute("UPDATE selectors SET last_seen=(SELECT max(ts) FROM location_hits WHERE selector_id=?) WHERE id=? AND last_seen IS NULL", (sid_, sid_))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--synthetic", nargs="*", default=[]); ap.add_argument("--no-isw", action="store_true"); a = ap.parse_args()
    R = Resolver()
    os.makedirs(f"{ROOT}/db/exports", exist_ok=True)
    dbp = f"{ROOT}/db/afpak.sqlite"
    if os.path.exists(dbp): os.remove(dbp)
    con = sqlite3.connect(dbp); con.executescript(DDL)
    eps = {e["idx"]: e for e in json.load(open(f"{ROOT}/raw/episodes_afpak.json"))} if os.path.exists(f"{ROOT}/raw/episodes_afpak.json") else {}
    ents = {}   # id -> row dict
    def ent(kind, name, dataset, ep, **fields):
        canon = R.resolve(kind, name)
        if not canon: return None
        if kind == "persons" and fold(canon) in PRESENTERS: return None
        i = eid(kind, canon, dataset)
        if dataset == "synthetic" and kind != "persons" and eid(kind, canon, "real") in ents:
            i = eid(kind, canon, "real")   # synthetic rows may attach to real orgs/places; never to real persons
        row = ents.setdefault(i, {"id": i, "kind": kind[:-1], "name": canon, "dataset": dataset, "aliases": {}, "eps": set(), "docs": set(), "pubs": [], "sources": set()})
        if fold(name) != fold(canon): row["aliases"].setdefault(name.strip(), "extraction")
        if ep is not None:
            if "doc_id" in ep: row["docs"].add(ep["doc_id"]); row["sources"].add("document")
            elif "idx" in ep: row["eps"].add(ep["idx"]); row["sources"].add("podcast")
            row["pubs"].append(ep.get("published",""))
        for k, v in fields.items():
            if v and not row.get(k): row[k] = v
        return i

    files = ([(f, "real") for f in sorted(glob.glob(f"{ROOT}/raw/extractions/*.json"))]
             + [(f, "real") for f in sorted(glob.glob(f"{ROOT}/raw/documents/extractions/*.json")) if not os.path.basename(f).startswith("_")]
             + [(f, "synthetic") for f in a.synthetic])
    GLOBAL_KIND = {}
    for _f, _ds in files:
        _d = json.load(open(_f))
        for _kind in ("persons", "organizations", "places"):
            for _it in _d.get(_kind, []) or []:
                for _nm in [_it.get("name")] + (_it.get("aliases", []) or []):
                    if _nm: GLOBAL_KIND.setdefault(fold(_nm), _kind)
    for f, dataset in files:
        d = json.load(open(f)); ep = d.get("episode") or d.get("document") or {}; idx = ep.get("idx"); doc = ep.get("doc_id")
        local = dict(GLOBAL_KIND)
        for kind in ("persons", "organizations", "places"):
            for it in d.get(kind, []) or []:
                for nm in [it.get("name")] + (it.get("aliases", []) or []):
                    if nm: local.setdefault(fold(nm), kind)
        def kind_of(name, default):
            k, n = R.resolve_any(name)
            if k: return k, n
            return local.get(fold(name), default), name.strip()
        if dataset == "real" and idx is not None:
            m = eps.get(idx, {})
            con.execute("INSERT OR REPLACE INTO episodes VALUES(?,?,?,?,?,?,?,?)", (idx, ep.get("guid"), ep.get("title"), ep.get("published"),
                        m.get("dur"), m.get("audio"), m.get("desc"), f"raw/transcripts/{os.path.basename(f)[:-5]}.txt"))
        if dataset == "real" and doc is not None:
            con.execute("INSERT OR REPLACE INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)", (doc, ep.get("kind"), ep.get("title"), ep.get("authors"), ep.get("publisher"),
                        ep.get("published"), ep.get("url"), ep.get("pages"), ep.get("note"), f"raw/documents/{doc}.txt"))
        for p in d.get("persons", []) or []:
            i = ent("persons", p.get("name"), dataset, ep, role=p.get("role"), nationality=p.get("nationality_or_origin"), status=p.get("status"),
                    status_detail=p.get("status_detail"), is_presenter_or_guest=1 if p.get("is_presenter_or_guest") else 0)
            if not i: continue
            for al in p.get("aliases", []) or []: ents[i]["aliases"].setdefault(al, "extraction")
            for o in p.get("organizations", []) or []:
                oi = ent("organizations", o, dataset, ep)
                if oi: con.execute("INSERT OR IGNORE INTO memberships VALUES(?,?,?,?)", (i, oi, idx, doc or ""))
            for fam in p.get("family", []) or []:
                fi = ent("persons", fam.get("name"), dataset, ep)
                if fi: con.execute("INSERT INTO relationships(source_id,target_id,type,detail,confidence,episode_idx,dataset,doc_id) VALUES(?,?,?,?,?,?,?,?)",
                                   (i, fi, "family", "derived:person.family — " + ((f"{fam.get('relation')} ({ents[i]['name']} is {fam.get('relation')} {ents[fi]['name']})" if fam.get('relation').strip().endswith(' of') else f"{fam.get('relation')} ({ents[fi]['name']} is {fam.get('relation')} of {ents[i]['name']})")
                                    if fam.get("relation") else "family"), "stated", idx, dataset, doc))
            locs = ", ".join(p.get("locations", []) or [])
            for l in p.get("locations", []) or []: ent("places", l, dataset, ep)
            ms = p.get("mentions", []) or [{}]
            for mnt in ms:
                con.execute("INSERT INTO mentions(entity_id,episode_idx,timestamp,quote,role_in_episode,locations,doc_id) VALUES(?,?,?,?,?,?,?)",
                            (i, idx, mnt.get("timestamp"), mnt.get("quote"), p.get("role"), locs, doc))
            if p.get("status"):
                con.execute("INSERT INTO person_status_history VALUES(?,?,?,?,?,?)", (i, p.get("status"), p.get("status_detail"), idx, ep.get("published"), doc))
        for o in d.get("organizations", []) or []:
            i = ent("organizations", o.get("name"), dataset, ep, org_type=o.get("type"), country=o.get("country_base"), notes=o.get("notes"))
            if not i: continue
            for al in o.get("aliases", []) or []: ents[i]["aliases"].setdefault(al, "extraction")
            for pa in o.get("parent_or_allies", []) or []:
                pi = ent("organizations", pa, dataset, ep)
                if pi and pi != i: con.execute("INSERT INTO relationships(source_id,target_id,type,detail,confidence,episode_idx,dataset,doc_id) VALUES(?,?,?,?,?,?,?,?)", (i, pi, "allied_with", "derived:organization.parent_or_allies", "stated", idx, dataset, doc))
            for rv in o.get("rivals", []) or []:
                ri = ent("organizations", rv, dataset, ep)
                if ri and ri != i: con.execute("INSERT INTO relationships(source_id,target_id,type,detail,confidence,episode_idx,dataset,doc_id) VALUES(?,?,?,?,?,?,?,?)", (i, ri, "rival_of", "derived:organization.rivals", "stated", idx, dataset, doc))
        for pl in d.get("places", []) or []:
            ent("places", pl.get("name"), dataset, ep, place_type=pl.get("type"), country=pl.get("country"), parent_place=pl.get("parent"), notes=pl.get("significance"))
        for r in d.get("relationships", []) or []:
            ks, s = kind_of(r.get("source", ""), "persons"); kt, t = kind_of(r.get("target", ""), "places" if r.get("type") == "located_in" else "persons")
            si = ent(ks, s, dataset, ep) if s else None
            ti = ent(kt, t, dataset, ep) if t else None
            if not si or not ti: continue
            con.execute("INSERT INTO relationships(source_id,target_id,type,detail,date,confidence,episode_idx,timestamp,quote,dataset,doc_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (si, ti, r.get("type"), r.get("detail"), r.get("date"), r.get("confidence"), idx, r.get("timestamp"), r.get("quote"), dataset, doc))
        for ev in d.get("events", []) or []:
            pi = ent("places", ev["place"], dataset, ep) if ev.get("place") else None
            cur = con.execute("INSERT INTO events(date,date_precision,type,description,place_id,place_text,episode_idx,timestamp,dataset,doc_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
                              (ev.get("date"), ev.get("date_precision"), ev.get("type"), ev.get("description"), pi, ev.get("place"), idx, ev.get("timestamp"), dataset, doc))
            if ev.get("lat") is not None and ev.get("lon") is not None:
                con.execute("INSERT OR REPLACE INTO event_geo VALUES(?,?,?,?,?,?)", (cur.lastrowid, ev["lat"], ev["lon"], ev.get("precision_km"), "scenario", dataset))
            for ac in ev.get("actors", []) or []:
                k, n = kind_of(ac, "persons"); ai = ent(k, n, dataset, ep)
                if ai: con.execute("INSERT OR IGNORE INTO event_actors VALUES(?,?)", (cur.lastrowid, ai))
        for c in d.get("key_claims", []) or []: con.execute("INSERT INTO claims(episode_idx,claim,doc_id) VALUES(?,?,?)", (idx, c, doc))
        for s in d.get("sources_cited", []) or []: con.execute("INSERT INTO sources_cited(episode_idx,source,doc_id) VALUES(?,?,?)", (idx, s, doc))

    load_profiles(con, ents, ent)
    load_targets(con, ents, files)

    # entity-level resolution of unresolved person names that are a substring/last-name match of a canonical (conservative): skipped on purpose; see review_names.py
    for i, r in ents.items():
        pubs = sorted(p for p in r["pubs"] if p)
        con.execute("INSERT INTO entities(id,kind,name,dataset,role,nationality,status,status_detail,org_type,country,place_type,parent_place,n_episodes,n_documents,first_mentioned,last_mentioned,is_presenter_or_guest,notes,sources) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (i, r["kind"], r["name"], r["dataset"], r.get("role"), r.get("nationality"), r.get("status"), r.get("status_detail"), r.get("org_type"), r.get("country"),
                     r.get("place_type"), r.get("parent_place"), len(r["eps"]), len(r["docs"]), pubs[0] if pubs else None, pubs[-1] if pubs else None, r.get("is_presenter_or_guest", 0), r.get("notes"),
                     ",".join(sorted(r["sources"])) or ("synthetic" if r["dataset"] == "synthetic" else "podcast")))
        for al, src in r["aliases"].items():
            if fold(al) != fold(r["name"]): con.execute("INSERT OR IGNORE INTO aliases VALUES(?,?,?)", (i, al, src))
    con.execute("UPDATE relationships SET source='document' WHERE doc_id IS NOT NULL")
    con.commit()
    if os.path.isdir(f"{ROOT}/isw/maps") and not a.no_isw:
        from build_isw_db import load_isw, export_isw
        load_isw(con, R)

    # exports
    def dump(q, name):
        cur = con.execute(q); cols = [c[0] for c in cur.description]; rows = cur.fetchall()
        with open(f"{ROOT}/db/exports/{name}.csv", "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(cols); w.writerows(rows)
        return cols, rows
    dump("SELECT * FROM entities ORDER BY kind, n_episodes DESC, name", "entities")
    dump("SELECT * FROM sites ORDER BY kind, name", "sites")
    dump("SELECT s.*, e.name AS entity_name FROM selectors s JOIN entities e ON e.id=s.entity_id ORDER BY e.name, s.kind", "selectors")
    dump("SELECT * FROM selector_links", "selector_links")
    dump("SELECT h.*, e.name AS entity_name FROM location_hits h JOIN entities e ON e.id=h.entity_id ORDER BY e.name, h.ts", "location_hits")
    def geojson(q, name, props):
        feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [r[1], r[0]]}, "properties": dict(zip(props, r[2:]))} for r in con.execute(q) if r[0] is not None]
        json.dump({"type": "FeatureCollection", "features": feats}, open(f"{ROOT}/db/exports/{name}.geojson", "w"), ensure_ascii=False)
    geojson("SELECT lat,lon,id,name,kind,operator,status,place,precision_km,verified,note,dataset FROM sites", "sites", ["id","name","kind","operator","status","place","precision_km","verified","note","dataset"])
    geojson("SELECT h.lat,h.lon,h.id,h.entity_id,e.name,h.kind,h.ts,h.precision_km,h.place,h.detail,h.confidence,h.selector_id,h.dataset FROM location_hits h JOIN entities e ON e.id=h.entity_id", "location_hits",
            ["id","entity_id","name","kind","ts","precision_km","place","detail","confidence","selector_id","dataset"])
    geojson("""SELECT g.lat,g.lon,ev.id,ev.date,ev.type,ev.description,ev.place_text,g.precision_km,ev.dataset,ev.source,
                (SELECT group_concat(en.name,'; ') FROM event_actors ea JOIN entities en ON en.id=ea.entity_id WHERE ea.event_id=ev.id),
                (SELECT group_concat(en.name,'; ') FROM event_actors ea JOIN entities en ON en.id=ea.entity_id WHERE ea.event_id=ev.id AND en.kind='organization')
                FROM events ev JOIN event_geo g ON g.event_id=ev.id""", "event_points", ["id","date","type","description","place","precision_km","dataset","source","actors","groups"])
    cards = []
    for r in con.execute("""SELECT c.entity_id,e.name,c.objective_name,c.kunyas,c.name_variants,c.tribe,c.sub_tribe,c.network,c.role_current,c.role_history,c.priority,c.status,c.dob,c.pob,c.home_area,c.summary,c.dataset,
                               h.kind,h.ts,h.lat,h.lon,h.precision_km,h.place,h.detail FROM target_cards c JOIN entities e ON e.id=c.entity_id LEFT JOIN location_hits h ON h.id=c.last_hit_id"""):
        eid_ = r[0]
        cards.append(dict(entity_id=eid_, name=r[1], objective_name=r[2], kunyas=json.loads(r[3] or "[]"), name_variants=json.loads(r[4] or "[]"), tribe=r[5], sub_tribe=r[6], network=r[7], role_current=r[8],
                          role_history=json.loads(r[9] or "[]"), priority=r[10], status=r[11], dob=r[12], pob=r[13], home_area=r[14], summary=r[15], dataset=r[16],
                          last_known_location=dict(kind=r[17], ts=r[18], lat=r[19], lon=r[20], precision_km=r[21], place=r[22], detail=r[23]) if r[18] else None,
                          aliases=[a for (a,) in con.execute("SELECT alias FROM aliases WHERE entity_id=?", (eid_,))],
                          family=[dict(type=t, name=n) for (t, n) in con.execute("SELECT r.type, x.name FROM relationships r JOIN entities x ON x.id=CASE WHEN r.source_id=? THEN r.target_id ELSE r.source_id END WHERE (r.source_id=? OR r.target_id=?) AND r.type LIKE '%_of'", (eid_, eid_, eid_))],
                          selectors=[dict(id=a, kind=b, value=c, label=d, provider=p, platform=pl, country=cc, first_seen=fs, last_seen=ls, confidence=cf) for (a, b, c, d, p, pl, cc, fs, ls, cf) in
                                     con.execute("SELECT id,kind,value,label,provider,platform,country,first_seen,last_seen,confidence FROM selectors WHERE entity_id=?", (eid_,))],
                          correlations=[dict(a=a, b=b, relation=rel, evidence=ev, confidence=cf) for (a, b, rel, ev, cf) in
                                        con.execute("SELECT l.a_id,l.b_id,l.relation,l.evidence,l.confidence FROM selector_links l WHERE l.a_id IN (SELECT id FROM selectors WHERE entity_id=?) OR l.b_id IN (SELECT id FROM selectors WHERE entity_id=?)", (eid_, eid_))],
                          location_hits=[dict(kind=k, ts=t, lat=la, lon=lo, precision_km=pr, place=pl, detail=de, confidence=cf, selector_id=sl) for (k, t, la, lo, pr, pl, de, cf, sl) in
                                         con.execute("SELECT kind,ts,lat,lon,precision_km,place,detail,confidence,selector_id FROM location_hits WHERE entity_id=? ORDER BY ts DESC", (eid_,))]))
    json.dump(cards, open(f"{ROOT}/db/exports/target_cards.json", "w"), indent=1, ensure_ascii=False)
    dump("SELECT p.*, e.name AS entity_name FROM profiles p LEFT JOIN entities e ON e.id=p.entity_id ORDER BY p.source, p.reference", "profiles")
    dump("""SELECT r.id, s.name AS source, s.kind AS source_kind, r.type, t.name AS target, t.kind AS target_kind, r.detail, r.date, r.confidence,
            r.episode_idx, r.doc_id, COALESCE(e.title, d.title) AS source_title, COALESCE(e.published, d.published) AS published, r.timestamp, r.quote, r.dataset, r.source
            FROM relationships r JOIN entities s ON s.id=r.source_id JOIN entities t ON t.id=r.target_id
            LEFT JOIN episodes e ON e.idx=r.episode_idx LEFT JOIN documents d ON d.doc_id=r.doc_id ORDER BY r.episode_idx, r.doc_id, r.id""", "relationships")
    dump("""SELECT ev.id, ev.date, ev.date_precision, ev.type, ev.description, ev.place_text, group_concat(en.name, '; ') AS actors, ev.episode_idx, ev.doc_id, ev.timestamp, ev.dataset
            FROM events ev LEFT JOIN event_actors ea ON ea.event_id=ev.id LEFT JOIN entities en ON en.id=ea.entity_id GROUP BY ev.id ORDER BY ev.date""", "events")
    dump("SELECT a.entity_id, e.name, a.alias FROM aliases a JOIN entities e ON e.id=a.entity_id ORDER BY e.name", "aliases")
    dump("SELECT m.entity_id, e.name, m.episode_idx, m.doc_id, m.timestamp, m.quote FROM mentions m JOIN entities e ON e.id=m.entity_id ORDER BY e.name, m.episode_idx, m.doc_id", "mentions")
    dump("SELECT * FROM documents ORDER BY published", "documents")
    # graph json for a GUI
    prof = {}
    for r in con.execute("SELECT entity_id, source, reference FROM profiles WHERE entity_id IS NOT NULL"): prof.setdefault(r[0], []).append(f"{r[1]}:{r[2]}")
    nodes = [dict(id=r[0], kind=r[1], name=r[2], dataset=r[3], role=r[4], status=r[6], n_episodes=r[7], country=r[8], n_documents=r[9], sources=r[10].split(","), profiles=prof.get(r[0], [])) for r in
             con.execute("SELECT id,kind,name,dataset,role,nationality,status,n_episodes,country,n_documents,sources FROM entities")]
    edges = []
    def docs_list(s): return [x for x in str(s or "").split(",") if x not in ("", "None")]
    for r in con.execute("""SELECT source_id,target_id,type,count(*),group_concat(DISTINCT episode_idx),min(confidence),max(detail),group_concat(DISTINCT doc_id),group_concat(DISTINCT source) FROM relationships GROUP BY source_id,target_id,type"""):
        edges.append(dict(source=r[0], target=r[1], type=r[2], n=r[3], episodes=[int(x) for x in str(r[4] or "").split(",") if x not in ("", "None")], documents=docs_list(r[7]), confidence=r[5], detail=r[6], sources=sorted(set(r[8].split(",")))))
    for r in con.execute("SELECT entity_id, org_id, count(DISTINCT episode_idx)+count(DISTINCT NULLIF(doc_id,'')), group_concat(DISTINCT episode_idx), group_concat(DISTINCT NULLIF(doc_id,'')) FROM memberships GROUP BY entity_id, org_id"):
        edges.append(dict(source=r[0], target=r[1], type="member_of", n=r[2], episodes=[int(x) for x in str(r[3] or "").split(",") if x not in ("", "None")], documents=docs_list(r[4]), confidence="stated", detail=None))
    json.dump({"nodes": nodes, "edges": edges}, open(f"{ROOT}/db/exports/graph.json", "w"), indent=0, ensure_ascii=False)
    if os.path.isdir(f"{ROOT}/isw/maps") and not a.no_isw: export_isw(con, f"{ROOT}/db/exports")
    n = {k: con.execute(f"SELECT count(*) FROM {k}").fetchone()[0] for k in ["episodes","documents","entities","aliases","relationships","events","mentions","memberships","profiles"]}
    if not a.no_isw: n.update({k: con.execute(f"SELECT count(*) FROM {k}").fetchone()[0] for k in ["map_sources","map_plots","place_coords"]})
    print(n); print({k: v for k, v in con.execute("SELECT kind, count(*) FROM entities GROUP BY kind")})

if __name__ == "__main__":
    main()
