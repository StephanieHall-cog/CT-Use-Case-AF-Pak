#!/usr/bin/env python3
"""QA for document extractions (raw/documents/extractions/<doc_id>.json).
Prints: persons that do not resolve to an existing canonical name (candidates for aliases.json), names that look like
authors/scholars rather than actors, relationships whose endpoints are not among the document's entities, and edges
lacking quote/page. Usage: python3 scripts/review_docs.py [doc_id ...]
"""
import json, glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize import Resolver, fold

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NON_ACTORS = {fold(x) for x in ["Don Rassler", "Vahid Brown", "Steve Coll", "Peter Bergen", "Thomas Ruttig", "Antonio Giustozzi", "Jere Van Dyk",
    "Gretchen Peters", "Nelly Lahoud", "Thomas Hegghammer", "Bob Nickelsberg", "Arie Perliger", "Bill Braniff", "Scott Helfstein", "Alex Gallo",
    "John Padgett", "Paul McLean", "Pir Zubair Shah", "Morten Skoldager", "Lawrence Wright", "Camille Tawil", "Anne Stenersen", "Brian Fishman",
    "Syed Saleem Shahzad", "Carlotta Gall", "Alan Cullison", "Mark Adkin", "Reid Sawyer", "John Abizaid", "Vinnie Viola", "Ahmed"]}

def main():
    R = Resolver()
    known_persons = {fold(c) for c in json.load(open(f"{ROOT}/scripts/aliases.json"))["persons"]}
    # names seen in the podcast corpus (canonical after resolution)
    corpus = set()
    for f in glob.glob(f"{ROOT}/raw/extractions/*.json"):
        d = json.load(open(f))
        for p in d.get("persons", []) or []:
            corpus.add(fold(R.resolve("persons", p.get("name", ""))))
    ids = sys.argv[1:] or [os.path.basename(f)[:-5] for f in glob.glob(f"{ROOT}/raw/documents/extractions/*.json") if not os.path.basename(f).startswith("_")]
    for doc_id in ids:
        d = json.load(open(f"{ROOT}/raw/documents/extractions/{doc_id}.json"))
        print(f"\n=== {doc_id}: {len(d['persons'])} persons, {len(d['organizations'])} orgs, {len(d['places'])} places, {len(d['relationships'])} rels, {len(d['events'])} events")
        names = {fold(x["name"]) for k in ("persons", "organizations", "places") for x in d.get(k, []) if x.get("name")}
        for k in ("persons", "organizations", "places"):
            for x in d.get(k, []):
                for al in x.get("aliases", []) or []: names.add(fold(al))
        print("-- persons flagged as non-actors (authors/scholars):")
        for p in d["persons"]:
            if fold(p["name"]) in NON_ACTORS: print("   ", p["name"], "|", p.get("role"))
        print("-- persons already in podcast corpus (will merge):")
        merged = [p["name"] for p in d["persons"] if fold(R.resolve("persons", p["name"])) in corpus]
        print("   ", "; ".join(f"{n} -> {R.resolve('persons', n)}" if R.resolve('persons', n) != n else n for n in merged))
        print("-- NEW persons (not in corpus):")
        for p in d["persons"]:
            if fold(R.resolve("persons", p["name"])) not in corpus and fold(p["name"]) not in NON_ACTORS:
                print(f"    {p['name']} [{', '.join(p.get('aliases', []) or [])}] | {p.get('role')}")
        print("-- relationship endpoints not among document entities:")
        for r in d["relationships"]:
            for e in (r.get("source"), r.get("target")):
                if e and fold(e) not in names and fold(R.resolve("persons", e)) not in names and not R.resolve_any(e)[0]:
                    print("   ", e, "<-", r.get("type"), "|", (r.get("quote") or "")[:80])
        bad = [r for r in d["relationships"] if not r.get("quote") or not r.get("timestamp")]
        print(f"-- relationships without quote/page: {len(bad)}")
        from collections import Counter
        print("-- relationship types:", dict(Counter(r.get("type") for r in d["relationships"]).most_common()))

if __name__ == "__main__":
    main()
