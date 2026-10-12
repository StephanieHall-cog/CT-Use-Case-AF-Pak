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
| `scripts/aliases.json` | curated canonical-name → alias table used for entity resolution |
| `scripts/build_db.py` | merges episode + document extractions → `db/afpak.sqlite` + `db/exports/*.csv` + `db/exports/graph.json` |
| `scripts/extract_doc.py` | two-pass Claude extraction for documents (entities pass, then an exhaustive relationships/events pass) |
| `scripts/review_docs.py` | QA listing for document extractions (new vs. merged persons, non-actor names, dangling edge endpoints) |
| `synthetic/` | fictional supplement records (same schema, `dataset='synthetic'`, ids prefixed `S`) |
| `docs/` | GUI plan and network findings |

## Rebuild
```
python3 scripts/build_db.py                       # real data only
python3 scripts/build_db.py --synthetic synthetic/*.json
```

## Data model (SQLite)
`episodes`, `documents`, `entities` (person/organization/place, `dataset` real|synthetic, `n_episodes`, `n_documents`), `aliases`,
`memberships` (person→org per episode/document), `mentions` (entity, episode or doc_id, timestamp/page, quote),
`relationships` (typed edge + detail + date + confidence + provenance: `episode_idx` **or** `doc_id`, `timestamp`, `quote`),
`events` + `event_actors`, `person_status_history`, `claims`, `sources_cited`. Exactly one of `episode_idx` / `doc_id` is set on every real row.

## Provenance / caveats
- Transcripts are machine-generated (faster-whisper distil-large-v3); proper nouns were normalized by the extractor and by `aliases.json`,
  raw spellings are kept in `aliases`.
- Claims are the hosts' analysis, not adjudicated fact. `confidence` = `stated` (hosts said it) or `inferred` (extractor inference).
- Synthetic records are fictional people only; never attach synthetic attributes to a real entity id.
- Document-sourced rows are the published authors' findings (CTC/Harmony primary-source research), not podcast commentary; they are
  the only part of the database that covers 1973–2001. The Brown & Rassler book *Fountainhead of Jihad* (2013) itself is not
  open-access and was **not** used; its open-access precursor report and two CTC Sentinel articles were (see `db/exports/documents.csv`).

## Documentation
- `docs/network-findings.md` — what the 93 episodes reveal (narrative + generated tables; regenerate the tables with `python3 scripts/report.py`).
- `docs/gui-plan.md` — how to turn this database into an analyst GUI.
- `raw/reports/batch_XX_report.md` — per-batch extraction notes, including which episodes were hand-extracted.

## Current build
93 episodes + 3 documents · 1,760 entities (persons/organizations/places) · 3,732 aliases · 7,432 relationships (6,571 podcast / 861 document) · 1,657 dated events (263 document) · 2,939 mentions.
