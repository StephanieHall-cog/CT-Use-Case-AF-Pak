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
| `raw/sanctions/un_consolidated_snapshot.xml` | snapshot of the UN Security Council consolidated sanctions XML (`scsanctions.un.org`); `scripts/un_sanctions.py` keeps the 1988 (Taliban) list → `raw/sanctions/un_1988.json` |
| `raw/sanctions/un_1988_narratives.json` | narrative summaries of reasons for listing, scraped from `main.un.org/securitycouncil/…/1988/materials/summaries` (incl. the Haqqani Network entity page) |
| `raw/sanctions/fbi_wanted_snapshot.json` | FBI Wanted API snapshot of the 54 items on `fbi.gov/wanted/terrorism` (Most Wanted Terrorists, Seeking Information – Terrorism, Domestic Terrorism); `scripts/fbi_wanted.py` → `raw/sanctions/fbi_wanted.json` (`--fetch` refreshes) |
| `scripts/aliases.json` | curated canonical-name → alias table used for entity resolution |
| `scripts/profile_matches.json` | hand-curated identity links from UN / FBI profiles to podcast-derived people (unlisted profiles become their own entities) |
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
`events` + `event_actors`, `person_status_history`, `claims`, `sources_cited`,
`profiles` (official biodata per entity: UN 1988 listing — aliases, original-script name, DOB/POB, addresses, passports, designation, listed-on,
INTERPOL link, comments, narrative summary; FBI Wanted — aliases, DOBs used, POB, nationality, languages, physical description, reward, caution/details text, photo URL).
`entities.sources` lists which of `podcast`, `un_1988`, `fbi_wanted` contributed to a record; `relationships.source` distinguishes podcast-quoted
edges from UN-stated family/command links (`son_of`, `brother_of`, `uncle_of`, `leader_of`, `founder_of`, `deputy_of`, `subordinate_of`, …) parsed from
the UN COMMENTS field, each carrying the UN sentence as its `quote`.

## Provenance / caveats
- Transcripts are machine-generated (faster-whisper distil-large-v3); proper nouns were normalized by the extractor and by `aliases.json`,
  raw spellings are kept in `aliases`.
- Claims are the hosts' analysis, not adjudicated fact. `confidence` = `stated` (hosts said it) or `inferred` (extractor inference).
- Synthetic records are fictional people only; never attach synthetic attributes to a real entity id.
- External profiles are attached to a podcast entity only through `scripts/profile_matches.json` (curated by hand; near-namesakes such as UN TAi.164
  Abdul Rauf Zakir vs. Abdul Qayyum Zakir are deliberately kept apart). UN/FBI spellings are added as aliases tagged with their source.

## Documentation
- `docs/network-findings.md` — what the 93 episodes reveal (narrative + generated tables; regenerate the tables with `python3 scripts/report.py`).
- `docs/gui-plan.md` — how to turn this database into an analyst GUI.
- `raw/reports/batch_XX_report.md` — per-batch extraction notes, including which episodes were hand-extracted.

## Refresh external sources
```
curl -sL https://scsanctions.un.org/resources/xml/en/consolidated.xml -o raw/sanctions/un_consolidated_snapshot.xml
python3 scripts/un_sanctions.py          # → raw/sanctions/un_1988.json (merges raw/sanctions/un_1988_narratives.json if present)
python3 scripts/fbi_wanted.py --fetch    # → raw/sanctions/fbi_wanted.json
python3 scripts/build_db.py
```

## Current build
93 episodes · 1,803 entities (persons/organizations/places) · 4,087 aliases · 6,642 relationships (6,571 podcast + 71 UN-stated) · 1,394 dated events · 2,720 mentions · 194 official profiles (140 UN 1988 listings, 54 FBI Wanted – Terrorism items; 22 attached to podcast-derived entities).
