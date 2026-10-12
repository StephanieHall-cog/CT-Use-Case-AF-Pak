# Long War Journal written-corpus extraction (`lwj/`)

Companion to the podcast pipeline in `scripts/`. Same entity-id scheme (`P-/O-/L-` + sha1 of folded name), same
`scripts/normalize.py` resolver and `scripts/aliases.json`, so the two databases can be joined on entity id.

## What was processed

| Stage | Count |
|---|---|
| Posts enumerated from `longwarjournal.org` sitemaps (2004–2026) | 63,999 posts + 10 reference pages |
| Posts crawled (title, date, author, tags, categories, body) | 64,008 (0 failures) |
| Relevant to Afghanistan / Pakistan / Taliban / Haqqani / al-Qaeda-AQIS / TTP / ISKP (tag or keyword filter) | 24,675 |
| Articles run through LLM extraction | 14884 (extraction paused: Anthropic credits exhausted; `pipeline.py submit` resumes the remaining ~9.8k) |
| …of which the model confirmed in-scope (`relevant=true`) | 10390 |

Relevance filter (`pipeline.py::is_relevant`): article carries one of the AfPak tags (Afghanistan, Pakistan, Taliban,
Haqqani Network, al Qaeda, AQIS, TTP/Movement of the Taliban in Pakistan, ISKP, Lashkar-e-Taiba, Jaish-e-Mohammed,
Waziristan, Khorasan, …) **or** the title/body matches ≥3 AfPak keywords. Out-of-region articles that slip through
(e.g. AQAP, Shabaab, Syria) are kept with `articles.relevant=0` so nothing is silently lost; filter on that column.

## Pipeline (`lwj/scripts/`)

1. `crawl.py` – reads the Yoast post sitemaps, fetches each article (4 workers, ~7 req/s), writes `corpus.jsonl`.
   The WordPress REST API is Cloudflare-blocked; article pages are not.
2. `pipeline.py prepare|submit|poll|status` – filters the corpus, splits long bodies into 30k-char chunks, and submits
   Anthropic Message Batches with the cached system prompt `lwj_prompt.txt`. Haiku 4.5 for normal articles; Sonnet 4.6
   for `Analysis`-category / >12k-char pieces. Results land in `lwj/extractions/<article-id>.json`, one file per article,
   with the article metadata embedded under `article`. Truncated or malformed outputs are automatically re-queued
   (`submit` re-submits any relevant article that has no extraction file).
3. `build_lwj_db.py` – merges all extraction files into `db/lwj_afpak.sqlite` and `db/lwj_exports/*.csv|json`.

## Extraction schema (per article JSON)

```
article{id,url,title,published,author,tags,categories}  model  relevant  summary
persons[]        name, aliases[], role, organizations[], nationality_or_origin, status, status_detail,
                 family[{name,relation}], locations[], quote
organizations[]  name, aliases[], type, parent_or_allies[], rivals[], country_base, notes
places[]         name, type, country, parent, significance
events[]         date, date_precision(day|month|year|approx|unknown), type, description, place, actors[], targets[], casualties
relationships[]  source, target, type, detail, date, confidence(stated|inferred), quote
sources_cited[]  key_claims[]
```

Relationship direction: source = actor / junior party, target = recipient / senior party
(`TTP sheltered_by Taliban`, `Sirajuddin Haqqani deputy_of Hibatullah Akhundzada`, `killer killed victim`,
`person member_of org`, `subject based_in place`). For `family` edges the `detail` column is the **source's** relation to the target
(`Jalaluddin Haqqani —family(father)→ Sirajuddin Haqqani`).

## Database (`db/lwj_afpak.sqlite`)

| Table | Contents |
|---|---|
| `articles` | id, url, title, published, author, tags, categories, model, relevant, summary |
| `entities` | id, kind (person/organization/place), name, role, nationality, status, status_detail, org_type, country, place_type, parent_place, n_articles, first/last_mentioned, notes |
| `aliases` | every alternate spelling / kunya / title seen for an entity |
| `memberships`, `roles` | person→org and person→title, per article (so titles can be dated) |
| `mentions` | one row per person per article with the supporting quote and the locations the article tied them to |
| `relationships` | typed edge with detail, date, confidence, article id, publication date, quote |
| `events`, `event_actors` | dated events with place, casualties, and actor/target links |
| `claims`, `sources_cited` | the article's key analytic claims and the sources it cites |
| `person_status_history` | status (alive/killed/captured/…) as reported in each article, for timeline views |

Every row carries `article_id` → `articles.url` + `published`, and relationships/mentions carry the supporting quote.
Nothing is adjudicated: a relationship is what LWJ reported on that date, with `confidence` = `stated` or `inferred`.

### Entity resolution

`build_lwj_db.py` resolves names in this order: `scripts/aliases.json` → aliases the model listed in the same article →
exact folded-name match (diacritics, honorifics such as Mullah/Maulvi/Sheikh/Haji, al-/ul- removed) → a
transliteration skeleton for multi-token person names (Hakeemullah/Hakimullah, Mehsud/Mahsud, Mohammad/Muhammad,
Rehman/Rahman collapse together). Placeholder "persons" (unnamed commander, civilians, Taliban spokesman) are dropped.
Names that appear as both an organization and a place (Pakistan, United States, Taliban) are collapsed to the dominant
kind. Expect residual splits for rare spellings; `db/lwj_exports/entities.csv` sorted by name is the review surface,
and additions go in `scripts/aliases.json`.

## Exports (`db/lwj_exports/`)

`articles.csv`, `entities.csv`, `aliases.csv`, `relationships.csv` (joined names + article url + quote), `events.csv`,
`mentions.csv`, `roles.csv`, `memberships.csv`, and `graph.json` (`nodes` = every person plus any org/place seen in ≥2
articles; `edges` = relationships and memberships aggregated per source/target/type with article-id lists and first/last
dates). `graph.json` is the intended input for the link-analysis GUI.

## Known limitations

- LLM extraction: occasional wrong relationship direction, missed family links in long pieces, and date slips when an
  article discusses an event years before publication. Quotes are included precisely so these can be checked.
- Alias merging is conservative; the same person may still exist under 2–3 spellings. Country names serve as both
  state actor and location.
- Dates older than the article are preserved as written; relative dates ("yesterday") are resolved against the
  publication date and marked `approx` when the model was unsure.
- Article full text is **not** committed (copyright); `corpus.jsonl` stays local. Each record links back to the LWJ URL.
- Author bylines (Bill Roggio, Thomas Joscelyn, Caleb Weiss, …) are excluded as entities unless they are actors in the story.
