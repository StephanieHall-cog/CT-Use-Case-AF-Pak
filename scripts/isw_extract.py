"""Extract plot points from ISW Map Room images with Claude vision.

Input : isw/manifest.json (one record per map page, written by scripts/isw_scrape.py) + local map images.
Output: isw/maps/<slug>.json  — map metadata, legend, pixel-anchored labelled places and plot points.
Pixel positions are expressed in percent of the full image (x right, y down) so they survive resizing; they are turned
into lat/lon later by scripts/build_isw_db.py (anchor-based affine fit + gazetteer lookup). Re-runnable; skips done maps.

usage: python3 scripts/isw_extract.py --images /path/to/img [--only slug] [--model claude-opus-4-6]
"""
import argparse, base64, io, json, os, re, sys, time
from PIL import Image, ImageDraw, ImageFont
import anthropic

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
MAN = os.path.join(ROOT, "isw", "manifest.json"); OUT = os.path.join(ROOT, "isw", "maps")
MAXDIM = 1568

PROMPT = """You are digitising a static conflict map published by the Institute for the Study of War (ISW) / AEI Critical Threats Project for an Afghanistan–Pakistan militant-network database.

Page title: {title}
Page date: {date}
Page text: {page_text}

You get (1) the full map with a labelled percentage grid overlaid (x% from left, y% from top) and (2) optionally zoomed tiles of the same map; tile grids are labelled in FULL-image percent so every coordinate you return is in full-image percent.

Return ONE JSON object (no prose, no markdown fence) with:
"map": {{"title_on_map": str, "subtitle": str|null, "as_of_date": "YYYY-MM-DD"|null, "period_start": "YYYY-MM-DD"|null, "period_end": "YYYY-MM-DD"|null, "date_precision": "day"|"month"|"year"|null, "geographic_extent": str, "map_type": one of ["event_points","control_zones","force_disposition","reference","thematic"], "producer": str|null, "cartographer": str|null, "caption_text": str|null (any explanatory paragraph printed on the map, verbatim), "notes": str|null}}
"legend": [{{"label": str (verbatim legend text), "symbol": str (e.g. "red circle","purple area","black diamond"), "kind": "point"|"area"|"line"|"other"}}]
"anchors": [ labelled reference places printed on the map whose position you can read — cities, towns, district/province names, country names, bases. {{"name": str (as printed), "kind": "city"|"town"|"district"|"province"|"country"|"base"|"river"|"region"|"other", "country": "AF"|"PK"|"IR"|"TJ"|"UZ"|"TM"|"IN"|"CN"|null, "x_pct": float, "y_pct": float}} — be generous (15–60 anchors if the map has them); give the position of the label's town dot where there is one, else the label centre. Accuracy matters: these anchors are used to georeference the map. ]
"plots": [ EVERY individual plotted marker or shaded area, one entry each — do not summarise clusters, enumerate each dot you can distinguish. {{"legend_class": str (must match a legend label, or "unlabelled"), "marker": "point"|"area"|"line", "x_pct": float, "y_pct": float (centre), "extent_pct": float|null (approx radius for areas), "label": str|null (text printed next to this plot, verbatim), "place_name": str|null (nearest labelled town/district you can confidently associate; null if none), "admin_area": str|null (province/district/agency as readable from the map), "country": "AF"|"PK"|null, "actors": [str] (groups/forces implicated by the legend class or label, e.g. "TTP","ISKP","Taliban","Pakistani security forces","ISAF","Haqqani Network"), "event_type": str (short: "attack","clash","security_operation","control","support_zone","contested","hq","base","protest","mining_project","governor_appointment","deportation","sanctuary","supply_zone","operation","closure","presence","other"), "date": "YYYY-MM-DD"|null (only if printed), "description": str (one sentence of what the marker shows), "confidence": "high"|"medium"|"low"}} ]
"named_persons": [{{"name": str, "role": str|null, "affiliation": str|null, "place": str|null, "x_pct": float|null, "y_pct": float|null}}] (people named anywhere on the map)
"named_orgs": [str] (organisations/forces/units named on the map, verbatim)
"text_blocks": [str] (other substantive printed text: inset notes, numbered lists, footnotes)

Rules: coordinates are floats 0–100 in full-image percent. Do not invent locations; if a dot has no readable nearby label leave place_name null and rely on x/y. Keep going until all markers are enumerated even if there are 100+."""


def fit(im, maxdim=MAXDIM):
    w, h = im.size; s = min(1.0, maxdim / max(w, h))
    return im.resize((int(w * s), int(h * s)), Image.LANCZOS) if s < 1 else im.copy()


def grid(im, x0=0.0, x1=100.0, y0=0.0, y1=100.0, step=5):
    """Overlay a percentage grid. (x0..x1, y0..y1) = region of the full image this crop covers, in percent."""
    im = im.convert("RGB"); d = ImageDraw.Draw(im, "RGBA"); w, h = im.size
    try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", max(12, w // 90))
    except Exception: font = ImageFont.load_default()
    for p in range(0, 101, step):
        if x0 <= p <= x1:
            x = (p - x0) / (x1 - x0) * (w - 1); major = p % 10 == 0
            d.line([(x, 0), (x, h)], fill=(0, 90, 255, 140 if major else 60), width=2 if major else 1)
            if major: d.text((x + 3, 3), f"x{p}", fill=(0, 60, 220, 255), font=font); d.text((x + 3, h - font.size - 4), f"x{p}", fill=(0, 60, 220, 255), font=font)
        if y0 <= p <= y1:
            y = (p - y0) / (y1 - y0) * (h - 1); major = p % 10 == 0
            d.line([(0, y), (w, y)], fill=(0, 90, 255, 140 if major else 60), width=2 if major else 1)
            if major: d.text((3, y + 2), f"y{p}", fill=(0, 60, 220, 255), font=font); d.text((w - 4 * font.size, y + 2), f"y{p}", fill=(0, 60, 220, 255), font=font)
    return im


def tiles(im):
    """2x2 (or 2x3 for tall images) overlapping tiles for maps larger than ~2000px."""
    w, h = im.size
    if max(w, h) < 2000: return []
    nx = 2; ny = 3 if h > 1.3 * w else 2
    out = []
    for j in range(ny):
        for i in range(nx):
            x0 = max(0, i / nx - 0.05); x1 = min(1, (i + 1) / nx + 0.05); y0 = max(0, j / ny - 0.05); y1 = min(1, (j + 1) / ny + 0.05)
            crop = im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
            out.append(grid(fit(crop), x0 * 100, x1 * 100, y0 * 100, y1 * 100))
    return out


def b64(im):
    buf = io.BytesIO(); im.convert("RGB").save(buf, "JPEG", quality=88); return base64.b64encode(buf.getvalue()).decode()


def extract(client, model, m, img_path):
    im = Image.open(img_path); im.load()
    if im.mode in ("P", "RGBA", "LA"): im = im.convert("RGBA").convert("RGB")
    parts = [grid(fit(im))] + tiles(im)
    content = [{"type": "text", "text": PROMPT.format(title=m["title"], date=m.get("page_date"), page_text=m.get("page_text") or "(none)")},
               {"type": "text", "text": "Full map with grid:"}, {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64(parts[0])}}]
    for k, t in enumerate(parts[1:], 1):
        content += [{"type": "text", "text": f"Zoom tile {k} (grid labels are full-image percent):"}, {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64(t)}}]
    text = ""
    with client.messages.stream(model=model, max_tokens=32000, messages=[{"role": "user", "content": content}]) as s:
        for ev in s.text_stream: text += ev
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try: data = json.loads(text)
    except json.JSONDecodeError:
        data = json.loads(text[text.index("{"): text.rindex("}") + 1])
    data["_extraction"] = {"model": model, "n_images": len(parts), "image_px": list(im.size), "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    return data


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--images", required=True); ap.add_argument("--only"); ap.add_argument("--model", default="claude-opus-4-6"); ap.add_argument("--force", action="store_true"); ap.add_argument("--shard", default="0/1", help="i/n to split the manifest across parallel runs")
    a = ap.parse_args(); os.makedirs(OUT, exist_ok=True)
    client = anthropic.Anthropic(); man = json.load(open(MAN))
    si, sn = map(int, a.shard.split("/"))
    for k, m in enumerate(man):
        if k % sn != si: continue
        if a.only and m["slug"] != a.only: continue
        if not m.get("image_file"): print("skip (no image)", m["slug"]); continue
        out = os.path.join(OUT, m["slug"] + ".json")
        if os.path.exists(out) and not a.force: continue
        t0 = time.time()
        for attempt in range(3):
            try:
                data = extract(client, a.model, m, os.path.join(a.images, m["image_file"])); break
            except Exception as e:
                print("  retry", m["slug"], type(e).__name__, str(e)[:120]); time.sleep(10 * (attempt + 1))
        else: continue
        json.dump({"source": {k: m[k] for k in ("slug", "url", "title", "page_date", "isw_map_id", "image_url", "image_file", "tags")}, **data}, open(out, "w"), indent=1, ensure_ascii=False)
        print(f"{m['slug'][:60]:60} anchors={len(data.get('anchors', []))} plots={len(data.get('plots', []))} persons={len(data.get('named_persons', []))} {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__": main()
