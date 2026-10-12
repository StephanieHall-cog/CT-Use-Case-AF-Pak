#!/usr/bin/env python3
"""Batch variant of extract_doc.py: runs the same entity and relationship passes over MANY document text files
through the Anthropic Message Batches API (half price, no per-request concurrency limits).
Usage: python3 scripts/extract_doc_batch.py raw/documents/nsa-*.txt [--stage all|entities|rels] [--model claude-sonnet-5-5]
       [--out raw/documents/extractions] [--state /tmp/batch_state.json]
Output per document is identical to extract_doc.py (raw/documents/extractions/<doc_id>.json). Needs ANTHROPIC_API_KEY.
The state file remembers submitted batch ids so an interrupted run can be resumed with the same command."""
import json, os, sys, time, argparse, re, hashlib, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import parse_json, merge
from extract_doc import SYSTEM, RELS_SYSTEM, page_chunks, call

API = "https://api.anthropic.com/v1/messages/batches"
HDR = lambda: {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"}

def http(url, data=None):
    for attempt in range(8):
        try:
            req = urllib.request.Request(url, data=data, headers=HDR())
            with urllib.request.urlopen(req, timeout=600) as r:
                return r.read()
        except Exception as ex:
            msg = ex.read().decode(errors="ignore")[:300] if hasattr(ex, "read") else str(ex)
            print("  api retry", attempt, str(ex)[:120], msg, flush=True); time.sleep(15 * (attempt + 1))
    raise RuntimeError("batch API failed")

def submit(requests, state, key):
    """Submit requests (<=10k each) unless state already has batch ids for this key."""
    if state.get(key):
        return state[key]
    ids = []
    for i in range(0, len(requests), 10000):
        j = json.loads(http(API, json.dumps({"requests": requests[i:i + 10000]}).encode()))
        ids.append(j["id"]); print(f"submitted batch {j['id']} ({len(requests[i:i+10000])} requests)", flush=True)
    state[key] = ids
    return ids

def collect(ids):
    """Poll until all batches end; yield (custom_id, text or None, error)."""
    for bid in ids:
        while True:
            j = json.loads(http(f"{API}/{bid}"))
            c = j.get("request_counts", {})
            print(f"  {bid}: {j['processing_status']} {c}", flush=True)
            if j["processing_status"] == "ended": break
            time.sleep(60)
        for line in http(j["results_url"]).decode().splitlines():
            if not line.strip(): continue
            r = json.loads(line); res = r["result"]
            if res["type"] == "succeeded":
                m = res["message"]
                yield r["custom_id"], "".join(c.get("text", "") for c in m["content"]), m.get("stop_reason")
            else:
                yield r["custom_id"], None, res.get("error") or res["type"]

def parse_or_repair(text, model, label):
    try:
        return parse_json(text)
    except Exception as ex:
        print(f"  {label}: JSON parse failed ({ex}); repairing", flush=True)
        text2, _, _ = call(model, "Return ONLY the corrected, complete, valid JSON document. No commentary.",
                           "Fix this truncated/invalid JSON so it parses, dropping any incomplete trailing item:\n" + text)
        return parse_json(text2)

def load_docs(paths):
    docs = {}
    for p in paths:
        raw = open(p).read(); head, _, body = raw.partition("\n")
        d = json.loads(head); docs[d["doc_id"]] = (d, body)
    return docs

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("txt", nargs="+"); ap.add_argument("--out", default=None)
    ap.add_argument("--model", default="claude-sonnet-5-5"); ap.add_argument("--max-chars", type=int, default=24000)
    ap.add_argument("--rels-max-chars", type=int, default=12000); ap.add_argument("--max-tokens", type=int, default=32000)
    ap.add_argument("--stage", choices=["all", "entities", "rels"], default="all"); ap.add_argument("--state", default="/tmp/extract_doc_batch_state.json")
    a = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = a.out or os.path.join(os.path.dirname(os.path.abspath(a.txt[0])), "extractions"); os.makedirs(out_dir, exist_ok=True)
    schema = open(os.path.join(here, "schema.json")).read().replace('"episode": {"idx": 0, "title": "", "published": "", "guid": ""}',
                                                                     '"document": {"doc_id": "", "title": ""}')
    frag = json.loads(schema); frag = json.dumps({"relationships": frag["relationships"], "events": frag["events"]}, indent=1)
    state = json.load(open(a.state)) if os.path.exists(a.state) else {}
    save_state = lambda: json.dump(state, open(a.state, "w"))
    docs = load_docs(a.txt)
    cid = lambda doc_id, stage, ci: f"{hashlib.md5(doc_id.encode()).hexdigest()[:16]}__{stage}__{ci:03d}"  # custom_id max 64 chars

    if a.stage in ("all", "entities"):
        reqs, chunks = [], {}
        for doc_id, (doc, body) in docs.items():
            chs = page_chunks(body, a.max_chars); chunks[doc_id] = chs
            for ci, ch in enumerate(chs):
                user = (f"DOCUMENT: {doc['title']}\nAUTHORS: {doc.get('authors')}\nPUBLISHED: {doc.get('published')} by {doc.get('publisher')}\n"
                        f"(chunk {ci+1} of {len(chs)}; extract only what appears in this chunk; use the [PDF p.N]/[para N] markers for `timestamp` as 'p.N'/'para N')\n\n"
                        f"SCHEMA:\n{schema}\n\nTEXT:\n{ch}")
                reqs.append({"custom_id": cid(doc_id, "ent", ci), "params": {"model": a.model, "max_tokens": a.max_tokens, "system": SYSTEM,
                                                                             "messages": [{"role": "user", "content": user}]}})
        print(f"entities pass: {len(docs)} docs -> {len(reqs)} chunk requests", flush=True)
        ids = submit(reqs, state, "entities"); save_state()
        parts = {d: [None] * len(chunks[d]) for d in docs}
        lookup = {cid(d, "ent", ci): (d, ci) for d in docs for ci in range(len(chunks[d]))}
        for custom_id, text, err in collect(ids):
            d, ci = lookup[custom_id]
            if text is None:
                print(f"  {custom_id}: FAILED {err}", flush=True); continue
            res = parse_or_repair(text, a.model, custom_id)
            json.dump(res, open(os.path.join(out_dir, f"_{d}_chunk{ci+1:02d}.json"), "w"), indent=1, ensure_ascii=False)
            parts[d][ci] = res
        for d, (doc, body) in docs.items():
            ok = [p for p in parts[d] if p is not None]
            if len(ok) < len(parts[d]): print(f"  {d}: {len(parts[d])-len(ok)} chunks missing; rerun to fill", flush=True)
            res = merge(ok, {}); res.pop("episode", None)
            json.dump({"document": doc, **res}, open(os.path.join(out_dir, f"{d}.json"), "w"), indent=1, ensure_ascii=False)
        print("entities pass done", flush=True)

    if a.stage in ("all", "rels"):
        reqs, chunks, base = [], {}, {}
        for doc_id, (doc, body) in docs.items():
            outp = os.path.join(out_dir, f"{doc_id}.json")
            if not os.path.exists(outp): print(f"  {doc_id}: no entity extraction, skipping"); continue
            res = json.load(open(outp)); base[doc_id] = res
            ents = {k: [x["name"] for x in res.get(k, []) if x.get("name")] for k in ("persons", "organizations", "places")}
            names = "\n".join(f"- {k}: " + "; ".join(ents[k]) for k in ents)
            chs = page_chunks(body, a.rels_max_chars); chunks[doc_id] = chs
            for ci, ch in enumerate(chs):
                user = (f"DOCUMENT: {doc['title']} ({doc.get('authors')}, {doc.get('published')})\n(chunk {ci+1} of {len(chs)}; extract only what appears in this chunk)\n\n"
                        f"ENTITIES already identified in this document:\n{names}\n\nSCHEMA FRAGMENTS:\n{frag}\n\nTEXT:\n{ch}")
                reqs.append({"custom_id": cid(doc_id, "rel", ci), "params": {"model": a.model, "max_tokens": a.max_tokens, "system": RELS_SYSTEM,
                                                                             "messages": [{"role": "user", "content": user}]}})
        print(f"relationship pass: {len(base)} docs -> {len(reqs)} chunk requests", flush=True)
        ids = submit(reqs, state, "rels"); save_state()
        parts = {d: [] for d in base}
        lookup = {cid(d, "rel", ci): (d, ci) for d in base for ci in range(len(chunks[d]))}
        for custom_id, text, err in collect(ids):
            d, ci = lookup[custom_id]
            if text is None:
                print(f"  {custom_id}: FAILED {err}", flush=True); continue
            res = parse_or_repair(text, a.model, custom_id)
            json.dump(res, open(os.path.join(out_dir, f"_{d}_rels{ci+1:02d}.json"), "w"), indent=1, ensure_ascii=False)
            parts[d].append(res)
        for d, res in base.items():
            b = {k: res.get(k, []) for k in ("relationships", "events")}
            merged = merge([b] + parts[d], {})
            res["relationships"], res["events"] = merged["relationships"], merged["events"]
            json.dump(res, open(os.path.join(out_dir, f"{d}.json"), "w"), indent=1, ensure_ascii=False)
            print(f"done {d}: {len(res['persons'])} persons, {len(res['organizations'])} orgs, {len(res['places'])} places, "
                  f"{len(res['relationships'])} rels, {len(res['events'])} events", flush=True)

if __name__ == "__main__":
    main()
