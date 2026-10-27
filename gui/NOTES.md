# GUI build notes (working file for the build; see docs/gui-plan-v2.md for the plan)

Stephanie's required baseball-card fields (always shown, all editable, synthetic targets pre-filled):
Name · Name variations · Kunyah/Call Sign/Nick Names · Tribe affiliation · Religion · Terrorist Network · Bed Down Location (BDL) ·
Addresses or Alternate Known Locations · Travel · Car make/model · Family member names and relationship ·
Phone/IMSI/IMEI pairings (each value a separate editable field, grouped to show pairing; a phone may have multiple IMSI/IMEI; link push tokens) ·
Social media handles and ID (separate fields) · Date of birth · Passport number · CNIC or ID number · Visa number · Additional notes · a card map with a dropdown of CDR / SS7 pings / other geolocation events · Physical descriptors (fillable).

Stack: gui/server.mjs (Express 4 + better-sqlite3; Node 24). Reads AFPAK_DB (default ../db/afpak_demo.sqlite, built with
`python3 scripts/build_db.py --synthetic synthetic/*.json --db db/afpak_demo.sqlite`) read-only; writes to gui/data/app.db
(users, sessions, audit, card_fields, card_selectors, card_links, investigations). Auth copied from UKR Watch lib/auth.mjs
(cookie `uw`, roles viewer/analyst/instructor/admin, ADMIN_PASSWORD env). Frontend: single gui/public/index.html, MapLibre
(OpenFreeMap dark) + vis-network, UKR Watch CSS tokens. Tabs: Map · Targets · Link chart · Admin.

Added by Stephanie (3rd message): Date of birth · Passport number · CNIC or ID number · Visa number · Additional notes.
Added (4th message): EVERY field has a fillable Citation (source + URL). Inference/algorithm-identified items (correlations,
matches to UN/FBI/podcast/document records) are stored as PROPOSALS with an auto-citation hyperlink to the source database
record and need an analyst Accept (merge/add) / Reject button before they appear on the card.

app.db tables: card_fields(id, entity_id, field, value, citation, citation_url, status 'accepted'|'proposed'|'rejected',
proposed_by 'analyst'|'algorithm:<name>', edited_by, edited_at); card_selectors(id, entity_id, kind, value, parent_id (pairing:
IMSI/IMEI/pushtoken -> phone), platform, label, citation, citation_url, status, proposed_by...); card_links(a,b,relation,
evidence,citation_url,status,proposed_by); proposals view = status='proposed'.

Added (5th message): every location event on the maps needs a citation (source of information) and, when pulled from a feed,
a hyperlink to that database/feed. Implementation: API geojson features carry `source`, `source_label`, `source_url`
(ISW map page URL / podcast episode audio+timestamp / document URL+page / UN or FBI listing URL / synthetic scenario file /
feed URL); popups and drawers always render "Source: <label> ↗". location_hits and sites get `source_url` columns.

Added (6th message) — "Draft memo" button on the baseball card opening an email-style template, 4 types:
1. Profile of the Target: auto-populated from card fields in digestible format WITH citations; editable summary paragraph at top; option to add additional free-text sections.
2. Location update: references existing profile; summary paragraph; free-text area; line "<name> is located at <lat/long or MGRS> as of <time>" from latest accepted hit.
3. Burn Notice: references previous memos on the individual; free-text why we should not engage.
4. Threat Notice: immediate-attention; free text describing the threat, linked to the profile.
All memos linked to the individual and listed on the card with an easy reader window.
Server: table memos(id, entity_id, kind, subject, body, summary, sections JSON, refs JSON, created_by, created_at); GET/POST /api/targets/:id/memos, GET /api/memos/:id; template builder server-side (GET /api/targets/:id/memo-template?kind=).
Server status: gui/server.mjs runs (port 3300, ADMIN_PASSWORD=demo-pass-123, login admin). Seen once: better-sqlite3 Statement destructor assertion at GC → cache prepared statements (prep(sql) memo) instead of re-preparing per request. index.html NOT yet written.

STATE: gui/public/index.html written (map/targets/link chart/proposals/admin; all card fields fillable w/ citation + url; selector pairings; card map w/ hit-kind dropdown).
Memo module contract (child session delivers gui/public/memos.js + gui/lib/memos.mjs routes, mounted in server.mjs):
  window.Memos.open(CARD)  -> opens draft dialog (CARD = GET /api/targets/:id payload: entity, fields[], selectors[], hits[], relationships[], profiles[])
  window.Memos.list(CARD, el) -> renders memo list + reader pane into el
Push method: git push https://x-access-token:${UKR_WATCH_GH_PAT}@github.com/StephanieHall-cog/CT-Use-Case-AF-Pak.git main  (proxy remote gives 403)

STATE 2: main=6fa645d pushed (works ONLY with RESEARCH_DASHBOARD_GH_PAT; UKR_WATCH_GH_PAT now denied). Server running :3300 (preview https://3300--71d7b7977aee4d27a6066de343042c15.preview.devinapps.com), Map + Targets grid verified in browser (34 cards: 14 synthetic + 20 real).
Memo child session: 27506e5a20fc43419885367a98e02aff (branch devin/memos-module; merge into main when it reports). Remaining: verify card tabs in browser, fix bugs, cache prepared statements, gui tests, README/docs update, testing_agent run, final message.
STATE 3: prepared-statement cache added to server.mjs; server relaunched with setsid (never pkill in the same exec as the relaunch). Verified in browser: Identity, Selectors (pairings), Location (map+dropdown+table). Still to eyeball: Correlations, Family, Sources, Proposals tab, Link chart tab.
STATE 4: gui/test/api.test.mjs added (npm test); server now REQUIRES a citation on analyst adds (fields w/ value, selectors, links, hits). Verified in browser: Correlations tab, Proposals view (27, accept/reject + auto-citation links), Link chart (Sirajuddin root → 47 nodes/257 edges). Next: wait for memo child (27506e5a…), merge branch devin/memos-module, README section for gui, testing_agent run, final message.
STATE 5: testing agent ran a bounded pass (declined real-person/selector/location flows; verified cited edits persist, citation refusal, audit, map drawer source links). Fixed vis-network arrows:'' invalid-option errors. circle-11 sprite warnings come from the OpenFreeMap style, not our layers.
STATE 6: memos branch merged (lib/memos.mjs, public/memos.js, test/memos.test.mjs; better-sqlite3 ^12.4.1 — fixes Node 24 GC abort). Fixed /api/maps column (image_local AS image_path) and signed-shift bug that produced "undefined" in synthetic physical descriptors. 12/12 tests pass.

Added (round 2, Stephanie): CITATION TRIGRAPHS — every cited row (card_fields / card_selectors / card_links / card_hits) now also carries
cit_src (3-letter source code), cit_pub (publication), cit_date (ISO), cit_trust (1 best … 4 worst) next to the free-text citation + citation_url.
Rendered on the card as an icon-like badge after the value, e.g. "Zahir Shah Mangal (SYN; 2/OCT/2026; trust 3)" or "Haji Zahir (GJP; 19/AUG/2014; trust 2)";
hover = full book-style cite (publication, date, trust level + meaning, detail, URL); click = opens the record in the source database/feed.
Codes (server.mjs CITE_CODES): SYN synthetic scenario · GJP Generation Jihad podcast · UNS UN 1988 list · FBI FBI Wanted · ISW map room · DOC document corpus ·
PUB public reference · SIG telecom feed (CDR/SS7) · ISR · HUM HUMINT · OSN open-source/social · ALG inference algorithm (auto-citation) · ANL analyst entry.
Trust (TRUST): 1 confirmed/official · 2 probably true, reputable single source · 3 possibly true / analyst assessment / synthetic · 4 unverified / algorithm-inferred.
Seeded rows get codes + dates from their origin (UN listed/updated date, FBI update, podcast episode publish date, SYN_DATE for synthetic); older app.db rows are backfilled on boot.
REJECT WITH COMMENT — delete buttons are gone. Accept / Reject everywhere (card rows, card Proposed tab, Proposals view); rejecting requires a comment
(PATCH status='rejected' + reject_comment → 400 without it). Row stays with status='rejected' + reject_comment/rejected_by/rejected_at, history in `rejections`.
"Run inference" no longer re-queues a rejected item: it bumps reidentified/last_identified and the Proposals view lists it under "Previously rejected" with the
analyst comment (Re-open button sets it back to proposed). Response: { proposals, reidentified }.
BULK — Proposals view and card Proposed tab have checkboxes, select all, "Accept / merge selected", "Reject selected" (one comment applied to each) and
"Accept / merge ALL"; POST /api/proposals/bulk { items:[{tbl,id}], status, reject_comment }.
PROFILE PHOTO — new fixed card field `photo` (type image). Header + grid card show it (silhouette placeholder when blank). "Set photo" / "+ upload" posts a data URL to
POST /api/targets/:id/photo (saved under gui/data/photos, served at /photos/…), "+ URL" records an image URL; both need a citation. FBI profile photos are seeded with the FBI cite.
Tests: 15 (api 7 + memos 8).

## Standalone offline snapshot (round 3)
- `scripts/build_standalone.mjs` boots server.mjs on a random port, pulls every API payload + entities/aliases/relationships/memberships/episodes/documents from the source DB, and inlines vendor libs, `standalone/basemap.json`, photos and `standalone/shim.js` into `public/index.html` (unchanged app code).
- The shim overrides `window.fetch` for `/api/*`, replays the localStorage ops log (`afpak-standalone-ops-v1`) on load, and wraps `maplibregl.Map` to force the offline style; symbol layers become HTML markers because there is no glyph server offline.
- Gotchas: `location.origin` is "null" under file:// (resolve URLs against a dummy origin); a style with `glyphs: undefined` fails validation (use any string); fbi.gov returns 403 to Node fetches, so photos are fetched through Chrome (`standalone/fetch_photos.cjs`); `lib/memo_core.mjs` holds the DB-free memo logic shared by server and shim.
