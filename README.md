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
| `synthetic/` | fictional supplement records (same schema, `dataset='synthetic'`, ids prefixed `S`) |
| `docs/` | GUI plan and network findings |

## Rebuild
```
python3 scripts/build_db.py                       # real data only
python3 scripts/build_db.py --synthetic synthetic/*.json
```

## Data model (SQLite)
`episodes`, `entities` (person/organization/place, `dataset` real|synthetic), `aliases`, `memberships` (person→org per episode),
`mentions` (entity, episode, timestamp, quote), `relationships` (typed edge + detail + date + confidence + provenance),
`events` + `event_actors`, `person_status_history`, `claims`, `sources_cited`.

## Provenance / caveats
- Transcripts are machine-generated (faster-whisper distil-large-v3); proper nouns were normalized by the extractor and by `aliases.json`,
  raw spellings are kept in `aliases`.
- Claims are the hosts' analysis, not adjudicated fact. `confidence` = `stated` (hosts said it) or `inferred` (extractor inference).
- Synthetic records are fictional people only; never attach synthetic attributes to a real entity id.

## Documentation
- `docs/network-findings.md` — what the 93 episodes reveal (narrative + generated tables; regenerate the tables with `python3 scripts/report.py`).
- `docs/gui-plan.md` — how to turn this database into an analyst GUI.
- `raw/reports/batch_XX_report.md` — per-batch extraction notes, including which episodes were hand-extracted.

## Current build
93 episodes · 1,635 entities (persons/organizations/places) · 3,536 aliases · 6,571 relationships · 1,394 dated events · 2,720 mentions.
