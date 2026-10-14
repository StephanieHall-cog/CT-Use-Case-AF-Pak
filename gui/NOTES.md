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
