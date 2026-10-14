# CT Use Case — AF/Pak jihadist network database

Open-source link-analysis database of Taliban / Haqqani Network / al-Qaeda (core + AQIS) / TTP / ISKP networks in
Afghanistan and Pakistan, built from the FDD Long War Journal podcast **Generation Jihad** (93 AfPak-focused episodes,
Mar 2020 – Oct 2026) plus open-access research documents (CTC West Point Harmony report and CTC Sentinel articles by
Don Rassler and Vahid Brown, covering the Haqqani network 1973–2011). Every record carries provenance back to an episode + timestamp + quote,
or to a document + page/paragraph + quote. Intended as the real-world
backbone for a terrorist-network tracking GUI; a separate `synthetic/` namespace holds fictional supplements for exercises.

## Layout
| Path | What |
|---|---|
| `raw/episodes_afpak.json` | episode metadata (RSS: title, date, audio URL, duration) |
| `raw/transcripts/<idx>_<slug>.txt` | Whisper transcripts with `[MMM:SS]` line markers |
| `raw/extractions/<idx>_<slug>.json` | per-episode Claude extraction (persons, orgs, places, events, relationships) — see `scripts/schema.json` |
| `raw/reports/` | per-batch analyst reports from the extraction sessions |
| `raw/documents/<doc_id>.txt` | open-access documents: JSON metadata header line + text with `[PDF p.N]` / `[para N]` markers |
| `raw/documents/extractions/<doc_id>.json` | per-document Claude extraction (same schema, top-level `document` instead of `episode`, `timestamp` = `p.N` / `para N`) |
| `raw/sanctions/un_consolidated_snapshot.xml` | snapshot of the UN Security Council consolidated sanctions XML (`scsanctions.un.org`); `scripts/un_sanctions.py` keeps the 1988 (Taliban) list → `raw/sanctions/un_1988.json` |
| `raw/sanctions/un_1988_narratives.json` | narrative summaries of reasons for listing, scraped from `main.un.org/securitycouncil/…/1988/materials/summaries` (incl. the Haqqani Network entity page) |
| `raw/sanctions/fbi_wanted_snapshot.json` | FBI Wanted API snapshot of the 54 items on `fbi.gov/wanted/terrorism` (Most Wanted Terrorists, Seeking Information – Terrorism, Domestic Terrorism); `scripts/fbi_wanted.py` → `raw/sanctions/fbi_wanted.json` (`--fetch` refreshes) |
| `scripts/aliases.json` | curated canonical-name → alias table used for entity resolution |
| `scripts/profile_matches.json` | hand-curated identity links from UN / FBI profiles to podcast-derived people (unlisted profiles become their own entities) |
| `scripts/build_db.py` | merges episode + document extractions → `db/afpak.sqlite` + `db/exports/*.csv` + `db/exports/graph.json` |
| `scripts/extract_doc.py` | two-pass Claude extraction for documents (entities pass, then an exhaustive relationships/events pass) |
| `scripts/extract_doc_batch.py` | same two passes via the Anthropic Message Batches API for bulk document loads (used for the 446 National Security Archive documents) |
| `scripts/review_docs.py` | QA listing for document extractions (new vs. merged persons, non-actor names, dangling edge endpoints) |
| `isw/` | ISW Map Room source (`isw_maps`): `manifest.json` (58 maps), `maps/<slug>.json` (vision-extracted legend/anchors/plots), `images/` (≤1600 px map JPEGs), gazetteer, `dead_pages.json` — see `docs/isw-maps.md` |
| `scripts/isw_scrape.py` / `isw_extract.py` / `build_isw_db.py` | collect Map Room pages+images (Chrome over CDP) → Claude-vision digitisation → georeference + load `map_*`/`place_coords` tables + GeoJSON |
| `synthetic/` | fictional supplement records (same schema, `dataset='synthetic'`, ids prefixed `S`); `targets_demo.json` = target-tracking demo (14 targets, selectors, correlations, location hits, attacks) from `scripts/synthetic_targets.py`; `sites_reference.json` = public USG / other-government / international sites with approximate coordinates |
| `docs/` | GUI plan, network findings, National Security Archive source inventory (`docs/nsa-sources.md`) |

## Rebuild
```
python3 scripts/build_db.py                       # real data only
python3 scripts/build_db.py --synthetic synthetic/*.json
python3 scripts/build_db.py --no-isw               # podcast data only (skip ISW map tables)
```

## Data model (SQLite)
`episodes`, `documents`, `entities` (person/organization/place, `dataset` real|synthetic, `n_episodes`, `n_documents`, `sources`), `aliases`,
`memberships` (person→org per episode/document), `mentions` (entity, episode or doc_id, timestamp/page, quote),
`relationships` (typed edge + detail + date + confidence + provenance: `episode_idx` **or** `doc_id`, `timestamp`, `quote`, `source`),
`events` + `event_actors`, `person_status_history`, `claims`, `sources_cited`,
`profiles` (official biodata per entity: UN 1988 listing — aliases, original-script name, DOB/POB, addresses, passports, designation, listed-on,
INTERPOL link, comments, narrative summary; FBI Wanted — aliases, DOBs used, POB, nationality, languages, physical description, reward, caution/details text, photo URL).
UN-stated family/command links (`son_of`, `brother_of`, `uncle_of`, `leader_of`, `founder_of`, `deputy_of`, `subordinate_of`, …) are parsed from
the UN COMMENTS field, each carrying the UN sentence as its `quote`.
`entities.sources` lists which of `podcast`, `document`, `un_1988`, `fbi_wanted` contributed to a record; `relationships.source` is `podcast`, `document` (see `doc_id`) or `un_1988`.
`events` additionally carry `source` (podcast|document|isw_maps) and `map_plot_id`.
ISW map layer: `map_sources`, `map_legend`, `map_anchors`, `map_plots` (lat/lon + `geo_method` + `geo_precision_km`), `map_plot_actors`, `map_text`; `place_coords` (gazetteer lat/lon for place entities).
Map exports: `db/exports/isw_plots.geojson`, `isw_maps.json`, `place_coords.json`.

## Provenance / caveats
- Transcripts are machine-generated (faster-whisper distil-large-v3); proper nouns were normalized by the extractor and by `aliases.json`,
  raw spellings are kept in `aliases`.
- Claims are the hosts' analysis, not adjudicated fact. `confidence` = `stated` (hosts said it) or `inferred` (extractor inference).
- ISW map plots are approximate positions read from raster maps by a vision model (`geo_precision_km`), reflect ISW/CTP assessments, and are linked to podcast entities only via unambiguous aliases; see `docs/isw-maps.md`.
- Synthetic records are fictional people only; never attach synthetic attributes to a real entity id.
- Document-sourced rows are the published authors' findings (CTC/Harmony primary-source research), not podcast commentary; they are
  the only part of the database that covers 1973–2001. The Brown & Rassler book *Fountainhead of Jihad* (2013) itself is not
  open-access and was **not** used; its open-access precursor report and two CTC Sentinel articles were (see `db/exports/documents.csv`).
- External profiles are attached to a podcast entity only through `scripts/profile_matches.json` (curated by hand; near-namesakes such as UN TAi.164
  Abdul Rauf Zakir vs. Abdul Qayyum Zakir are deliberately kept apart). UN/FBI spellings are added as aliases tagged with their source.

## GUI (gui/) — AfPak Target Tracker

Demo analyst GUI over the database: layered event map (attacks by group, USG / foreign-government / intl-org / border / soft-target sites, target last-known-location + trails, time slider, citation link on every point), target "baseball cards" (fixed fillable field set — every value carries a Citation + source URL), phone/IMSI/IMEI/push-token pairings, selector correlations, per-card geolocation map with CDR/SS7/ISR/travel/HUMINT/OSINT dropdown, inference proposals with Accept/Reject, link chart, memos, users/audit.

```bash
python3 scripts/build_db.py --synthetic synthetic/targets_demo.json synthetic/sample_scenario.json --db db/afpak_demo.sqlite
cd gui && npm install && ADMIN_PASSWORD=change-me node server.mjs   # http://localhost:3300, login admin
npm test
```

The AfPak DB is opened read-only; analyst edits, proposals, memos, users and the audit log live in `gui/data/app.db` (gitignored). Real people never receive selectors or location hits unless an analyst enters sourced ones; all synthetic material is on `SP-…` ids and is banner-labelled. Requirements log: `gui/NOTES.md`.

## Documentation
- `docs/network-findings.md` — what the 93 episodes reveal (narrative + generated tables; regenerate the tables with `python3 scripts/report.py`).
- `docs/gui-plan.md` — how to turn this database into an analyst GUI (incl. the Events & Mapping tab).
- `docs/isw-maps.md` — ISW Map Room source: collection, extraction, georeferencing, tables, caveats, map inventory.
- `docs/nsa-sources.md` — National Security Archive briefing books surveyed, the 446 declassified documents ingested (with source URLs, dates, originators, extraction counts), maps/graphics inventory and caveats.
- `raw/reports/batch_XX_report.md` — per-batch extraction notes, including which episodes were hand-extracted.

## Refresh external sources
```
curl -sL https://scsanctions.un.org/resources/xml/en/consolidated.xml -o raw/sanctions/un_consolidated_snapshot.xml
python3 scripts/un_sanctions.py          # → raw/sanctions/un_1988.json (merges raw/sanctions/un_1988_narratives.json if present)
python3 scripts/fbi_wanted.py --fetch    # → raw/sanctions/fbi_wanted.json
python3 scripts/build_db.py
```
To add more documents (e.g. further National Security Archive briefing books): write `raw/documents/<doc_id>.txt` (JSON header line + `[PDF p.N]` text; OCR scanned PDFs with Tesseract), then
```
python3 scripts/extract_doc_batch.py raw/documents/<doc_id>.txt ...   # or extract_doc.py for one or two files
python3 scripts/review_docs.py <doc_id> ...                             # add transliteration variants to scripts/aliases.json
python3 scripts/build_db.py
```

## Current build
93 episodes + 449 open-access documents (446 National Security Archive declassified records + 3 CTC/Harmony papers) · 6,476 entities (persons/organizations/places; 4,676 appear only in documents) · 9,084 aliases · 32,013 relationships (6,571 podcast + 24,510 NSA documents + 861 CTC documents + 71 UN-stated) · 12,960 dated events (9,580 from documents) · 9,231 mentions · 194 official profiles (140 UN 1988 listings, 54 FBI Wanted items).
ISW map layer: 58 maps · 1,986 plot points (1,930 geocoded) · 601 printed names/text blocks · 100 geocoded podcast/document places (`place_coords`).
