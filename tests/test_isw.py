import glob, json, os, sqlite3, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f"{ROOT}/scripts")
from build_isw_db import Gazetteer, Georef, fold_place, hav

G = Gazetteer(extra=f"{ROOT}/isw/gazetteer_extra.tsv")


def test_gazetteer_resolves_common_places():
    assert G.lookup("Kabul", country="AF")[0]["fcode"] == "PPLC"
    assert G.lookup("Kunar", country="AF", kind="province")[0]["fcode"] == "ADM1"
    r = G.lookup("Miram Shah", country="PK")[0]
    assert abs(r["lat"] - 33.0) < 0.1 and abs(r["lon"] - 70.07) < 0.1
    assert G.lookup("FATA", country="PK")[0]["id"] < 0  # curated extra row
    assert fold_place("Khyber Agency") == "khyber"


def test_georef_affine_recovers_known_points():
    # synthetic linear map: x% -> lon 66..72, y% -> lat 36..30
    pts = [dict(x=x, y=y, lon=66 + x * 0.06, lat=36 - y * 0.06, w=1.0) for x, y in ((10, 10), (90, 10), (10, 90), (90, 90), (50, 50))]
    pts.append(dict(x=50, y=20, lon=71.5, lat=31.0, w=1.0))  # one badly mislabelled anchor
    g = Georef(pts)
    assert g.A is not None and len(g.used) == 5 and g.rms < 3
    lat, lon = g.to_ll(30, 40); assert abs(lat - 33.6) < 0.05 and abs(lon - 67.8) < 0.05


def test_extraction_files_are_well_formed():
    files = glob.glob(f"{ROOT}/isw/maps/*.json"); assert files
    man = {m["slug"] for m in json.load(open(f"{ROOT}/isw/manifest.json"))}
    for f in files:
        d = json.load(open(f))
        assert d["source"]["slug"] in man and d["source"]["url"].startswith("https://understandingwar.org/map/")
        for p in d.get("plots", []):
            assert 0 <= p["x_pct"] <= 100 and 0 <= p["y_pct"] <= 100 and p["legend_class"]


def test_build_with_isw_maps():
    subprocess.run([sys.executable, f"{ROOT}/scripts/build_db.py"], check=True, capture_output=True)
    con = sqlite3.connect(f"{ROOT}/db/afpak.sqlite"); q = lambda s: con.execute(s).fetchall()
    n_maps = q("select count(*) from map_sources")[0][0]; assert n_maps == len(glob.glob(f"{ROOT}/isw/maps/*.json"))
    # every plot is an event with isw_maps provenance and a back-link to its map + original URL
    assert q("select count(*) from map_plots p left join events e on e.id=p.event_id where e.id is null or e.source!='isw_maps' or e.map_plot_id!=p.id")[0][0] == 0
    assert q("select count(*) from map_sources where url is null or url=''")[0][0] == 0
    # podcast events untouched
    assert q("select count(*) from events where source='podcast' and episode_idx is null")[0][0] == 0
    # geocoded plots carry a method + precision and fall inside the wider region
    assert q("select count(*) from map_plots where lat is not null and (geo_method is null or geo_precision_km is null)")[0][0] == 0
    assert q("select count(*) from map_plots where lat is not null and not (lat between 20 and 45 and lon between 55 and 85)")[0][0] == 0
    # cross-links only point at real existing entities
    assert q("select count(*) from map_plot_actors a left join entities e on e.id=a.entity_id where a.entity_id is not null and e.id is null")[0][0] == 0
    assert q("select count(*) from map_plots p left join entities e on e.id=p.place_entity_id where p.place_entity_id is not null and e.id is null")[0][0] == 0
    assert q("select count(*) from place_coords pc left join entities e on e.id=pc.entity_id where e.id is null or e.kind!='place'")[0][0] == 0
    gj = json.load(open(f"{ROOT}/db/exports/isw_plots.geojson"))
    assert gj["type"] == "FeatureCollection" and len(gj["features"]) == q("select count(*) from map_plots where lat is not null")[0][0]
    assert all(f["properties"]["map_url"] and f["properties"]["source"] == "isw_maps" for f in gj["features"])
