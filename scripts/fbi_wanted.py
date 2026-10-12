#!/usr/bin/env python3
"""Normalise the FBI Wanted API snapshot (https://api.fbi.gov/wanted/v1/list, the 54 items shown on
https://www.fbi.gov/wanted/terrorism) into raw/sanctions/fbi_wanted.json.

Refresh the snapshot with:  python3 scripts/fbi_wanted.py --fetch
"""
import json, os, re, sys, html, urllib.request, time

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SNAP = os.path.join(ROOT, "raw/sanctions/fbi_wanted_snapshot.json")
OUT = os.path.join(ROOT, "raw/sanctions/fbi_wanted.json")
TERROR_SUBJECTS = ("Most Wanted Terrorists", "Seeking Information - Terrorism", "Domestic Terrorism")

def strip_html(s):
    s = re.sub(r"<br\s*/?>|</p>|</li>", "\n", s or ""); s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(s)).strip()

def fetch():
    items, page = {}, 1
    while True:
        u = f"https://api.fbi.gov/wanted/v1/list?pageSize=50&page={page}"
        d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=60))
        for it in d["items"]:
            if any(s in TERROR_SUBJECTS for s in (it.get("subjects") or [])): items[it["uid"]] = it
        if page * 50 >= d["total"]: break
        page += 1; time.sleep(0.5)
    json.dump(list(items.values()), open(SNAP, "w"), indent=1)
    print("snapshot:", len(items), "items")

def main():
    if "--fetch" in sys.argv: fetch()
    recs = []
    for it in json.load(open(SNAP)):
        cat = next((s for s in it.get("subjects", []) if s in TERROR_SUBJECTS), it.get("subjects", [""])[0])
        is_person = it.get("person_classification") == "Main" and not it["title"].upper().startswith(("KIDNAPPERS", "UNKNOWN"))
        physical = {k: it.get(k) for k in ("sex", "race", "hair", "eyes", "height_min", "height_max", "weight", "build", "complexion", "age_range", "scars_and_marks") if it.get(k)}
        recs.append({
            "kind": "persons" if is_person else "cases", "uid": it["uid"], "category": cat,
            "name": it["title"].strip(), "aliases": [a.strip() for a in (it.get("aliases") or []) if a.strip()],
            "dob": it.get("dates_of_birth_used") or [], "pob": it.get("place_of_birth") or "",
            "nationality": it.get("nationality") or "", "languages": it.get("languages") or [],
            "occupations": it.get("occupations") or [], "possible_countries": it.get("possible_countries") or [],
            "physical": physical, "ncic": it.get("ncic") or "",
            "reward_text": strip_html(it.get("reward_text")), "reward_max": it.get("reward_max"),
            "description": strip_html(it.get("description")), "caution": strip_html(it.get("caution")),
            "details": strip_html(it.get("details")), "remarks": strip_html(it.get("remarks")),
            "additional_information": strip_html(it.get("additional_information")),
            "warning_message": it.get("warning_message") or "", "status": it.get("status") or "",
            "field_offices": it.get("field_offices") or [], "legat_names": it.get("legat_names") or [],
            "publication": it.get("publication") or "", "modified": it.get("modified") or "",
            "url": it.get("url"), "photo_url": (it.get("images") or [{}])[0].get("original"),
            "photo_caption": (it.get("images") or [{}])[0].get("caption") or "",
            "files": [f.get("url") for f in (it.get("files") or []) if f.get("url")],
        })
    json.dump(recs, open(OUT, "w"), indent=1, ensure_ascii=False)
    from collections import Counter
    print(len(recs), "records", dict(Counter(r["category"] for r in recs)), dict(Counter(r["kind"] for r in recs)))

if __name__ == "__main__":
    main()
