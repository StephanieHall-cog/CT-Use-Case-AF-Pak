"""Collect ISW Map Room pages + images for the AfPak map set (source `isw_maps`).

ISW sits behind a Cloudflare browser check, so this script drives an already-open Chrome over CDP instead of using
plain HTTP: start Chrome with `google-chrome --user-data-dir=/tmp/chrome-isw --remote-debugging-port=9333`, open
https://understandingwar.org/analysis/map-room/ and pass the "verify you are human" check once, then run

    python3 scripts/isw_scrape.py --out /tmp/isw          # index -> pages -> images
    python3 scripts/isw_extract.py --images /tmp/isw/img  # Claude-vision digitisation -> isw/maps/*.json
    python3 scripts/build_isw_db.py                        # geocode + tables + GeoJSON

Writes isw/manifest.json (one record per surviving map page) and <out>/img/<slug>.<ext> full-resolution images.
Legacy 2009–2012 interactive maps that now 302 to /analysis/map-room/ are recorded under "dead_pages".
"""
import argparse, html, json, os, re, time
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
BASE = "https://understandingwar.org/analysis/map-room/?"
QUERIES = ["_search_research=afghanistan&_map_type=static-map%2Cinteractive-map",
           "_search_research=pakistan&_map_type=static-map%2Cinteractive-map",
           "_search_research=taliban", "_search_research=haqqani", "_search_research=ttp", "_search_research=waziristan",
           "_map_series=afghanistan-pakistan-militant-groups", "_map_series=afghanistan-surge", "_map_series=campaign-for-helmand",
           "_map_series=campaign-for-kandahar", "_map_series=control-of-terrain-in-afghanistan", "_map_series=counter-isis-operations-afghanistan",
           "_map_series=haqqani-network", "_product_line_filter=afghanistan-pakistan-salafi-jihadi-update", "_product_line_filter=afghanistan-surge-and-drawdown",
           "_product_line_filter=afghanistan-the-taliban-and-isis", "_product_line_filter=afghanistan-us-withdrawal-and-aftermath", "_product_line_filter=iran-in-afghanistan",
           "_product_line_filter=militant-groups-in-afhganistan-and-pakistan"]
# full-text search also returns other theatres; drop them by slug
EXCL = re.compile(r"syria|zaporizhia|homs|aleppo|manbij|rif-dimashq|dobropillya|novopavlivka|orikhiv|hudaydah|taiz|esfahan|fordow|houthi|red-sea|russian|ukraine|lebanon|kurdistan|israel|june-29-2025|saudi|borova")


def settle(page):
    for _ in range(20):
        if "Just a moment" not in page.title(): break
        time.sleep(2)
    page.wait_for_timeout(2000)


def index(page):
    out = {}
    for q in QUERIES:
        for pg in range(1, 20):
            page.goto(BASE + q + (f"&_paged={pg}" if pg > 1 else ""), wait_until="domcontentloaded", timeout=60000); settle(page)
            for h in page.eval_on_selector_all("a[href*='/map/']", "els => els.map(e => e.href)"):
                h = h.split("#")[0].split("?")[0]; out.setdefault(h, []).append(q)
            pager = page.eval_on_selector_all(".facetwp-page", "els => els.map(e => e.innerText.trim())")
            if not pager or str(pg + 1) not in pager: break
    return out


def page_record(page, ctx, u, outdir):
    slug = u.rstrip("/").split("/")[-1]
    page.goto(u, wait_until="domcontentloaded", timeout=60000); settle(page)
    if page.url.rstrip("/").endswith("/analysis/map-room"): return None
    h = page.content(); open(f"{outdir}/pages/{slug}.html", "w").write(h)
    g = lambda p: (re.search(p, h, re.S) or [None, None])[1]
    title = re.sub("<[^>]+>", "", html.unescape(g(r"<h1[^>]*>\s*(.*?)\s*</h1>") or "")).strip()
    date = g(r"<h6[^>]*map-date[^>]*>\s*([^<]+?)\s*</h6>") or (g(r'"datePublished":"([^"]+)"') or "")[:10] or None
    tags = sorted({html.unescape(re.sub("<[^>]+>", "", t)).strip() for t in re.findall(r'class="[^"]*(?:tag|term|category)[^"]*"[^>]*>(.*?)</', h, re.S)} - {""})
    body = g(r'<div class="dynamic-entry-content">(.*?)</main>') or ""
    body = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<(style|script).*?</\1>", "", body, flags=re.S)))).strip()
    body = re.sub(r"\b(Email|LinkedIn|X|Facebook|Print|Share|Copy link)\b", "", body).strip()
    imgs = [(s, w) for s, w in page.eval_on_selector_all("main img", "els => els.map(i => [i.src, i.naturalWidth])") if s and "uploads" in s and not s.endswith(".svg")]
    imgurl = g(r'conflict-map-block">.*?<img[^>]*src="([^"]+)"') or (max(imgs, key=lambda x: x[1])[0] if imgs else None)
    image_file = None
    if imgurl:
        orig = re.sub(r"-\d{3,4}x\d{3,4}(\.\w+)$", r"\1", imgurl)
        for cand in dict.fromkeys([orig, imgurl]):
            r = ctx.request.get(cand, timeout=60000)
            if r.ok and len(r.body()) > 5000:
                image_file = slug + os.path.splitext(cand)[1].lower(); open(f"{outdir}/img/{image_file}", "wb").write(r.body()); break
            time.sleep(3)
    return dict(slug=slug, url=u, title=title, page_date=date, isw_map_id=g(r'data-map-id="(\d+)"'), image_url=imgurl, image_file=image_file, tags=[t for t in tags if len(t) < 60], page_text=body[:3000] if len(body) < 1400 else "")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="/tmp/isw"); ap.add_argument("--cdp", default="http://localhost:9333"); a = ap.parse_args()
    for d in ("pages", "img"): os.makedirs(f"{a.out}/{d}", exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.connect_over_cdp(a.cdp).contexts[0]; page = ctx.pages[0]
        idx = index(page); json.dump(idx, open(f"{a.out}/map_index.json", "w"), indent=1)
        urls = [u for u in sorted(idx) if not EXCL.search(u)]; print(len(idx), "indexed,", len(urls), "AfPak")
        man, dead = [], []
        for u in urls:
            try:
                rec = page_record(page, ctx, u, a.out)
            except Exception as e:
                print("ERR", u, e); continue
            (man.append(rec) if rec else dead.append(u)); print(u.split("/map/")[1], "ok" if rec else "DEAD", flush=True); time.sleep(2)
    json.dump(man, open(os.path.join(ROOT, "isw", "manifest.json"), "w"), indent=1, ensure_ascii=False)
    json.dump({"dead_pages": dead}, open(os.path.join(ROOT, "isw", "dead_pages.json"), "w"), indent=1)


if __name__ == "__main__": main()
