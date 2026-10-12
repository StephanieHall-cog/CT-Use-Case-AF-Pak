import json, os, sqlite3, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f"{ROOT}/scripts")
from normalize import Resolver, fold
from build_db import eid, PRESENTERS

R = Resolver()

def test_alias_normalization():
    assert R.resolve("persons", "Siraj Hakani") == "Sirajuddin Haqqani"
    assert R.resolve("persons", "Haibatullah Akhunzada") == "Hibatullah Akhundzada"
    assert R.resolve("persons", "Abu Mohammad al-Julani") == "Abu Mohammad al-Jolani"
    assert R.resolve_any("Taliban")[0] == "organizations"
    assert R.resolve_any("Kabul")[0] == "places"

def test_unknown_name_passthrough():
    assert R.resolve("persons", "Totally Unknown Person") == "Totally Unknown Person"

def test_presenters_excluded():
    assert fold("Bill Roggio") in PRESENTERS and fold("Thomas Joscelyn") in PRESENTERS

def test_stable_ids_and_dataset_separation():
    a = eid("persons", "Sirajuddin Haqqani"); b = eid("persons", "sirajuddin  haqqani")
    assert a == b and a.startswith("P-")
    s = eid("persons", "Sirajuddin Haqqani", "synthetic")
    assert s != a and s.startswith("SP-")

def _build(extra):
    subprocess.run([sys.executable, f"{ROOT}/scripts/build_db.py", *extra], check=True, capture_output=True)
    return sqlite3.connect(f"{ROOT}/db/afpak.sqlite")

def test_build_real_and_synthetic():
    con = _build(["--synthetic", f"{ROOT}/synthetic/sample_scenario.json"])
    q = lambda s: con.execute(s).fetchall()
    assert q("select count(*) from entities where kind='person' and name='Bill Roggio'")[0][0] == 0
    assert q("select count(*) from entities where dataset='synthetic'")[0][0] >= 2
    assert all(i.startswith("S") for (i,) in q("select id from entities where dataset='synthetic'"))
    # synthetic edge to a real org is allowed but must be flagged synthetic
    rows = q("select r.dataset, t.dataset from relationships r join entities t on t.id=r.target_id join entities s on s.id=r.source_id where s.name='Zubair Kohistani' and t.name='al-Qaeda'")
    assert rows and rows[0] == ("synthetic", "real")
    # every real relationship has provenance
    assert q("select count(*) from relationships where dataset='real' and (episode_idx is null or quote is null or quote='')")[0][0] == 0
    g = json.load(open(f"{ROOT}/db/exports/graph.json"))
    ids = {n["id"] for n in g["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in g["edges"])
    assert any(n.get("dataset") == "synthetic" for n in g["nodes"])
    _build([])  # leave the repo DB real-only
