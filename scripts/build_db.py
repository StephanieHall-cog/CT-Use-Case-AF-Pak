#!/usr/bin/env python3
"""Merge per-episode extraction JSON (raw/extractions/*.json) into db/afpak.sqlite + db/exports/*.
Usage: python3 scripts/build_db.py [--synthetic synthetic/*.json]
Every row carries provenance (episode idx, timestamp, quote) and a `dataset` column: 'real' or 'synthetic'.
"""
import json, glob, os, sqlite3, csv, argparse, re, hashlib
from normalize import Resolver, fold

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESENTERS = {fold(x) for x in ["Bill Roggio","Thomas Joscelyn","Tom Joscelyn","Caleb Weiss","Joe Truzman","David Daoud","Behnam Ben Taleblu","Ahmad Sharawi","Preston Stewart"]}

DDL = """
CREATE TABLE episodes(idx INTEGER PRIMARY KEY, guid TEXT, title TEXT, published TEXT, duration_s INTEGER, audio_url TEXT, description TEXT, transcript_path TEXT);
CREATE TABLE entities(id TEXT PRIMARY KEY, kind TEXT, name TEXT, dataset TEXT DEFAULT 'real',
  role TEXT, nationality TEXT, status TEXT, status_detail TEXT, org_type TEXT, country TEXT, place_type TEXT, parent_place TEXT,
  n_episodes INTEGER DEFAULT 0, first_mentioned TEXT, last_mentioned TEXT, is_presenter_or_guest INTEGER DEFAULT 0, notes TEXT);
CREATE TABLE aliases(entity_id TEXT, alias TEXT, source TEXT, PRIMARY KEY(entity_id, alias));
CREATE TABLE memberships(entity_id TEXT, org_id TEXT, episode_idx INTEGER, PRIMARY KEY(entity_id, org_id, episode_idx));
CREATE TABLE mentions(id INTEGER PRIMARY KEY AUTOINCREMENT, entity_id TEXT, episode_idx INTEGER, timestamp TEXT, quote TEXT, role_in_episode TEXT, locations TEXT);
CREATE TABLE relationships(id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT, target_id TEXT, type TEXT, detail TEXT, date TEXT, confidence TEXT,
  episode_idx INTEGER, timestamp TEXT, quote TEXT, dataset TEXT DEFAULT 'real');
CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, date_precision TEXT, type TEXT, description TEXT, place_id TEXT, place_text TEXT,
  episode_idx INTEGER, timestamp TEXT, dataset TEXT DEFAULT 'real');
CREATE TABLE event_actors(event_id INTEGER, entity_id TEXT, PRIMARY KEY(event_id, entity_id));
CREATE TABLE claims(id INTEGER PRIMARY KEY AUTOINCREMENT, episode_idx INTEGER, claim TEXT);
CREATE TABLE sources_cited(id INTEGER PRIMARY KEY AUTOINCREMENT, episode_idx INTEGER, source TEXT);
CREATE TABLE person_status_history(entity_id TEXT, status TEXT, detail TEXT, episode_idx INTEGER, published TEXT);
CREATE INDEX i_rel_s ON relationships(source_id); CREATE INDEX i_rel_t ON relationships(target_id);
CREATE INDEX i_men_e ON mentions(entity_id); CREATE INDEX i_ev_d ON events(date);
"""

def eid(kind, name, dataset="real"):
    p = {"persons":"P","organizations":"O","places":"L"}[kind]
    h = hashlib.sha1(f"{dataset}|{kind}|{fold(name)}".encode()).hexdigest()[:10]
    return f"{'S' if dataset=='synthetic' else ''}{p}-{h}"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--synthetic", nargs="*", default=[]); a = ap.parse_args()
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
        row = ents.setdefault(i, {"id": i, "kind": kind[:-1], "name": canon, "dataset": dataset, "aliases": set(), "eps": set(), "pubs": []})
        if fold(name) != fold(canon): row["aliases"].add(name.strip())
        if ep is not None:
            row["eps"].add(ep["idx"]); row["pubs"].append(ep.get("published",""))
        for k, v in fields.items():
            if v and not row.get(k): row[k] = v
        return i

    files = [(f, "real") for f in sorted(glob.glob(f"{ROOT}/raw/extractions/*.json"))] + [(f, "synthetic") for f in a.synthetic]
    GLOBAL_KIND = {}
    for _f, _ds in files:
        _d = json.load(open(_f))
        for _kind in ("persons", "organizations", "places"):
            for _it in _d.get(_kind, []) or []:
                for _nm in [_it.get("name")] + (_it.get("aliases", []) or []):
                    if _nm: GLOBAL_KIND.setdefault(fold(_nm), _kind)
    for f, dataset in files:
        d = json.load(open(f)); ep = d.get("episode", {}); idx = ep.get("idx")
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
        for p in d.get("persons", []) or []:
            i = ent("persons", p.get("name"), dataset, ep, role=p.get("role"), nationality=p.get("nationality_or_origin"), status=p.get("status"),
                    status_detail=p.get("status_detail"), is_presenter_or_guest=1 if p.get("is_presenter_or_guest") else 0)
            if not i: continue
            for al in p.get("aliases", []) or []: ents[i]["aliases"].add(al)
            for o in p.get("organizations", []) or []:
                oi = ent("organizations", o, dataset, ep)
                if oi: con.execute("INSERT OR IGNORE INTO memberships VALUES(?,?,?)", (i, oi, idx))
            for fam in p.get("family", []) or []:
                fi = ent("persons", fam.get("name"), dataset, ep)
                if fi: con.execute("INSERT INTO relationships(source_id,target_id,type,detail,confidence,episode_idx,dataset) VALUES(?,?,?,?,?,?,?)",
                                   (i, fi, "family", f"{fam.get('relation')} ({ents[i]['name']} is {fam.get('relation')} of {ents[fi]['name']})"
                                    if fam.get("relation") else "family", "stated", idx, dataset))
            locs = ", ".join(p.get("locations", []) or [])
            for l in p.get("locations", []) or []: ent("places", l, dataset, ep)
            ms = p.get("mentions", []) or [{}]
            for mnt in ms:
                con.execute("INSERT INTO mentions(entity_id,episode_idx,timestamp,quote,role_in_episode,locations) VALUES(?,?,?,?,?,?)",
                            (i, idx, mnt.get("timestamp"), mnt.get("quote"), p.get("role"), locs))
            if p.get("status"):
                con.execute("INSERT INTO person_status_history VALUES(?,?,?,?,?)", (i, p.get("status"), p.get("status_detail"), idx, ep.get("published")))
        for o in d.get("organizations", []) or []:
            i = ent("organizations", o.get("name"), dataset, ep, org_type=o.get("type"), country=o.get("country_base"), notes=o.get("notes"))
            if not i: continue
            for al in o.get("aliases", []) or []: ents[i]["aliases"].add(al)
            for pa in o.get("parent_or_allies", []) or []:
                pi = ent("organizations", pa, dataset, ep)
                if pi and pi != i: con.execute("INSERT INTO relationships(source_id,target_id,type,confidence,episode_idx,dataset) VALUES(?,?,?,?,?,?)", (i, pi, "allied_with", "stated", idx, dataset))
            for rv in o.get("rivals", []) or []:
                ri = ent("organizations", rv, dataset, ep)
                if ri and ri != i: con.execute("INSERT INTO relationships(source_id,target_id,type,confidence,episode_idx,dataset) VALUES(?,?,?,?,?,?)", (i, ri, "rival_of", "stated", idx, dataset))
        for pl in d.get("places", []) or []:
            ent("places", pl.get("name"), dataset, ep, place_type=pl.get("type"), country=pl.get("country"), parent_place=pl.get("parent"), notes=pl.get("significance"))
        for r in d.get("relationships", []) or []:
            ks, s = kind_of(r.get("source", ""), "persons"); kt, t = kind_of(r.get("target", ""), "places" if r.get("type") == "located_in" else "persons")
            si = ent(ks, s, dataset, ep) if s else None
            ti = ent(kt, t, dataset, ep) if t else None
            if not si or not ti: continue
            con.execute("INSERT INTO relationships(source_id,target_id,type,detail,date,confidence,episode_idx,timestamp,quote,dataset) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (si, ti, r.get("type"), r.get("detail"), r.get("date"), r.get("confidence"), idx, r.get("timestamp"), r.get("quote"), dataset))
        for ev in d.get("events", []) or []:
            pi = ent("places", ev["place"], dataset, ep) if ev.get("place") else None
            cur = con.execute("INSERT INTO events(date,date_precision,type,description,place_id,place_text,episode_idx,timestamp,dataset) VALUES(?,?,?,?,?,?,?,?,?)",
                              (ev.get("date"), ev.get("date_precision"), ev.get("type"), ev.get("description"), pi, ev.get("place"), idx, ev.get("timestamp"), dataset))
            for ac in ev.get("actors", []) or []:
                k, n = kind_of(ac, "persons"); ai = ent(k, n, dataset, ep)
                if ai: con.execute("INSERT OR IGNORE INTO event_actors VALUES(?,?)", (cur.lastrowid, ai))
        for c in d.get("key_claims", []) or []: con.execute("INSERT INTO claims(episode_idx,claim) VALUES(?,?)", (idx, c))
        for s in d.get("sources_cited", []) or []: con.execute("INSERT INTO sources_cited(episode_idx,source) VALUES(?,?)", (idx, s))

    # entity-level resolution of unresolved person names that are a substring/last-name match of a canonical (conservative): skipped on purpose; see review_names.py
    for i, r in ents.items():
        pubs = sorted(p for p in r["pubs"] if p)
        con.execute("INSERT INTO entities(id,kind,name,dataset,role,nationality,status,status_detail,org_type,country,place_type,parent_place,n_episodes,first_mentioned,last_mentioned,is_presenter_or_guest,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (i, r["kind"], r["name"], r["dataset"], r.get("role"), r.get("nationality"), r.get("status"), r.get("status_detail"), r.get("org_type"), r.get("country"),
                     r.get("place_type"), r.get("parent_place"), len(r["eps"]), pubs[0] if pubs else None, pubs[-1] if pubs else None, r.get("is_presenter_or_guest", 0), r.get("notes")))
        for al in r["aliases"]:
            con.execute("INSERT OR IGNORE INTO aliases VALUES(?,?,?)", (i, al, "extraction"))
    con.commit()

    # exports
    def dump(q, name):
        cur = con.execute(q); cols = [c[0] for c in cur.description]; rows = cur.fetchall()
        with open(f"{ROOT}/db/exports/{name}.csv", "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(cols); w.writerows(rows)
        return cols, rows
    dump("SELECT * FROM entities ORDER BY kind, n_episodes DESC, name", "entities")
    dump("""SELECT r.id, s.name AS source, s.kind AS source_kind, r.type, t.name AS target, t.kind AS target_kind, r.detail, r.date, r.confidence,
            r.episode_idx, e.title AS episode, e.published, r.timestamp, r.quote, r.dataset FROM relationships r JOIN entities s ON s.id=r.source_id JOIN entities t ON t.id=r.target_id
            LEFT JOIN episodes e ON e.idx=r.episode_idx ORDER BY r.episode_idx, r.id""", "relationships")
    dump("""SELECT ev.id, ev.date, ev.date_precision, ev.type, ev.description, ev.place_text, group_concat(en.name, '; ') AS actors, ev.episode_idx, ev.timestamp, ev.dataset
            FROM events ev LEFT JOIN event_actors ea ON ea.event_id=ev.id LEFT JOIN entities en ON en.id=ea.entity_id GROUP BY ev.id ORDER BY ev.date""", "events")
    dump("SELECT a.entity_id, e.name, a.alias FROM aliases a JOIN entities e ON e.id=a.entity_id ORDER BY e.name", "aliases")
    dump("SELECT m.entity_id, e.name, m.episode_idx, m.timestamp, m.quote FROM mentions m JOIN entities e ON e.id=m.entity_id ORDER BY e.name, m.episode_idx", "mentions")
    # graph json for a GUI
    nodes = [dict(id=r[0], kind=r[1], name=r[2], dataset=r[3], role=r[4], status=r[6], n_episodes=r[7], country=r[8]) for r in
             con.execute("SELECT id,kind,name,dataset,role,nationality,status,n_episodes,country FROM entities")]
    edges = []
    for r in con.execute("""SELECT source_id,target_id,type,count(*),group_concat(DISTINCT episode_idx),min(confidence),max(detail) FROM relationships GROUP BY source_id,target_id,type"""):
        edges.append(dict(source=r[0], target=r[1], type=r[2], n=r[3], episodes=[int(x) for x in str(r[4] or "").split(",") if x not in ("", "None")], confidence=r[5], detail=r[6]))
    for r in con.execute("SELECT entity_id, org_id, count(DISTINCT episode_idx), group_concat(DISTINCT episode_idx) FROM memberships GROUP BY entity_id, org_id"):
        edges.append(dict(source=r[0], target=r[1], type="member_of", n=r[2], episodes=[int(x) for x in str(r[3] or "").split(",") if x not in ("", "None")], confidence="stated", detail=None))
    json.dump({"nodes": nodes, "edges": edges}, open(f"{ROOT}/db/exports/graph.json", "w"), indent=0, ensure_ascii=False)
    n = {k: con.execute(f"SELECT count(*) FROM {k}").fetchone()[0] for k in ["episodes","entities","aliases","relationships","events","mentions","memberships"]}
    print(n); print({k: v for k, v in con.execute("SELECT kind, count(*) FROM entities GROUP BY kind")})

if __name__ == "__main__":
    main()
