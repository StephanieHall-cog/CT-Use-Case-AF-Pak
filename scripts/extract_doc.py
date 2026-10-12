#!/usr/bin/env python3
"""Entity/relationship extraction from an open-source DOCUMENT (report/article) with Claude.
Usage: python3 extract_doc.py raw/documents/<doc_id>.txt [--out raw/documents/extractions] [--model claude-sonnet-5-5] [--workers 4]
The text file starts with a JSON header line (document metadata) followed by the body with `[PDF p.N]` page markers (or `[para N]` for web articles).
Output follows scripts/schema.json except that the top-level key is `document` (not `episode`) and every `timestamp`
field holds a page/paragraph reference like `p.12` or `para 7`. Needs ANTHROPIC_API_KEY in env.
"""
import json, os, sys, time, argparse, re, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import parse_json, merge

SYSTEM = """You are an intelligence analyst building a link-analysis database of jihadist networks in Afghanistan and Pakistan
(Haqqani Network, Taliban, al-Qa'ida, TTP, Kashmiri groups, Central Asian groups, and their state sponsors/opponents).
You are reading a published open-source research document (a scholarly report or article), given in chunks with `[PDF p.N]` page markers (or `[para N]` paragraph markers for web articles).

Rules:
- Extract EVERY named individual discussed as an actor in the history (jihadist commanders, fighters, financiers, clerics, tribal
  figures, Pakistani/Afghan/Arab/US officials, family members). Give role at the time discussed, affiliations, status if stated,
  family links, and places. Do NOT create person entries for the document's authors, reviewers, acknowledged colleagues, or cited
  scholars/journalists (e.g. Steve Coll, Peter Bergen, Thomas Ruttig) unless they are actors in the events themselves.
- Keep the document's transliteration as the name and add common alternative English spellings in aliases
  (e.g. 'al-Qa'ida' -> alias 'al-Qaeda'; 'Usama bin Ladin' -> alias 'Osama bin Laden'; 'Jalaluddin Haqqani' is canonical).
- Extract every organization (including fronts, madrasas, magazines, committees, state agencies), every place (with country and parent),
  every dated event, and every relationship between two named entities. Family and clan links, patronage/hosting/sheltering,
  training, funding, succession, command relations, meetings and travel are especially important. Record direction carefully:
  'sheltered_by'/'hosted_by'/'funded_by'/'trained_by' point from the recipient to the provider.
- Dates: use the most precise date the text supports; mark precision day|month|year|approx.
- Every relationship and mention needs a short verbatim supporting quote (<= 40 words) and a `timestamp` holding the page/paragraph marker, e.g. 'p.12' or 'para 7'.
  Footnotes count as text: extract names and links from them too, and quote them.
- Output ONLY valid JSON following the provided schema (no markdown fences, no commentary). Empty arrays are fine."""

def call(model, system, user, max_tokens=32000):
    body = json.dumps({"model": model, "max_tokens": max_tokens, "system": system,
                       "messages": [{"role": "user", "content": user}]}).encode()
    for attempt in range(6):
        try:
            req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
                "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=900) as r:
                j = json.load(r)
            return "".join(c.get("text", "") for c in j["content"]), j.get("stop_reason"), j.get("usage", {})
        except Exception as ex:
            msg = getattr(ex, 'read', lambda: b'')().decode(errors='ignore') if hasattr(ex, 'read') else str(ex)
            print("  api retry", attempt, str(ex)[:200], msg[:300], flush=True)
            if "credit balance" in msg: raise
            time.sleep(10 * (attempt + 1))
    raise RuntimeError("API failed")

def page_chunks(body, max_chars=24000):
    pages = re.split(r"(?=\[(?:PDF p\.|para )\d+\])", body)
    pages = [p for p in pages if p.strip()]
    out, cur = [], []
    for p in pages:
        if cur and sum(len(x) for x in cur) + len(p) > max_chars:
            out.append(cur); cur = cur[-1:]   # one-page overlap
        cur.append(p)
    if cur: out.append(cur)
    return ["".join(c) for c in out]

RELS_SYSTEM = """You are an intelligence analyst building a link-analysis database of jihadist networks in Afghanistan and Pakistan.
You are reading one chunk of a published open-source research document with `[PDF p.N]` page markers (or `[para N]` paragraph markers).
A first pass has already listed the named entities in this document; your job is the EXHAUSTIVE extraction of RELATIONSHIPS and DATED EVENTS.

Rules:
- For every pair of named entities (person/organization/place) that the text connects, emit one relationship using the schema types:
  family|member_of|leads|deputy_of|reports_to|allied_with|rival_of|hosted_by|sheltered_by|funded_by|trained_by|married_into|succeeded|killed|captured|negotiated_with|located_in|met_with|other.
  Typical connections in this literature: X was a commander under Y; X fought with/alongside Y; X hosted Arab volunteers at Z; X was based in/ran camps at Z;
  X received funds/weapons from Y (funded_by); X trained at Y's camp (trained_by); X studied under Y / at madrasa Y (use 'other' with detail);
  X sent Y to Z; X married into Y's tribe/family; X succeeded Y; X was deputy of Y; X was killed by Y; X met Y; X's magazine/front/committee (leads/member_of).
  Direction: 'sheltered_by'/'hosted_by'/'funded_by'/'trained_by' point from the recipient to the provider; 'leads' from leader to org; 'member_of' from person to org;
  'located_in' from entity to place; 'succeeded' from successor to predecessor; 'killed' from killer to victim.
- Use entity names exactly as in the ENTITIES list when the text refers to them; introduce new names only if the text names someone not in the list.
- Also emit every dated or datable event (attacks, meetings, travel, appointments, deaths, founding of fronts/camps/magazines, agreements, ISI/CIA supply decisions),
  with the actors involved and place. Date precision day|month|year|approx.
- Every relationship and event needs a verbatim supporting quote (<= 40 words) and `timestamp` = the page/paragraph marker ('p.12' / 'para 7').
- Footnotes count as text. Do not create relationships for the document's authors, reviewers or cited scholars/journalists.
- Expect 20-80 relationships per chunk for this kind of text. Output ONLY valid JSON: {"relationships": [...], "events": [...]} per the schema fragments given."""

def rels_pass(doc, body, ents, a, out_dir, schema):
    chs = page_chunks(body, a.rels_max_chars)
    frag = json.loads(schema)
    frag = json.dumps({"relationships": frag["relationships"], "events": frag["events"]}, indent=1)
    names = "\n".join(f"- {k}: " + "; ".join(ents[k]) for k in ("persons", "organizations", "places"))
    print(f"{doc['doc_id']}: relationship pass -> {len(chs)} chunks", flush=True)
    def work(ci):
        user = (f"DOCUMENT: {doc['title']} ({doc.get('authors')}, {doc.get('published')})\n(chunk {ci+1} of {len(chs)}; extract only what appears in this chunk)\n\n"
                f"ENTITIES already identified in this document:\n{names}\n\nSCHEMA FRAGMENTS:\n{frag}\n\nTEXT:\n{chs[ci]}")
        t0 = time.time(); text, stop, usage = call(a.model, RELS_SYSTEM, user)
        try:
            res = parse_json(text)
        except Exception as ex:
            print(f"  rels chunk {ci+1}: JSON parse failed ({ex}); repairing", flush=True)
            text2, _, _ = call(a.model, "Return ONLY the corrected, complete, valid JSON document. No commentary.",
                               "Fix this truncated/invalid JSON so it parses, dropping any incomplete trailing item:\n" + text)
            res = parse_json(text2)
        print(f"  rels chunk {ci+1}: {time.time()-t0:.0f}s stop={stop} out_tokens={usage.get('output_tokens')} rels={len(res.get('relationships',[]))} events={len(res.get('events',[]))}", flush=True)
        json.dump(res, open(os.path.join(out_dir, f"_{doc['doc_id']}_rels{ci+1:02d}.json"), "w"), indent=1, ensure_ascii=False)
        return res
    with ThreadPoolExecutor(a.workers) as ex:
        return list(ex.map(work, range(len(chs))))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("txt"); ap.add_argument("--out", default=None)
    ap.add_argument("--model", default="claude-sonnet-5-5"); ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-chars", type=int, default=24000); ap.add_argument("--rels-max-chars", type=int, default=12000)
    ap.add_argument("--stage", choices=["all", "entities", "rels"], default="all", help="'rels' re-runs only the relationship pass over an existing extraction")
    a = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = a.out or os.path.join(os.path.dirname(os.path.abspath(a.txt)), "extractions")
    os.makedirs(out_dir, exist_ok=True)
    schema = open(os.path.join(here, "schema.json")).read().replace('"episode": {"idx": 0, "title": "", "published": "", "guid": ""}',
                                                                     '"document": {"doc_id": "", "title": ""}')
    raw = open(a.txt).read(); head, _, body = raw.partition("\n")
    doc = json.loads(head)
    outp = os.path.join(out_dir, f"{doc['doc_id']}.json")
    if a.stage == "rels":
        res = json.load(open(outp))
    else:
        res = entities_pass(doc, body, a, out_dir, schema)
        json.dump(res, open(outp, "w"), indent=1, ensure_ascii=False)
    if a.stage in ("all", "rels"):
        ents = {k: [x["name"] for x in res.get(k, []) if x.get("name")] for k in ("persons", "organizations", "places")}
        parts = rels_pass(doc, body, ents, a, out_dir, schema)
        base = {k: res.get(k, []) for k in ("relationships", "events")}
        merged = merge([base] + parts, {})
        res["relationships"], res["events"] = merged["relationships"], merged["events"]
        json.dump(res, open(outp, "w"), indent=1, ensure_ascii=False)
    print(f"done {doc['doc_id']}: {len(res['persons'])} persons, {len(res['organizations'])} orgs, {len(res['places'])} places, "
          f"{len(res['relationships'])} rels, {len(res['events'])} events -> {outp}", flush=True)

def entities_pass(doc, body, a, out_dir, schema):
    chs = page_chunks(body, a.max_chars)
    print(f"{doc['doc_id']}: {len(body)} chars -> {len(chs)} chunks", flush=True)
    def work(ci):
        ch = chs[ci]
        user = (f"DOCUMENT: {doc['title']}\nAUTHORS: {doc.get('authors')}\nPUBLISHED: {doc.get('published')} by {doc.get('publisher')}\n"
                f"(chunk {ci+1} of {len(chs)}; extract only what appears in this chunk; use the [PDF p.N]/[para N] markers for `timestamp` as 'p.N'/'para N')\n\n"
                f"SCHEMA:\n{schema}\n\nTEXT:\n{ch}")
        t0 = time.time(); text, stop, usage = call(a.model, SYSTEM, user)
        try:
            res = parse_json(text)
        except Exception as ex:
            print(f"  chunk {ci+1}: JSON parse failed ({ex}); repairing", flush=True)
            text2, _, _ = call(a.model, "Return ONLY the corrected, complete, valid JSON document. No commentary.",
                               "Fix this truncated/invalid JSON so it parses, dropping any incomplete trailing item:\n" + text)
            res = parse_json(text2)
        print(f"  chunk {ci+1}: {time.time()-t0:.0f}s stop={stop} out_tokens={usage.get('output_tokens')} "
              f"persons={len(res.get('persons',[]))} rels={len(res.get('relationships',[]))}", flush=True)
        json.dump(res, open(os.path.join(out_dir, f"_{doc['doc_id']}_chunk{ci+1:02d}.json"), "w"), indent=1, ensure_ascii=False)
        return res
    with ThreadPoolExecutor(a.workers) as ex:
        parts = list(ex.map(work, range(len(chs))))
    res = merge(parts, {}); res.pop("episode", None)
    return {"document": doc, **res}

if __name__ == "__main__":
    main()
