#!/usr/bin/env python3
"""Merge per-article extraction JSON (lwj/extractions/*.json) into db/lwj_afpak.sqlite + db/lwj_exports/*.
Same entity-id scheme and alias resolver as scripts/build_db.py (podcast DB) so the two can be joined on entity id.
Usage: python3 lwj/scripts/build_lwj_db.py [--extractions DIR] [--out DBPATH]
"""
import json, glob, os, sqlite3, csv, argparse, re, hashlib, sys, collections
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, f"{ROOT}/scripts")
from normalize import Resolver, fold

DDL = """
CREATE TABLE articles(id TEXT PRIMARY KEY, url TEXT, title TEXT, published TEXT, author TEXT, tags TEXT, categories TEXT, model TEXT, relevant INTEGER, summary TEXT);
CREATE TABLE entities(id TEXT PRIMARY KEY, kind TEXT, name TEXT, dataset TEXT DEFAULT 'real',
  role TEXT, nationality TEXT, status TEXT, status_detail TEXT, org_type TEXT, country TEXT, place_type TEXT, parent_place TEXT,
  n_articles INTEGER DEFAULT 0, first_mentioned TEXT, last_mentioned TEXT, notes TEXT);
CREATE TABLE aliases(entity_id TEXT, alias TEXT, source TEXT, PRIMARY KEY(entity_id, alias));
CREATE TABLE memberships(entity_id TEXT, org_id TEXT, article_id TEXT, published TEXT, PRIMARY KEY(entity_id, org_id, article_id));
CREATE TABLE roles(entity_id TEXT, role TEXT, article_id TEXT, published TEXT, PRIMARY KEY(entity_id, role, article_id));
CREATE TABLE mentions(id INTEGER PRIMARY KEY AUTOINCREMENT, entity_id TEXT, article_id TEXT, published TEXT, quote TEXT, role_in_article TEXT, locations TEXT);
CREATE TABLE relationships(id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT, target_id TEXT, type TEXT, detail TEXT, kin TEXT, date TEXT, confidence TEXT,
  article_id TEXT, published TEXT, quote TEXT, dataset TEXT DEFAULT 'real');
CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, date_precision TEXT, type TEXT, description TEXT, place_id TEXT, place_text TEXT,
  casualties TEXT, article_id TEXT, published TEXT, dataset TEXT DEFAULT 'real');
CREATE TABLE event_actors(event_id INTEGER, entity_id TEXT, role TEXT, PRIMARY KEY(event_id, entity_id, role));
CREATE TABLE claims(id INTEGER PRIMARY KEY AUTOINCREMENT, article_id TEXT, claim TEXT);
CREATE TABLE sources_cited(id INTEGER PRIMARY KEY AUTOINCREMENT, article_id TEXT, source TEXT);
CREATE TABLE person_status_history(entity_id TEXT, status TEXT, detail TEXT, article_id TEXT, published TEXT);
CREATE INDEX i_rel_s ON relationships(source_id); CREATE INDEX i_rel_t ON relationships(target_id); CREATE INDEX i_rel_a ON relationships(article_id);
CREATE INDEX i_men_e ON mentions(entity_id); CREATE INDEX i_ev_d ON events(date); CREATE INDEX i_mem_e ON memberships(entity_id); CREATE INDEX i_roles_e ON roles(entity_id);
CREATE INDEX i_ent_name ON entities(name); CREATE INDEX i_ali ON aliases(alias);
"""
ORG_HINT=re.compile(r"\b(taliban|network|qaeda|qaida|aqis|ttp|tehrik|lashkar|jaish|army|police|forces?|brigade|battalion|regiment|corps|division|command|isaf|nato|centcom|cia|isi|fbi|ministry|government|council|shura|movement|front|group|faction|party|jamaat|jamiat|harakat|ansar|islamic|state|emirate|union|united|nations|un\b|committee|agency|directorate|intelligence|militia|tribe|mujahid[ie]n|brigades|media|foundation|trust|court|bureau|department|office|regiment|al-?shabaab|hezb|harkat|khorasan|iskp|isis|daesh|military|marines|navy|air force|seals|pentagon|white house|congress|senate|treasury|embassy)\b", re.I)
PLACE_HINT=re.compile(r"\b(province|district|valley|city|town|village|afghanistan|pakistan|waziristan|kabul|kandahar|peshawar|quetta|karachi|islamabad|miramshah|miran shah|helmand|kunar|khost|paktika|paktia|nangarhar|nuristan|ghazni|wardak|logar|zabul|uruzgan|kunduz|balkh|herat|farah|badakhshan|bajaur|mohmand|khyber|kurram|orakzai|swat|dir\b|chitral|lahore|balochistan|baluchistan|punjab|sindh|fata|iran|india|kashmir|yemen|iraq|syria|somalia|guantanamo|bagram|base|camp|agency|border)\b", re.I)

PLACEHOLDER=re.compile(r"\b(unnamed|unknown|unidentified|anonymous|unspecified|unconfirmed|several|various|multiple|civilians?|villagers?|residents?|sources?|witness(es)?|suicide bombers?|gunmen)\b|[()?/]|^\d|'s\b|\b(commanders|militants|fighters|soldiers|troops|bombers|operatives|leaders|officials|gunmen|hijacking|attack|bombing|flight|forces)$", re.I)
GENERIC=re.compile(r"^(a |an |the )?((senior|former|local|top|high-ranking|deputy|suspected|alleged|slain|wanted|unnamed|mid-level)\s+)*((pakistani|afghan|american|us|u\.s\.|nato|isaf|ana|anp|anf|isi|cia|afghan national|frontier corps|tajik|uzbek|arab|chechen|punjabi|iranian|british|taliban|haqqani|al[ -]?qaeda|ttp|isis|islamic state|iskp|lashkar|jaish|tribal|military|army|police|security|intelligence|government|coalition)\s+)*(commanders?|leaders?|spokes(man|men|person)|officials?|fighters?|operatives?|governors?|militants?|soldiers?|officers?|members?|bombers?|facilitators?|financiers?|elders?|sources?|ministers?|emirs?|amirs?|chiefs?|troops|forces|personnel)( (in|of|for|from) .*)?$", re.I)
def skel(name):
    """Transliteration skeleton: Hakeemullah/Hakimullah Mehsud/Mahsud, Mohammad/Muhammad, Rehman/Rahman collapse together."""
    out=[]
    for t in fold(name).split():
        t=t.replace("ph","f").replace("ck","k").replace("gh","g").replace("dh","d").replace("th","t")
        for a,b in (("ee","i"),("oo","u"),("ai","i"),("ei","i"),("ay","i"),("ou","u"),("aa","a")): t=t.replace(a,b)
        t=t.replace("e","a").replace("o","u").replace("y","i").replace("q","k").replace("w","v")
        t=re.sub(r"(.)\1+",r"\1",t); out.append(t)
    return " ".join(out)

def eid(kind, name, dataset="real"):
    p = {"persons":"P","organizations":"O","places":"L"}[kind]
    h = hashlib.sha1(f"{dataset}|{kind}|{fold(name)}".encode()).hexdigest()[:10]
    return f"{'S' if dataset=='synthetic' else ''}{p}-{h}"

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--extractions", default=f"{HERE}/../extractions"); ap.add_argument("--out", default=f"{ROOT}/db/lwj_afpak.sqlite")
    ap.add_argument("--exports", default=f"{ROOT}/db/lwj_exports"); ap.add_argument("--min-relevant", action="store_true", help="skip articles the extractor marked relevant=false")
    a=ap.parse_args()
    R=Resolver(); os.makedirs(a.exports, exist_ok=True)
    if os.path.exists(a.out): os.remove(a.out)
    con=sqlite3.connect(a.out); con.executescript(DDL)
    ents={}; known_kind={}   # fold(name) -> kind, learned from explicit entity lists per article
    def ent(kind, name, art, **fields):
        if not name or not isinstance(name,str): return None
        canon=R.resolve(kind, name)
        if not canon or len(canon)<2: return None
        i=eid(kind, canon)
        row=ents.setdefault(i, {"id":i,"kind":kind[:-1],"name":canon,"dataset":"real","aliases":set(),"arts":set(),"pubs":[]})
        row["arts"].add(art["id"]); row["pubs"].append(art.get("published") or "")
        if fold(name)!=fold(canon) or name.strip()!=canon: row["aliases"].add(name.strip())
        for k,v in fields.items():
            if v and (not row.get(k) or (k in ("role","status","status_detail") and (art.get("published") or "")>=row.get("_pub_"+k,""))):
                row[k]=v; row["_pub_"+k]=art.get("published") or ""
        return i
    def kind_of(name, default, art_kinds):
        f=fold(name)
        if f in art_kinds: return art_kinds[f], name
        if f in known_kind: return known_kind[f], name
        k,r=R.resolve_any(name)
        if k: return k, r
        if PLACE_HINT.search(name) and not ORG_HINT.search(name): return "places", name
        if ORG_HINT.search(name): return "organizations", name
        return default, name
    files=sorted(glob.glob(f"{a.extractions}/*.json")); n_art=0
    for fp in files:
        try: d=json.load(open(fp))
        except Exception as e: print("bad json", fp, e); continue
        art=d.get("article") or {}; aid=art.get("id") or os.path.basename(fp)[:-5]; art["id"]=aid
        if a.min_relevant and d.get("relevant") is False: continue
        pub=art.get("published") or ""
        con.execute("INSERT OR REPLACE INTO articles VALUES(?,?,?,?,?,?,?,?,?,?)",(aid,art.get("url"),art.get("title"),pub,art.get("author"),
                    json.dumps(art.get("tags") or []),json.dumps(art.get("categories") or []),d.get("model"),1 if d.get("relevant") else 0,d.get("summary")))
        n_art+=1
        art_kinds={}
        for k in ("persons","organizations","places"):
            for it in d.get(k,[]) or []:
                if isinstance(it,dict) and it.get("name"): art_kinds[fold(it["name"])]=k; known_kind.setdefault(fold(it["name"]),k)
                for al in (it.get("aliases") or []) if isinstance(it,dict) else []:
                    if isinstance(al,str): art_kinds.setdefault(fold(al),k)
        for p in d.get("persons",[]) or []:
            if not isinstance(p,dict): continue
            i=ent("persons", p.get("name"), art, role=p.get("role"), nationality=p.get("nationality_or_origin"), status=p.get("status"), status_detail=p.get("status_detail"))
            if not i: continue
            for al in p.get("aliases",[]) or []:
                if isinstance(al,str) and al.strip(): ents[i]["aliases"].add(al.strip())
            if p.get("role"): con.execute("INSERT OR IGNORE INTO roles VALUES(?,?,?,?)",(i,p["role"],aid,pub))
            for o in p.get("organizations",[]) or []:
                oi=ent("organizations", o, art)
                if oi: con.execute("INSERT OR IGNORE INTO memberships VALUES(?,?,?,?)",(i,oi,aid,pub))
            for f in p.get("family",[]) or []:
                if not isinstance(f,dict) or not f.get("name"): continue
                fi=ent("persons", f["name"], art)
                if fi and fi!=i: con.execute("INSERT INTO relationships(source_id,target_id,type,detail,confidence,article_id,published,quote) VALUES(?,?,?,?,?,?,?,?)",
                                             (fi,i,"family",f.get("relation"),"stated",aid,pub,p.get("quote")))
            locs=[l for l in (p.get("locations") or []) if isinstance(l,str)]
            for l in locs: ent("places", l, art)
            con.execute("INSERT INTO mentions(entity_id,article_id,published,quote,role_in_article,locations) VALUES(?,?,?,?,?,?)",(i,aid,pub,p.get("quote"),p.get("role"),", ".join(locs)))
            if p.get("status"): con.execute("INSERT INTO person_status_history VALUES(?,?,?,?,?)",(i,p["status"],p.get("status_detail"),aid,pub))
        for o in d.get("organizations",[]) or []:
            if not isinstance(o,dict): continue
            i=ent("organizations", o.get("name"), art, org_type=o.get("type"), country=o.get("country_base"), notes=o.get("notes"))
            if not i: continue
            for al in o.get("aliases",[]) or []:
                if isinstance(al,str) and al.strip(): ents[i]["aliases"].add(al.strip())
            for pa in o.get("parent_or_allies",[]) or []:
                pi=ent("organizations", pa, art)
                if pi and pi!=i: con.execute("INSERT INTO relationships(source_id,target_id,type,confidence,article_id,published) VALUES(?,?,?,?,?,?)",(i,pi,"allied_with","stated",aid,pub))
            for rv in o.get("rivals",[]) or []:
                ri=ent("organizations", rv, art)
                if ri and ri!=i: con.execute("INSERT INTO relationships(source_id,target_id,type,confidence,article_id,published) VALUES(?,?,?,?,?,?)",(i,ri,"rival_of","stated",aid,pub))
        for pl in d.get("places",[]) or []:
            if isinstance(pl,dict): ent("places", pl.get("name"), art, place_type=pl.get("type"), country=pl.get("country"), parent_place=pl.get("parent"), notes=pl.get("significance"))
        for r in d.get("relationships",[]) or []:
            if not isinstance(r,dict): continue
            s,t=r.get("source",""),r.get("target","")
            if not isinstance(s,str) or not isinstance(t,str) or not s or not t: continue
            ks,s=kind_of(s,"persons",art_kinds)
            kt,t=kind_of(t,"places" if r.get("type") in ("located_in","based_in","operates_in") else "persons",art_kinds)
            si=ent(ks,s,art); ti=ent(kt,t,art)
            if not si or not ti or si==ti: continue
            con.execute("INSERT INTO relationships(source_id,target_id,type,detail,date,confidence,article_id,published,quote) VALUES(?,?,?,?,?,?,?,?,?)",
                        (si,ti,r.get("type"),r.get("detail"),r.get("date"),r.get("confidence"),aid,pub,r.get("quote")))
        for ev in d.get("events",[]) or []:
            if not isinstance(ev,dict): continue
            pi=ent("places", ev.get("place"), art) if isinstance(ev.get("place"),str) and ev.get("place") else None
            cur=con.execute("INSERT INTO events(date,date_precision,type,description,place_id,place_text,casualties,article_id,published) VALUES(?,?,?,?,?,?,?,?,?)",
                            (ev.get("date"),ev.get("date_precision"),ev.get("type"),ev.get("description"),pi,ev.get("place"),ev.get("casualties"),aid,pub))
            for role,key in (("actor","actors"),("target","targets")):
                for ac in ev.get(key,[]) or []:
                    if not isinstance(ac,str) or not ac: continue
                    k,n=kind_of(ac,"persons" if role=="actor" else "places",art_kinds); ai=ent(k,n,art)
                    if ai: con.execute("INSERT OR IGNORE INTO event_actors VALUES(?,?,?)",(cur.lastrowid,ai,role))
        for c in d.get("key_claims",[]) or []:
            if isinstance(c,str): con.execute("INSERT INTO claims(article_id,claim) VALUES(?,?)",(aid,c))
        for s in d.get("sources_cited",[]) or []:
            if isinstance(s,str): con.execute("INSERT INTO sources_cited(article_id,source) VALUES(?,?)",(aid,s))
    # ---- post-pass: drop placeholder persons, merge dual-kind names, alias-based and transliteration merges ----
    idmap={}
    def merge_into(src,dst):
        if src==dst or src in idmap or dst in idmap: return
        a,b=ents[src],ents[dst]; b["aliases"]|=a["aliases"]|{a["name"]}; b["arts"]|=a["arts"]; b["pubs"]+=a["pubs"]
        for k,v in a.items():
            if k not in b or not b.get(k): b[k]=v
        idmap[src]=dst
    for i,r in list(ents.items()):
        if r["kind"]=="person" and (PLACEHOLDER.search(r["name"]) or GENERIC.match(r["name"]) or not re.search(r"[A-Z]",r["name"])): idmap[i]=None
    byfold=collections.defaultdict(list)
    for i,r in ents.items():
        if i not in idmap: byfold[fold(r["name"])].append(i)
    for f,ids in byfold.items():
        if len(ids)>1:
            ids.sort(key=lambda x:-len(ents[x]["arts"])); 
            for o in ids[1:]:
                same_text=ents[o]["name"].lower()==ents[ids[0]]["name"].lower()
                if "person" in (ents[o]["kind"],ents[ids[0]]["kind"]) and not same_text: continue
                if len(ents[ids[0]]["arts"])>=3*max(1,len(ents[o]["arts"])): merge_into(o,ids[0])
    alias_idx={}
    for i,r in ents.items():
        if i in idmap: continue
        for al in r["aliases"]:
            alias_idx.setdefault((r["kind"],fold(al)),[]).append(i)
    for i,r in list(ents.items()):
        if i in idmap: continue
        cands=[c for c in alias_idx.get((r["kind"],fold(r["name"])),[]) if c!=i and c not in idmap]
        if len(cands)==1:
            dst=cands[0]; src=i
            if len(ents[src]["arts"])>len(ents[dst]["arts"]): src,dst=dst,src
            merge_into(src,dst)
    bysk=collections.defaultdict(list)
    for i,r in ents.items():
        if i not in idmap and r["kind"]=="person" and len(fold(r["name"]).split())>=2: bysk[skel(r["name"])].append(i)
    for k,ids in bysk.items():
        if len(ids)>1:
            ids.sort(key=lambda x:-len(ents[x]["arts"]))
            for o in ids[1:]: merge_into(o,ids[0])
    def final(i):
        seen=set()
        while i in idmap and i not in seen: seen.add(i); i=idmap[i]
        return i
    idmap={k:final(k) for k in list(idmap)}
    print("post-pass: dropped",sum(1 for v in idmap.values() if v is None),"merged",sum(1 for v in idmap.values() if v))
    for old,newid in idmap.items():
        for tbl,cols in (("memberships",("entity_id","org_id")),("roles",("entity_id",)),("mentions",("entity_id",)),("relationships",("source_id","target_id")),
                         ("event_actors",("entity_id",)),("person_status_history",("entity_id",)),("events",("place_id",))):
            for c in cols:
                if newid is None: con.execute(f"DELETE FROM {tbl} WHERE {c}=?",(old,)) if tbl!="events" else con.execute(f"UPDATE events SET place_id=NULL WHERE place_id=?",(old,))
                else: con.execute(f"UPDATE OR IGNORE {tbl} SET {c}=? WHERE {c}=?",(newid,old)); con.execute(f"DELETE FROM {tbl} WHERE {c}=?",(old,)) if tbl!="events" else None
        del ents[old]
    con.execute("DELETE FROM relationships WHERE source_id=target_id")
    # normalise model output that escaped the schema
    con.execute("UPDATE relationships SET type='other' WHERE type IS NULL OR trim(type)=''")
    con.execute("UPDATE relationships SET confidence='inferred' WHERE confidence IS NULL OR confidence NOT IN ('stated','inferred')")
    con.execute("UPDATE events SET date=NULL WHERE date IS NOT NULL AND date NOT GLOB '[0-9]*'")
    con.execute("UPDATE events SET date_precision='unknown' WHERE date IS NULL OR date=''")
    con.execute("UPDATE events SET date_precision='approx' WHERE date_precision LIKE '%approx%' AND date_precision!='approx'")
    con.execute("UPDATE events SET date_precision='approx' WHERE date_precision IS NULL OR date_precision NOT IN ('day','month','year','approx','unknown')")
    for i,r in ents.items():
        r["aliases"]={al for al in r["aliases"] if al.lower()!=r["name"].lower()}
        pubs=sorted(p for p in r["pubs"] if p)
        con.execute("INSERT INTO entities(id,kind,name,dataset,role,nationality,status,status_detail,org_type,country,place_type,parent_place,n_articles,first_mentioned,last_mentioned,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (i,r["kind"],r["name"],r["dataset"],r.get("role"),r.get("nationality"),r.get("status"),r.get("status_detail"),r.get("org_type"),r.get("country"),
                     r.get("place_type"),r.get("parent_place"),len(r["arts"]),pubs[0] if pubs else None,pubs[-1] if pubs else None,r.get("notes")))
        for al in r["aliases"]: con.execute("INSERT OR IGNORE INTO aliases VALUES(?,?,?)",(i,al,"extraction"))
    # family edges: normalise free-text detail to a kin term, then fix direction for asymmetric kin by
    # majority vote per pair (the model sometimes writes "Jalaluddin -son-> Sirajuddin"; direction rule is
    # detail = source's relation to target, so minority-orientation rows are flipped and marked inferred).
    SENIOR={"father","mother","parent","uncle","aunt","grandfather","grandmother","father-in-law","mother-in-law"}
    JUNIOR={"son","daughter","child","nephew","niece","grandson","granddaughter","son-in-law","daughter-in-law"}
    KIN=re.compile(r"\b(father-in-law|mother-in-law|son-in-law|daughter-in-law|brother-in-law|sister-in-law|grandfather|grandmother|grandson|granddaughter|half-brother|step-?son|father|mother|son|daughter|brother|sister|cousin|uncle|aunt|nephew|niece|wife|husband|widow|spouse|relative|tribe|clan)s?\b",re.I)
    def kin_of(detail):
        m=KIN.search(detail or ""); 
        if not m: return "relative"
        k=m.group(1).lower().replace("stepson","son").replace("step-son","son").replace("half-brother","brother").replace("widow","wife")
        return k
    rows=con.execute("SELECT id,source_id,target_id,detail FROM relationships WHERE type='family'").fetchall()
    for rid,src,tgt,detail in rows: con.execute("UPDATE relationships SET kin=? WHERE id=?",(kin_of(detail),rid))
    votes=collections.defaultdict(lambda: collections.Counter())
    for rid,src,tgt,kin in con.execute("SELECT id,source_id,target_id,kin FROM relationships WHERE type='family'"):
        if kin in SENIOR: votes[frozenset((src,tgt))][src]+=1
        elif kin in JUNIOR: votes[frozenset((src,tgt))][tgt]+=1
    flipped=0
    for rid,src,tgt,kin in con.execute("SELECT id,source_id,target_id,kin FROM relationships WHERE type='family'").fetchall():
        v=votes.get(frozenset((src,tgt)))
        if not v or len(v)<2 and (kin not in SENIOR|JUNIOR): continue
        senior=v.most_common(1)[0][0]
        if v[senior]==v[src if senior==tgt else tgt]: continue
        implied=src if kin in SENIOR else tgt if kin in JUNIOR else None
        if implied and implied!=senior:
            con.execute("UPDATE relationships SET source_id=?,target_id=?,confidence='inferred' WHERE id=?",(tgt,src,rid)); flipped+=1
    print("family edges re-oriented by majority vote:",flipped)
    con.commit()
    def dump(q,name):
        cur=con.execute(q); cols=[c[0] for c in cur.description]; rows=cur.fetchall()
        with open(f"{a.exports}/{name}.csv","w",newline="") as fh:
            w=csv.writer(fh); w.writerow(cols); w.writerows(rows)
    dump("SELECT * FROM articles ORDER BY published","articles")
    dump("SELECT * FROM entities ORDER BY kind, n_articles DESC, name","entities")
    dump("""SELECT r.id, s.name AS source, s.kind AS source_kind, r.type, t.name AS target, t.kind AS target_kind, r.detail, r.kin, r.date, r.confidence,
            r.article_id, ar.title AS article, ar.url, r.published, r.quote FROM relationships r JOIN entities s ON s.id=r.source_id JOIN entities t ON t.id=r.target_id
            LEFT JOIN articles ar ON ar.id=r.article_id ORDER BY r.published, r.id""","relationships")
    dump("""SELECT ev.id, ev.date, ev.date_precision, ev.type, ev.description, ev.place_text, ev.casualties,
            group_concat(CASE WHEN ea.role='actor' THEN en.name END, '; ') AS actors, group_concat(CASE WHEN ea.role='target' THEN en.name END, '; ') AS targets,
            ev.article_id, ar.url, ev.published FROM events ev LEFT JOIN event_actors ea ON ea.event_id=ev.id LEFT JOIN entities en ON en.id=ea.entity_id
            LEFT JOIN articles ar ON ar.id=ev.article_id GROUP BY ev.id ORDER BY ev.date""","events")
    dump("SELECT a.entity_id, e.name, e.kind, a.alias FROM aliases a JOIN entities e ON e.id=a.entity_id ORDER BY e.name","aliases")
    dump("SELECT m.entity_id, e.name, m.article_id, m.published, m.role_in_article, m.locations, m.quote FROM mentions m JOIN entities e ON e.id=m.entity_id ORDER BY e.name, m.published","mentions")
    dump("SELECT r.entity_id, e.name, r.role, r.published, r.article_id FROM roles r JOIN entities e ON e.id=r.entity_id ORDER BY e.name, r.published","roles")
    dump("SELECT m.entity_id, e.name, o.name AS organization, count(*) AS n_articles, min(m.published) AS first, max(m.published) AS last FROM memberships m JOIN entities e ON e.id=m.entity_id JOIN entities o ON o.id=m.org_id GROUP BY m.entity_id, m.org_id ORDER BY e.name","memberships")
    nodes=[dict(id=r[0],kind=r[1],name=r[2],role=r[3],status=r[4],n=r[5],country=r[6],first=r[7],last=r[8]) for r in
           con.execute("SELECT id,kind,name,role,status,n_articles,country,first_mentioned,last_mentioned FROM entities WHERE n_articles>=2 OR kind='person'")]
    keep={n["id"] for n in nodes}; edges=[]
    for r in con.execute("SELECT source_id,target_id,type,count(*),group_concat(DISTINCT article_id),min(published),max(published),min(confidence),max(detail) FROM relationships GROUP BY source_id,target_id,type"):
        if r[0] in keep and r[1] in keep: edges.append(dict(source=r[0],target=r[1],type=r[2],n=r[3],articles=str(r[4]).split(",")[:50],first=r[5],last=r[6],confidence=r[7],detail=r[8]))
    for r in con.execute("SELECT entity_id,org_id,count(*),group_concat(DISTINCT article_id),min(published),max(published) FROM memberships GROUP BY entity_id,org_id"):
        if r[0] in keep and r[1] in keep: edges.append(dict(source=r[0],target=r[1],type="member_of",n=r[2],articles=str(r[3]).split(",")[:50],first=r[4],last=r[5],confidence="stated",detail=None))
    json.dump({"nodes":nodes,"edges":edges},open(f"{a.exports}/graph.json","w"),ensure_ascii=False)
    n={k:con.execute(f"SELECT count(*) FROM {k}").fetchone()[0] for k in ["articles","entities","aliases","relationships","events","mentions","memberships","roles","claims"]}
    print(n); print(dict(con.execute("SELECT kind, count(*) FROM entities GROUP BY kind").fetchall()))
    print("graph nodes",len(nodes),"edges",len(edges))
if __name__=="__main__": main()
