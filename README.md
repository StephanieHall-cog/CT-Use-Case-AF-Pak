# CT Use Case — AF/Pak jihadist network database

Open-source link-analysis database of Taliban / Haqqani Network / al-Qaeda (core + AQIS) / TTP / ISKP networks in
Afghanistan and Pakistan, built from the FDD Long War Journal podcast **Generation Jihad** (93 AfPak-focused episodes,
Mar 2020 – Oct 2026). Every record carries provenance back to an episode, a timestamp and a quote. Intended as the real-world
backbone for a terrorist-network tracking GUI; a separate `synthetic/` namespace holds fictional supplements for exercises.

## Layout
| Path | What |
|---|---|
| `raw/episodes_afpak.json` | episode metadata (RSS: title, date, audio URL, duration) |
| `raw/transcripts/<idx>_<slug>.txt` | Whisper transcripts with `[MMM:SS]` line markers |
| `raw/extractions/<idx>_<slug>.json` | per-episode Claude extraction (persons, orgs, places, events, relationships) — see `scripts/schema.json` |
| `raw/reports/` | per-batch analyst reports from the extraction sessions |
| `scripts/aliases.json` | curated canonical-name → alias table used for entity resolution |
| `scripts/build_db.py` | merges extractions → `db/afpak.sqlite` + `db/exports/*.csv` + `db/exports/graph.json` |
| `isw/` | ISW Map Room source (`isw_maps`): `manifest.json` (58 maps), `maps/<slug>.json` (vision-extracted legend/anchors/plots), `images/` (≤1600 px map JPEGs), gazetteer, `dead_pages.json` — see `docs/isw-maps.md` |
| `scripts/isw_scrape.py` / `isw_extract.py` / `build_isw_db.py` | collect Map Room pages+images (Chrome over CDP) → Claude-vision digitisation → georeference + load `map_*`/`place_coords` tables + GeoJSON |
| `synthetic/` | fictional supplement records (same schema, `dataset='synthetic'`, ids prefixed `S`) |
| `docs/` | GUI plan and network findings |

## Rebuild
```
python3 scripts/build_db.py                       # real data only
python3 scripts/build_db.py --synthetic synthetic/*.json
python3 scripts/build_db.py --no-isw               # podcast data only (skip ISW map tables)
```

## Data model (SQLite)
`episodes`, `entities` (person/organization/place, `dataset` real|synthetic), `aliases`, `memberships` (person→org per episode),
`mentions` (entity, episode, timestamp, quote), `relationships` (typed edge + detail + date + confidence + provenance),
`events` (+ `source` podcast|isw_maps, `map_plot_id`) + `event_actors`, `person_status_history`, `claims`, `sources_cited`;
ISW map layer: `map_sources`, `map_legend`, `map_anchors`, `map_plots` (lat/lon + `geo_method` + `geo_precision_km`), `map_plot_actors`, `map_text`; `place_coords` (gazetteer lat/lon for place entities).
Map exports: `db/exports/isw_plots.geojson`, `isw_maps.json`, `place_coords.json`.

## Provenance / caveats
- Transcripts are machine-generated (faster-whisper distil-large-v3); proper nouns were normalized by the extractor and by `aliases.json`,
  raw spellings are kept in `aliases`.
- Claims are the hosts' analysis, not adjudicated fact. `confidence` = `stated` (hosts said it) or `inferred` (extractor inference).
- ISW map plots are approximate positions read from raster maps by a vision model (`geo_precision_km`), reflect ISW/CTP assessments, and are linked to podcast entities only via unambiguous aliases; see `docs/isw-maps.md`.
- Synthetic records are fictional people only; never attach synthetic attributes to a real entity id.

## Documentation
- `docs/network-findings.md` — what the 93 episodes reveal (narrative + generated tables; regenerate the tables with `python3 scripts/report.py`).
- `docs/gui-plan.md` — how to turn this database into an analyst GUI (incl. the Events & Mapping tab).
- `docs/isw-maps.md` — ISW Map Room source: collection, extraction, georeferencing, tables, caveats, map inventory.
- `raw/reports/batch_XX_report.md` — per-batch extraction notes, including which episodes were hand-extracted.

## Current build
93 episodes · 1,632 entities (persons/organizations/places) · 3,525 aliases · 6,571 relationships · 1,394 dated podcast events · 2,720 mentions.
ISW map layer: 58 maps · 1,986 plot points (1,930 geocoded) · 601 printed names/text blocks · 95 geocoded podcast places (`place_coords`).
