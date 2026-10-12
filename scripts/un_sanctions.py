#!/usr/bin/env python3
"""Parse the UN Security Council consolidated sanctions XML into raw/sanctions/un_1988.json.

Keeps only the 1988 (Taliban) list. Family/associate links are parsed from the COMMENTS1 field
(e.g. "Son of Jalaluddin Haqqani (TAi.040)") and kept with the sentence they came from as the quote.
Narrative summaries (reasons for listing) scraped from main.un.org are merged in when present.
"""
import re, json, os, sys, xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
XML = os.path.join(ROOT, "raw/sanctions/un_consolidated_snapshot.xml")
NARR = os.path.join(ROOT, "raw/sanctions/un_1988_narratives.json")
OUT = os.path.join(ROOT, "raw/sanctions/un_1988.json")

REL_WORDS = {
    "son": "son_of", "daughter": "daughter_of", "father": "father_of", "mother": "mother_of",
    "brother": "brother_of", "sister": "sister_of", "uncle": "uncle_of", "nephew": "nephew_of",
    "cousin": "cousin_of", "grandson": "grandson_of", "grandfather": "grandfather_of",
    "father-in-law": "father_in_law_of", "son-in-law": "son_in_law_of", "brother-in-law": "brother_in_law_of",
    "husband": "spouse_of", "wife": "spouse_of", "half-brother": "brother_of", "step-son": "son_of",
    "deputy": "deputy_of", "deputy commander": "deputy_of", "close associate": "associate_of",
    "associate": "associate_of", "assistant": "assistant_of", "adviser": "adviser_of", "advisor": "adviser_of",
    "driver": "driver_of", "bodyguard": "bodyguard_of", "spokesperson": "spokesperson_of", "financier": "financier_of",
    "member": "member_of", "commander": "commander_in", "leader": "leader_of",
}
REF = re.compile(r"\((TA[ie]\.\d{3})\)")

def txt(e, tag): return (e.findtext(tag) or "").strip()
def vals(e, tag): return [v.text.strip() for v in e.findall(f"{tag}/VALUE") if (v.text or "").strip()]

def name_of(e):
    return " ".join(x for x in (txt(e, k) for k in ("FIRST_NAME", "SECOND_NAME", "THIRD_NAME", "FOURTH_NAME")) if x)

def addr(a):
    parts = [txt(a, k) for k in ("STREET", "CITY", "STATE_PROVINCE", "COUNTRY")]
    s = ", ".join(p for p in parts if p); n = txt(a, "NOTE")
    return (s + (f" ({n})" if n else "")).strip()

def dob(d):
    t = txt(d, "TYPE_OF_DATE")
    if t == "EXACT": s = txt(d, "DATE")
    elif t == "BETWEEN": s = f"{txt(d,'FROM_YEAR')}–{txt(d,'TO_YEAR')}"
    elif t == "APPROXIMATELY": s = f"c. {txt(d,'YEAR') or txt(d,'DATE')}"
    else: s = txt(d, "YEAR") or txt(d, "DATE")
    n = txt(d, "NOTE"); return (s + (f" ({n})" if n else "")).strip()

ORG_CUES = [("founded by", "founder_of"), ("headed by", "leader_of"), ("led by", "leader_of"), ("members include", "member_of"),
            ("member", "member_of"), ("commander", "commander_in"), ("associated with", "associated_with")]

def links_from_comments(ref, comments):
    """Return [{type, target_ref, target_name, quote}] for every '(TAi.NNN)' / '(TAe.NNN)' cross-reference in COMMENTS1.
    Direction: for individual records the listed person is the source (e.g. TAi.144 son_of TAi.040).
    For entity records (TAe.*) the referenced person is the source and the entity the target (e.g. TAi.040 founder_of TAe.012)."""
    out = []
    is_entity = ref.startswith("TAe")
    for sent in re.split(r"(?<=[.;])\s+", comments):
        for m in REF.finditer(sent):
            tref = m.group(1); before = sent[:m.start()].rstrip(); low = before.lower()
            nm = re.search(r"((?:[A-Z][\w'’\-]*\s+){0,6}[A-Z][\w'’\-]*)\s*$", before)
            tname = nm.group(1).strip() if nm else ""
            if is_entity:
                prev = [x.end() for x in REF.finditer(sent) if x.end() <= m.start()]
                seg = low[prev[-1]:] if prev else low
                rtype = "associated_with"
                for cue, t in ORG_CUES:
                    if re.search(rf"\b{cue}\b", seg): rtype = t; break
                out.append({"type": rtype, "target_ref": tref, "target_name": tname, "quote": sent.strip(), "reverse": True})
                continue
            rtype = "associated_with"
            for w in sorted(REL_WORDS, key=len, reverse=True):
                if re.search(rf"\b{re.escape(w)}s? (of|to|in|for)\b[^.;()]{{0,60}}$", low) or re.search(rf"\b{re.escape(w)}\b[^.;()]{{0,30}}$", low):
                    rtype = REL_WORDS[w]; break
            if re.search(r"\bunder\b[^.;()]{0,60}$", low): rtype = "subordinate_of"
            if tref.startswith("TAe"):
                if re.search(r"\b(head(ing|s|ed)?|lead(er|ing|s)?) (of|the)\b[^.;()]{0,60}$", low): rtype = "leader_of"
                elif re.search(r"\bmember of\b[^.;()]{0,60}$", low): rtype = "member_of"
                elif rtype in ("son_of", "brother_of", "father_of", "uncle_of", "cousin_of", "nephew_of"): rtype = "associated_with"
            out.append({"type": rtype, "target_ref": tref, "target_name": tname, "quote": sent.strip(), "reverse": False})
    return out

def main():
    r = ET.parse(XML).getroot()
    narr = json.load(open(NARR)) if os.path.exists(NARR) else {}
    recs = []
    for kind, tag in (("persons", "INDIVIDUAL"), ("organizations", "ENTITY")):
        for e in r.iter(tag):
            if txt(e, "UN_LIST_TYPE") != "Taliban": continue
            ref = txt(e, "REFERENCE_NUMBER"); p = "INDIVIDUAL_" if kind == "persons" else "ENTITY_"
            comments = txt(e, "COMMENTS1")
            comments_clean = re.sub(r"\s*INTERPOL-UN Security Council Special Notice:?\s*https?://\S+", "", comments).strip()
            rec = {
                "kind": kind, "reference_number": ref, "dataid": txt(e, "DATAID"),
                "name": name_of(e), "name_original_script": txt(e, "NAME_ORIGINAL_SCRIPT"),
                "aliases": [{"name": txt(a, "ALIAS_NAME"), "quality": txt(a, "QUALITY")} for a in e.findall(f"{p}ALIAS") if txt(a, "ALIAS_NAME")],
                "title": "; ".join(vals(e, "TITLE")), "designation": "; ".join(vals(e, "DESIGNATION")),
                "nationality": "; ".join(vals(e, "NATIONALITY")),
                "listed_on": txt(e, "LISTED_ON"), "last_updated": "; ".join(vals(e, "LAST_DAY_UPDATED")),
                "dob": [dob(d) for d in e.findall("INDIVIDUAL_DATE_OF_BIRTH")],
                "pob": [addr(a) for a in e.findall("INDIVIDUAL_PLACE_OF_BIRTH")],
                "addresses": [addr(a) for a in e.findall(f"{p}ADDRESS") if addr(a)],
                "documents": [" ".join(x for x in (txt(d, "TYPE_OF_DOCUMENT"), txt(d, "NUMBER"), txt(d, "ISSUING_COUNTRY"), txt(d, "NOTE")) if x) for d in e.findall("INDIVIDUAL_DOCUMENT")],
                "comments": comments_clean, "interpol_link": txt(e, "INTERPOL_LINK"),
                "links": links_from_comments(ref, comments_clean),
                "narrative": narr.get(ref, {}),
            }
            rec["hqn_linked"] = bool(re.search(r"haqqani network|TAe\.012", comments, re.I) or "HAQQANI" in rec["name"].upper()
                                      or any(l["target_ref"] in ("TAe.012", "TAi.040", "TAi.144") for l in rec["links"]))
            recs.append(rec)
    json.dump(recs, open(OUT, "w"), indent=1, ensure_ascii=False)
    print(len(recs), "records;", sum(r["hqn_linked"] for r in recs), "HQN-linked;", sum(len(r["links"]) for r in recs), "cross-ref links")

if __name__ == "__main__":
    main()
