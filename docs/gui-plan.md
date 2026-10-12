# From database to analyst GUI — implementation plan

This plan is derived from what the merged Generation Jihad corpus actually contains
(see `docs/network-findings.md` for the numbers). It is written so a frontend team can
start without re-reading the extraction pipeline.

## 1. What the data supports (and what it does not)

| Data we have | Where | GUI capability it enables |
|---|---|---|
| Persons / organizations / places with stable IDs, roles, nationality, status | `entities` | Entity pages, type-filtered search, status badges (alive / killed / captured / unknown) |
| Alias table incl. raw ASR spellings | `aliases` | Search-by-any-spelling; "also known as" panel; alias-review queue |
| Typed, directed relationships with episode + `[MMM:SS]` + verbatim quote | `relationships` | Link chart with click-to-evidence; edge filters by type |
| `confidence` = stated \| inferred on every edge | `relationships.confidence` | Solid vs dashed edges; "stated only" toggle |
| `detail` prefixed `derived:` for edges inferred from structured fields (org parent/allies/rivals, family lists) | `relationships.detail` | Third edge style; hide-derived toggle |
| Dated events with precision + place + actors | `events`, `event_actors` | Timeline, map pins, event-centric queries |
| Memberships per episode | `memberships` | Org roster; affiliation-over-time strip |
| Status per person per episode (publish date) | `person_status_history` | "Status as of <date>" slider; contradiction flags |
| Mentions with role-in-episode and locations | `mentions` | Entity → episode list; "where was X placed" |
| `dataset` real \| synthetic, `S`-prefixed synthetic IDs | every table | Global real/synthetic filter; mandatory badge |
| Episode metadata + transcript path | `episodes` | Source viewer: jump to timestamp in transcript |

Not in the data (do not promise it in the GUI): geocoordinates (places are names + parent
place only), imagery, identifiers beyond names, independently adjudicated facts. Every
assertion is "the podcast said" — the UI must say so.

## 2. Edge semantics to encode in the renderer

Relationship types and how to draw them (counts from the current build):

- `allied_with`, `rival_of` — undirected for display; very dense (≈60% of edges, mostly org↔org). Default **off** at the org level above 1st degree, or the chart is a hairball.
- `member_of`, `leads`, `deputy_of`, `reports_to`, `succeeded` — directed hierarchy edges; render as a tree inside an org page.
- `family`, `married_into` — directed; `detail` carries the kin term ("X is father of Y"). Family panel on person pages.
- `sheltered_by`, `hosted_by`, `funded_by`, `trained_by` — directed support edges; the core of the CT use case. Highlight by default.
- `killed`, `captured`, `negotiated_with`, `met_with` — event-like edges; also surfaced on the timeline via `date`.
- `located_in` — person/org → place; feeds the map.
- `other` — keep but render grey; show `detail`.

Direction convention: `source` acts on / belongs to `target` (A `sheltered_by` B means B shelters A). Hover text should spell this out using `detail`.

## 3. Screens

1. **Search / landing** — one box searching `entities.name` + `aliases.alias`; result rows show kind, dataset badge, n_episodes, status.
2. **Entity page** (person / org / place) — header (name, aliases, role, status with "as of" date), tabs: Relationships (table + mini-graph), Events, Episodes (mentions with timestamp links), Family (persons), Roster (orgs), Located-here (places).
3. **Link chart** — Cytoscape.js or Sigma.js over `db/exports/graph.json`. Controls: degree (1/2), edge-type checkboxes, stated/inferred/derived toggles, dataset filter, time window (by episode publish date), min-episodes slider for nodes. Click edge → evidence drawer (quote, episode title, timestamp, "open transcript").
4. **Timeline** — `events` + dated relationships; swimlanes by organization; precision shown (year/month/day).
5. **Map** — places → requires a one-time geocoding step (name + parent_place → lat/lon) stored in a new `place_coords` table; until then, a hierarchical place tree.
6. **Episode viewer** — transcript with `[MMM:SS]` anchors; every extracted entity/relationship from that episode listed alongside; this is the provenance screen.
7. **Review queue** — (a) alias candidates (near-duplicate names across kinds / high string similarity), (b) contradictions (status flips, reversed family edges, same pair with opposite edge types), (c) low-density episodes (relationships per 10 min below threshold, flagged manual extraction). Analyst decisions write to `scripts/aliases.json` / an `overrides` table and trigger rebuild.
8. **Synthetic scenario manager** — load/unload `synthetic/*.json`; everything synthetic is badged and filterable; synthetic persons can never resolve to a real ID (enforced by `eid()` namespace).

## 4. Architecture

- **Backend**: FastAPI over the SQLite file (read-only for the real dataset; `overrides` + synthetic tables writable). Endpoints: `/search`, `/entity/{id}`, `/entity/{id}/neighbors?depth=&types=&confidence=`, `/events`, `/episode/{idx}`, `/review/aliases`, `/review/contradictions`, `/synthetic/load`.
- **Frontend**: React + TypeScript; Cytoscape.js for the chart; TanStack Table for evidence tables; Leaflet once coordinates exist.
- **Rebuild path**: `scripts/build_db.py` stays the single source of truth; the GUI never writes to real rows, only to `aliases.json`/overrides, then rebuilds. This keeps provenance auditable.
- **Deployment**: single container (API + static build) — the dataset is small (<100 MB with transcripts), so no external DB is needed for a demo; Postgres swap is straightforward later.

## 5. Guardrails the UI must enforce

- Persistent banner: "Claims are as stated on the FDD Long War Journal *Generation Jihad* podcast; machine-transcribed; not independently adjudicated."
- Every edge and event is one click from its quote + timestamp; no un-sourced edge is displayed.
- Inferred and derived edges are visually distinct and can be hidden.
- Synthetic records carry a badge on every surface (search rows, nodes, tables) and are excluded by default.
- Presenters (Roggio, Joscelyn, Weiss, Truzman, …) are excluded from the entity set unless they are discussed as subjects.

## 6. Phasing

1. Read-only explorer: search, entity pages, link chart with evidence drawer, episode viewer (uses existing exports; ~2–3 weeks).
2. Timeline + status-as-of slider + contradiction queue.
3. Geocoding + map; alias-review queue writing back to `aliases.json`.
4. Synthetic scenario manager; exercise mode (hide real/synthetic distinction for trainees, reveal on debrief).

## 7. Known data-quality items to carry into the review queue

- Manual (non-Claude) extractions are sparser on organizations/places; see each `raw/reports/batch_XX_report.md` for which episodes.
- States (Iran, Pakistan, United States…) exist both as organization (actor) and place (location) by design; the GUI should link the two.
- Some family edges were extracted with reversed direction upstream; `build_db.py` normalizes the wording, but analysts should spot-check "father/son" edges.
- `allied_with`/`rival_of` are over-generated by the extractor for co-mentioned orgs; treat as weak evidence unless `confidence='stated'` and a quote is present.
