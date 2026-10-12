# Synthetic supplements
Fictional persons/orgs/events in the same JSON shape as `raw/extractions/*.json` (set `"episode": {"idx": null, "title": "SYNTHETIC: <scenario>"}`).
Build with `python3 scripts/build_db.py --synthetic synthetic/*.json`. Entity ids are prefixed `S` and rows carry `dataset='synthetic'`
so a GUI can badge them. Rules: fictional names only; a synthetic person may be *linked* to a real organization or place, but never
to a real person as family/deputy/etc. without a visible synthetic flag on the edge (the `dataset` column on `relationships`).
