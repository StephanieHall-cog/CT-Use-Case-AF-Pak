#!/usr/bin/env python3
"""Entity/relationship extraction from transcripts with Claude.
Usage: python3 extract.py transcripts/ [--out extractions] [--model claude-sonnet-5-5]
Needs ANTHROPIC_API_KEY in env. Skips episodes already extracted. Long transcripts are chunked (with overlap) and merged.
"""
import json, os, sys, glob, time, argparse, re, urllib.request

SYSTEM = """You are an intelligence analyst building a link-analysis database of jihadist networks in Afghanistan and Pakistan
(Taliban, Haqqani Network, al-Qaeda core, AQIS, TTP, ISKP and their state sponsors/opponents) from podcast transcripts of
FDD's Long War Journal show 'Generation Jihad'. The transcript is machine-generated: names are often mis-spelled
(e.g. 'Siraj Hakani' = Sirajuddin Haqqani, 'Zawahari' = Ayman al-Zawahiri, 'Hibatullah Akundzada' = Hibatullah Akhundzada).
Normalize to the standard English transliteration and keep the raw spelling in aliases.

Rules:
- Extract EVERY named individual the hosts DISCUSS (jihadists, Taliban officials, Pakistani/Iranian/Afghan/US officials, family members),
  with role, affiliations, status, family links, and places. Do NOT create person entries for the hosts/presenters
  (Bill Roggio, Tom Joscelyn, Caleb Weiss, Joe Truzman, David Daoud, Behnam Ben Taleblu, Ahmad Sharawi, Edmund Fitton-Brown when hosting)
  unless they are themselves the subject (then set is_presenter_or_guest=true). Guests who are actors in the story
  (e.g. an Afghan general) get an entry with is_presenter_or_guest=true.
- Extract every organization, place (with country), dated event, and every relationship between two named entities.
  Family relations are especially important (father/son/brother/in-law/clan). Record succession, who sheltered whom,
  who was killed by whom, who met whom, who is based where.
- Dates: use the most precise date stated; if the hosts say 'last week' use the episode publish date to resolve it and mark precision 'approx'.
- Every relationship needs a short supporting quote and a timestamp from the transcript line markers [MMM:SS].
- Output ONLY valid JSON following the provided schema (no markdown fences, no commentary). Empty arrays are fine."""

def call(model, system, user, max_tokens=16000):
    body = json.dumps({"model": model, "max_tokens": max_tokens, "system": system,
                       "messages": [{"role":"user","content": user}]}).encode()
    for attempt in range(6):
        try:
            req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
                "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as r:
                j = json.load(r)
            return "".join(c.get("text","") for c in j["content"]), j.get("stop_reason")
        except Exception as ex:
            msg = getattr(ex, 'read', lambda: b'')().decode(errors='ignore') if hasattr(ex,'read') else str(ex)
            print("  api retry", attempt, str(ex)[:200], msg[:200]); time.sleep(10*(attempt+1))
    raise RuntimeError("API failed")

def parse_json(s):
    s = s.strip()
    s = re.sub(r"^```(?:json)?", "", s).strip(); s = re.sub(r"```$", "", s).strip()
    i = s.find("{"); j = s.rfind("}")
    return json.loads(s[i:j+1])

def chunks(lines, max_chars=60000, overlap=40):
    out, cur, n = [], [], 0
    for ln in lines:
        cur.append(ln); n += len(ln)+1
        if n >= max_chars:
            out.append(cur); cur = cur[-overlap:]; n = sum(len(x)+1 for x in cur)
    if cur and (not out or cur is not out[-1]): out.append(cur)
    return out

def merge(parts, ep):
    res = {"episode": ep, "persons": [], "organizations": [], "places": [], "events": [], "relationships": [], "sources_cited": [], "key_claims": []}
    seen = {k:set() for k in res}
    for p in parts:
        for k in ["persons","organizations","places"]:
            for it in p.get(k, []) or []:
                key = (it.get("name") or "").strip().lower()
                if not key: continue
                if key in seen[k]:
                    # merge arrays into existing
                    ex = next(x for x in res[k] if (x.get("name") or "").strip().lower()==key)
                    for f,v in it.items():
                        if isinstance(v, list): ex[f] = (ex.get(f) or []) + [x for x in v if x not in (ex.get(f) or [])]
                        elif not ex.get(f) and v: ex[f] = v
                else:
                    seen[k].add(key); res[k].append(it)
        for k in ["events","relationships"]:
            for it in p.get(k, []) or []:
                key = json.dumps({a:it.get(a) for a in ("source","target","type","date","description")}, sort_keys=True)
                if key not in seen[k]: seen[k].add(key); res[k].append(it)
        for k in ["sources_cited","key_claims"]:
            for it in p.get(k, []) or []:
                if it not in res[k]: res[k].append(it)
    return res

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("tdir"); ap.add_argument("--out", default="extractions")
    ap.add_argument("--model", default="claude-sonnet-5-5"); a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    schema = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.json")).read()
    for txt in sorted(glob.glob(os.path.join(a.tdir, "*.txt"))):
        base = os.path.basename(txt)[:-4]; outp = os.path.join(a.out, base+".json")
        if os.path.exists(outp): print("skip", base); continue
        raw = open(txt).read(); head, _, body = raw.partition("\n\n")
        m = re.search(r"idx: (\d+)\s+guid: (\S+)", head); title = head.splitlines()[0][2:]
        pub = re.search(r"published: (.*?)  duration", head).group(1)
        ep = {"idx": int(m.group(1)), "title": title, "published": pub, "guid": m.group(2)}
        parts = []
        for ci, ch in enumerate(chunks(body.splitlines())):
            user = (f"EPISODE: {title}\nPUBLISHED: {pub}\nDESCRIPTION: {head.splitlines()[2][2:]}\n"
                    f"(chunk {ci+1}; extract only what appears in this chunk)\n\nSCHEMA:\n{schema}\n\nTRANSCRIPT:\n" + "\n".join(ch))
            t0 = time.time()
            text, stop = call(a.model, SYSTEM, user)
            try:
                parts.append(parse_json(text))
            except Exception as ex:
                print("  JSON parse failed; retrying with repair", ex)
                text2, _ = call(a.model, "Return ONLY the corrected, complete, valid JSON document. No commentary.", "Fix this truncated/invalid JSON so it parses, dropping any incomplete trailing item:\n"+text)
                parts.append(parse_json(text2))
            print(f"  {base} chunk {ci+1}: {time.time()-t0:.0f}s stop={stop}", flush=True)
        res = merge(parts, ep)
        json.dump(res, open(outp,"w"), indent=1, ensure_ascii=False)
        print(f"done {base}: {len(res['persons'])} persons, {len(res['relationships'])} rels, {len(res['events'])} events", flush=True)

if __name__ == "__main__":
    main()
