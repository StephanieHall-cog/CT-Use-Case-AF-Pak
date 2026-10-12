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
    # every real relationship has provenance: a podcast episode, an open-source document, or an official list
    assert q("select count(*) from relationships where dataset='real' and source='podcast' and episode_idx is null")[0][0] == 0
    assert q("select count(*) from relationships where dataset='real' and source='document' and doc_id is null")[0][0] == 0
    assert q("select count(*) from relationships r where r.doc_id is not null and r.doc_id not in (select doc_id from documents)")[0][0] == 0
    # every real podcast/document edge is either quoted or explicitly derived from a structured field
    assert q("select count(*) from relationships where dataset='real' and source in ('podcast','document') and (quote is null or quote='') and (detail is null or detail not like 'derived:%')")[0][0] == 0
    # every external (sanctions/wanted) edge carries the sentence it was parsed from and its list reference
    assert q("select count(*) from relationships where source not in ('podcast','document') and (quote is null or quote='' or detail not like 'UN 1988 List %')")[0][0] == 0
    g = json.load(open(f"{ROOT}/db/exports/graph.json"))
    ids = {n["id"] for n in g["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in g["edges"])
    assert any(n.get("dataset") == "synthetic" for n in g["nodes"])
    _build([])  # leave the repo DB real-only


def test_document_sources():
    con = sqlite3.connect(f"{ROOT}/db/afpak.sqlite")
    q = lambda s: con.execute(s).fetchall()
    assert q("select count(*) from documents where doc_id='ctc-2011-haqqani-nexus'")[0][0] == 1
    # document-sourced edges carry a page/paragraph reference and a quote unless explicitly derived
    assert q("select count(*) from relationships where doc_id is not null and (quote is null or quote='') and (detail is null or detail not like 'derived:%')")[0][0] == 0
    assert q("select count(*) from relationships where doc_id is not null and quote<>'' and (timestamp is null or timestamp='')")[0][0] == 0
    # document authors are not entities
    assert q("select count(*) from entities where kind='person' and name in ('Don Rassler','Vahid Brown')")[0][0] == 0
    # the CTC report and the podcast corpus overlap on the Haqqani core
    assert q("select count(*) from entities where name='Jalaluddin Haqqani' and n_episodes>0 and n_documents>0")[0][0] == 1


def test_external_profiles_attach_without_overmerging():
    con = sqlite3.connect(f"{ROOT}/db/afpak.sqlite")
    q = lambda s, *a: con.execute(s, a).fetchall()
    assert q("select count(*) from profiles where source='un_1988'")[0][0] >= 100
    assert q("select count(*) from profiles where source='fbi_wanted'")[0][0] >= 40
    # curated identity match: Sirajuddin carries podcast + UN + FBI biodata on one entity
    assert q("select sources from entities where name='Sirajuddin Haqqani'")[0][0] == "document,fbi_wanted,podcast,un_1988"
    assert q("select count(*) from profiles p join entities e on e.id=p.entity_id where e.name='Sirajuddin Haqqani'")[0][0] == 2
    # UN family link with its sentence as evidence
    assert q("""select r.quote from relationships r join entities s on s.id=r.source_id join entities t on t.id=r.target_id
                where s.name='Sirajuddin Haqqani' and t.name='Jalaluddin Haqqani' and r.type='son_of' and r.source='un_1988'""")
    # near-namesakes stay separate (UN TAi.164 Abdul Rauf Zakir vs podcast Abdul Qayyum Zakir)
    assert q("select sources from entities where name='Abdul Rauf Zakir'")[0][0] == "un_1988"
    assert q("select sources from entities where name='Abdul Qayyum Zakir'")[0][0] == "podcast"
    # UN spellings are kept as aliases tagged with their source
    assert q("select count(*) from aliases a join entities e on e.id=a.entity_id where e.name='Sirajuddin Haqqani' and a.source='un_1988'")[0][0] >= 3
    # FBI biodata fields present
    assert q("select physical from profiles where source='fbi_wanted' and name='SIRAJUDDIN HAQQANI'")[0][0].find("height") >= 0
    g = json.load(open(f"{ROOT}/db/exports/graph.json"))
    n = next(n for n in g["nodes"] if n["name"] == "Sirajuddin Haqqani")
    assert "un_1988:TAi.144" in n["profiles"] and set(n["sources"]) == {"podcast", "document", "un_1988", "fbi_wanted"}
