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
| `synthetic/` | fictional supplement records (same schema, `dataset='synthetic'`, ids prefixed `S`) |
| `docs/` | GUI plan, network findings, National Security Archive source inventory (`docs/nsa-sources.md`) |

## Rebuild
```
python3 scripts/build_db.py                       # real data only
python3 scripts/build_db.py --synthetic synthetic/*.json
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

## Provenance / caveats
- Transcripts are machine-generated (faster-whisper distil-large-v3); proper nouns were normalized by the extractor and by `aliases.json`,
  raw spellings are kept in `aliases`.
- Claims are the hosts' analysis, not adjudicated fact. `confidence` = `stated` (hosts said it) or `inferred` (extractor inference).
- Synthetic records are fictional people only; never attach synthetic attributes to a real entity id.
- Document-sourced rows are the published authors' findings (CTC/Harmony primary-source research), not podcast commentary; they are
  the only part of the database that covers 1973–2001. The Brown & Rassler book *Fountainhead of Jihad* (2013) itself is not
  open-access and was **not** used; its open-access precursor report and two CTC Sentinel articles were (see `db/exports/documents.csv`).
- External profiles are attached to a podcast entity only through `scripts/profile_matches.json` (curated by hand; near-namesakes such as UN TAi.164
  Abdul Rauf Zakir vs. Abdul Qayyum Zakir are deliberately kept apart). UN/FBI spellings are added as aliases tagged with their source.

## Documentation
- `docs/network-findings.md` — what the 93 episodes reveal (narrative + generated tables; regenerate the tables with `python3 scripts/report.py`).
- `docs/gui-plan.md` — how to turn this database into an analyst GUI.
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
93 episodes + 449 open-access documents (446 National Security Archive declassified records + 3 CTC/Harmony papers) · 6,477 entities (persons/organizations/places; 4,677 appear only in documents) · 9,083 aliases · 32,013 relationships (6,571 podcast + 24,510 NSA documents + 861 CTC documents + 71 UN-stated) · 10,974 dated events (9,580 from documents) · 9,231 mentions · 194 official profiles (140 UN 1988 listings, 54 FBI Wanted items).
