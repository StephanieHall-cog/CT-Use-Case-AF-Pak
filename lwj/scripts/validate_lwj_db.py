#!/usr/bin/env python3
"""Integrity checks for db/lwj_afpak.sqlite. Exit 1 on hard failures; prints warnings for soft issues."""
import sqlite3, sys, os, re
ROOT=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB=sys.argv[1] if len(sys.argv)>1 else f"{ROOT}/db/lwj_afpak.sqlite"
c=sqlite3.connect(DB); q=lambda s:c.execute(s).fetchone()[0]
hard=[]; warn=[]
def H(label,n): (hard if n else []).append(f"{label}: {n}")
def W(label,n,limit=0): (warn if n>limit else []).append(f"{label}: {n}")
H("relationships with unknown source_id", q("select count(*) from relationships r left join entities e on e.id=r.source_id where e.id is null"))
H("relationships with unknown target_id", q("select count(*) from relationships r left join entities e on e.id=r.target_id where e.id is null"))
H("relationships with unknown article_id", q("select count(*) from relationships r left join articles a on a.id=r.article_id where a.id is null"))
H("events with unknown article_id", q("select count(*) from events e left join articles a on a.id=e.article_id where a.id is null"))
H("event_actors with unknown event_id", q("select count(*) from event_actors x left join events e on e.id=x.event_id where e.id is null"))
H("event_actors with unknown entity_id", q("select count(*) from event_actors x left join entities e on e.id=x.entity_id where e.id is null"))
H("mentions with unknown entity_id", q("select count(*) from mentions m left join entities e on e.id=m.entity_id where e.id is null"))
H("memberships with unknown org_id", q("select count(*) from memberships m left join entities e on e.id=m.org_id where e.id is null"))
H("aliases with unknown entity_id", q("select count(*) from aliases a left join entities e on e.id=a.entity_id where e.id is null"))
H("relationships with blank type", q("select count(*) from relationships where type is null or trim(type)=''"))
H("self-relationships", q("select count(*) from relationships where source_id=target_id"))
W("relationships with nonstandard confidence", q("select count(*) from relationships where confidence not in ('stated','inferred')"))
H("articles without url", q("select count(*) from articles where url is null or url=''"))
H("entities with bad kind", q("select count(*) from entities where kind not in ('person','organization','place')"))
H("entities with bad id prefix", q("select count(*) from entities where not ((kind='person' and id like 'P-%') or (kind='organization' and id like 'O-%') or (kind='place' and id like 'L-%'))"))
W("events with nonstandard date_precision", q("select count(*) from events where date_precision not in ('day','month','year','approx','unknown')"))
H("events with malformed date", q("select count(*) from events where date is not null and date!='' and date not glob '[0-9]*'"))
H("alias equal to canonical name", q("select count(*) from aliases a join entities e on e.id=a.entity_id where lower(a.alias)=lower(e.name)"))
W("relationships without quote", q("select count(*) from relationships where quote is null or quote=''"), limit=q("select count(*) from relationships")//20)
W("person entities in zero articles", q("select count(*) from entities where kind='person' and n_articles=0"))
W("events dated after article publication (+1y)", q("select count(*) from events where date is not null and length(date)>=4 and cast(substr(date,1,4) as int)>cast(substr(published,1,4) as int)+1"))
W("placeholder-looking person names", q("select count(*) from entities where kind='person' and (lower(name) like 'unnamed%' or lower(name) like 'unknown%' or lower(name) like 'unidentified%')"))
W("same name across kinds", q("select count(*) from (select lower(name) n from entities group by n having count(distinct kind)>1)"), limit=200)
for t in ("articles","entities","aliases","relationships","events","mentions","memberships","roles","claims"):
    print(f"{t:14s}{q(f'select count(*) from {t}'):>8}")
print("\nwarnings:" if warn else "\nno warnings"); [print("  ",w) for w in warn]
print("\nHARD FAILURES:" if hard else "\nall hard checks passed"); [print("  ",h) for h in hard]
sys.exit(1 if hard else 0)
