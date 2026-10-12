#!/usr/bin/env python3
"""Print network statistics from db/afpak.sqlite as Markdown (feeds docs/network-findings.md)."""
import sqlite3, os, sys, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
con = sqlite3.connect(f"{ROOT}/db/afpak.sqlite")
q = lambda s, *a: con.execute(s, a).fetchall()
def table(rows, hdr):
    out = ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    out += ["| " + " | ".join(str(x) if x is not None else "" for x in r) + " |" for r in rows]
    return "\n".join(out)
def deg(kind=None):
    k = f"and e.kind='{kind}'" if kind else ""
    return q(f"""select e.name, e.kind, e.n_episodes, count(r.id) rels,
        sum(r.confidence='stated') stated, sum(r.confidence='inferred') inferred
        from entities e join relationships r on r.source_id=e.id or r.target_id=e.id
        where e.dataset='real' {k} group by e.id order by rels desc""")
n = {t: q(f"select count(*) from {t}")[0][0] for t in ("episodes","entities","relationships","events","mentions","aliases")}
print("## Corpus\n", ", ".join(f"{k}: {v}" for k, v in n.items()))
print("\n## Most connected persons (degree = relationship rows)\n", table(deg("person")[:40], ["person","kind","episodes","edges","stated","inferred"]))
print("\n## Most connected organizations\n", table(deg("organization")[:25], ["org","kind","episodes","edges","stated","inferred"]))
print("\n## Relationship types\n", table(q("select type, count(*), sum(confidence='stated'), sum(confidence='inferred') from relationships where dataset='real' group by type order by 2 desc"), ["type","n","stated","inferred"]))
print("\n## Family ties\n", table(q("""select s.name, t.name, r.detail, group_concat(distinct r.episode_idx) from relationships r join entities s on s.id=r.source_id join entities t on t.id=r.target_id
    where r.type in ('family') or r.type like '%son_of%' or r.type like '%father%' or r.type like '%brother%' or r.type like '%uncle%' or r.type like '%married%' or r.type like 'relative%' group by s.id,t.id,r.type order by s.name"""), ["person","relative","detail","episodes"]))
print("\n## Leadership & succession\n", table(q("""select s.name, r.type, t.name, r.date, r.confidence, group_concat(distinct r.episode_idx) from relationships r join entities s on s.id=r.source_id join entities t on t.id=r.target_id
    where r.type in ('leads','leader_of','deputy_of','succeeded','succeeded_by','successor_of','appointed','commands','emir_of','deputy') group by s.id,t.id,r.type order by t.name, r.date"""), ["person","type","org/person","date","conf","episodes"]))
print("\n## Shelter / hosting / protection\n", table(q("""select s.name, r.type, t.name, r.date, r.confidence, group_concat(distinct r.episode_idx) from relationships r join entities s on s.id=r.source_id join entities t on t.id=r.target_id
    where r.type in ('sheltered_by','hosted_by','shelters','hosts','protected_by','harbors','harbored_by','safe_haven') group by s.id,t.id,r.type order by r.date"""), ["who","type","by","date","conf","episodes"]))
print("\n## Geographic hubs (places by mentions + located_in edges)\n", table(q("""select e.name, e.country, e.n_episodes, (select count(*) from relationships r where r.target_id=e.id) located, (select count(*) from events ev where ev.place_id=e.id) events
    from entities e where e.kind='place' and e.dataset='real' order by (located+events+e.n_episodes) desc limit 30"""), ["place","country","episodes","located_in edges","events"]))
print("\n## Deaths / captures (status)\n", table(q("select name, status, status_detail, n_episodes from entities where kind='person' and status in ('deceased','killed','dead','captured','detained','arrested') order by n_episodes desc limit 60"), ["person","status","detail","episodes"]))
print("\n## Dated events by year\n", table(q("select substr(date,1,4) y, count(*) from events where dataset='real' and date!='' group by y order by y"), ["year","events"]))
print("\n## Cross-episode continuity: persons discussed in 5+ episodes\n", table(q("select name, n_episodes, first_mentioned, last_mentioned, status from entities where kind='person' and n_episodes>=5 order by n_episodes desc"), ["person","episodes","first","last","status"]))
