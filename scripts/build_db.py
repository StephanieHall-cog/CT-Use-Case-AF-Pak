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
            for ac in ev.get("actors", []) or []:
                k, n = kind_of(ac, "persons"); ai = ent(k, n, dataset, ep)
                if ai: con.execute("INSERT OR IGNORE INTO event_actors VALUES(?,?)", (cur.lastrowid, ai))
        for c in d.get("key_claims", []) or []: con.execute("INSERT INTO claims(episode_idx,claim,doc_id) VALUES(?,?,?)", (idx, c, doc))
        for s in d.get("sources_cited", []) or []: con.execute("INSERT INTO sources_cited(episode_idx,source,doc_id) VALUES(?,?,?)", (idx, s, doc))

    load_profiles(con, ents, ent)

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
