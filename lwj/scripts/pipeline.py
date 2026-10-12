#!/usr/bin/env python3
"""LWJ article -> Claude extraction pipeline using the Anthropic Message Batches API.
  python3 pipeline.py prepare          # corpus.jsonl -> relevant.jsonl (+ ids, model choice, chunking)
  python3 pipeline.py submit [N]       # submit up to N batches (default all pending)
  python3 pipeline.py poll             # fetch finished batches -> extractions/<aid>.json
  python3 pipeline.py status
"""
import json, os, sys, re, hashlib, time, glob, collections
import anthropic
HERE=os.path.dirname(os.path.abspath(__file__))
CORPUS=f"{HERE}/corpus.jsonl"; REL=f"{HERE}/relevant.jsonl"; BATCHES=f"{HERE}/batches.json"; OUT=f"{HERE}/extractions"
PROMPT=open(f"{HERE}/lwj_prompt.txt").read()
HAIKU="claude-haiku-4-5-20251001"; SONNET="claude-sonnet-4-6"
TAGS={'afghanistan','pakistan','taliban','al qaeda','haqqani network','ttp','pakistan-taliban','aqis','islamic state khorasan province',
      'movement of the taliban in pakistan','al qaeda in the indian subcontinent','lashkar-e-taiba','lashkar-e-jhangvi','jaish-e-mohammed',
      'islamic movement of uzbekistan','turkistan islamic party','islamic jihad union','north waziristan','south waziristan','quetta shura',
      'mullah omar','sirajuddin haqqani','ayman al zawahiri','osama bin laden','hafiz gul bahadur','baitullah mehsud','hakeemullah mehsud',
      'tehrik-e-taliban pakistan','afghan taliban','isaf','afghan national army','afghan national police','us drone strikes','drone strikes',
      'pakistani taliban','iskp','isis-k','afghanistan-pakistan','afpak','gitmo','guantanamo'}
KW=re.compile(r"\b(afghan\w*|pakistan\w*|taliban|haqqani\w*|al[ -]?qa[ei]da|AQIS|TTP|waziristan|lashkar-e-(taiba|jhangvi)|jaish-e-mohammed|khorasan|ISKP|IS-K|kabul|kandahar|peshawar|quetta|zawahiri|bin laden|mehsud|hekmatyar|bajaur|khyber|swat valley|balochistan|baluchistan|helmand|kunar|nuristan|paktika|paktia|khost|nangarhar|ghazni|wardak|kunduz|guantanamo|gitmo)\b",re.I)
def aid(url): return "A-"+hashlib.sha1(url.encode()).hexdigest()[:10]
def is_relevant(r):
    t={x.lower() for x in r['tags']}
    if t & TAGS: return True, 'tag'
    txt=r['title']+' '+r['body']
    hits=KW.findall(txt)
    if len(hits)>=3 and (len(hits)>=8 or len(r['body'])<4000 or KW.search(r['title'])): return True, 'kw'
    return False, ''
def chunks(body, max_chars=30000, overlap=1500):
    if len(body)<=max_chars: return [body]
    out=[]; i=0
    while i<len(body):
        out.append(body[i:i+max_chars]); i+=max_chars-overlap
    return out
def prepare():
    seen=set(); n=0; models=collections.Counter(); why=collections.Counter()
    with open(REL,'w') as fo:
        for l in open(CORPUS):
            r=json.loads(l)
            if r['url'] in seen or not r.get('body'): continue
            seen.add(r['url'])
            ok,w=is_relevant(r)
            if not ok: continue
            why[w]+=1
            r['id']=aid(r['url'])
            longform=('Analysis' in r['categories']) or len(r['body'])>12000 or not r['date']
            r['model']=SONNET if longform else HAIKU
            r['chunks']=chunks(r['body']); models[r['model']]+=1; n+=1
            fo.write(json.dumps(r,ensure_ascii=False)+'\n')
    print('relevant',n,dict(models),dict(why))
def load_batches():
    return json.load(open(BATCHES)) if os.path.exists(BATCHES) else {"submitted":{}, "done_ids":[]}
def save_batches(b): json.dump(b,open(BATCHES,'w'),indent=0)
def requests_for(r):
    reqs=[]
    for k,ch in enumerate(r['chunks']):
        user=(f"ARTICLE TITLE: {r['title']}\nPUBLISHED: {r['date'][:10]}\nURL: {r['url']}\nTAGS: {', '.join(r['tags'])}\n"
              +(f"(part {k+1} of {len(r['chunks'])})\n" if len(r['chunks'])>1 else '')+f"\n{ch}")
        reqs.append({"custom_id":f"{r['id']}__c{k}","params":{"model":r['model'],"max_tokens":16000,
            "system":[{"type":"text","text":PROMPT,"cache_control":{"type":"ephemeral"}}],
            "messages":[{"role":"user","content":user}]}})
    return reqs
def submit(limit=None):
    c=anthropic.Anthropic(); b=load_batches(); os.makedirs(OUT,exist_ok=True)
    have={os.path.basename(p)[:-5] for p in glob.glob(f"{OUT}/*.json")}
    queued={cid.split('__')[0] for v in b['submitted'].values() if v.get('status')!='collected' for cid in v['ids']}
    todo=[json.loads(l) for l in open(REL)]
    todo=[r for r in todo if r['id'] not in have and r['id'] not in queued]
    print('to submit',len(todo))
    # group by model so batch cost/latency is uniform; 2000 requests per batch
    for model in (HAIKU,SONNET):
        rs=[r for r in todo if r['model']==model]
        for i in range(0,len(rs),2000):
            if limit is not None and limit<=0: return
            reqs=[q for r in rs[i:i+2000] for q in requests_for(r)]
            mb=c.messages.batches.create(requests=reqs)
            b['submitted'][mb.id]={"ids":[q['custom_id'] for q in reqs],"model":model,"created":time.time(),"status":"in_progress"}
            save_batches(b); print('submitted',mb.id,model,len(reqs))
            if limit is not None: limit-=1
def parse_json(s):
    try: return _parse_json(s)
    except Exception:
        import json_repair
        d=json_repair.loads(s[s.find("{"):] if "{" in s else s)
        if not isinstance(d,dict) or "persons" not in d: raise
        return d
def _parse_json(s):
    s=s.strip(); s=re.sub(r"^```(?:json)?","",s).strip(); s=re.sub(r"```$","",s).strip()
    i=s.find("{"); j=s.rfind("}")
    return json.loads(s[i:j+1])
def merge(parts):
    res={"relevant":any(p.get("relevant") for p in parts),"summary":" ".join(p.get("summary","") for p in parts if p.get("summary")),
         "persons":[],"organizations":[],"places":[],"events":[],"relationships":[],"sources_cited":[],"key_claims":[]}
    seen={k:set() for k in res}
    for p in parts:
        for k in ["persons","organizations","places"]:
            for it in p.get(k,[]) or []:
                if not isinstance(it,dict): continue
                key=(it.get("name") or "").strip().lower()
                if not key: continue
                if key in seen[k]:
                    ex=next(x for x in res[k] if (x.get("name") or "").strip().lower()==key)
                    for f,v in it.items():
                        if isinstance(v,list): ex[f]=(ex.get(f) or [])+[x for x in v if x not in (ex.get(f) or [])]
                        elif not ex.get(f) and v: ex[f]=v
                else: seen[k].add(key); res[k].append(it)
        for k in ["events","relationships"]:
            for it in p.get(k,[]) or []:
                if not isinstance(it,dict): continue
                key=json.dumps({a:it.get(a) for a in ("source","target","type","date","description")},sort_keys=True)
                if key not in seen[k]: seen[k].add(key); res[k].append(it)
        for k in ["sources_cited","key_claims"]:
            for it in p.get(k,[]) or []:
                if it not in res[k]: res[k].append(it)
    return res
def poll():
    c=anthropic.Anthropic(); b=load_batches(); os.makedirs(OUT,exist_ok=True)
    meta={json.loads(l)['id']:json.loads(l) for l in open(REL)}
    for bid,info in list(b['submitted'].items()):
        if info.get('status')=='collected': continue
        mb=c.messages.batches.retrieve(bid)
        info['status']=mb.processing_status; info['counts']=dict(mb.request_counts)
        print(bid,mb.processing_status,dict(mb.request_counts))
        if mb.processing_status!='ended': continue
        parts=collections.defaultdict(dict); usage=collections.Counter(); errs=[]
        for res in c.messages.batches.results(bid):
            a,ck=res.custom_id.split('__c')
            if res.result.type=='succeeded':
                m=res.result.message
                usage['in']+=m.usage.input_tokens; usage['out']+=m.usage.output_tokens
                usage['cache_read']+=getattr(m.usage,'cache_read_input_tokens',0) or 0
                txt="".join(getattr(x,'text','') for x in m.content)
                try: parts[a][int(ck)]=parse_json(txt)
                except Exception as e:
                    errs.append((res.custom_id,'json',str(e)[:80])); parts[a][int(ck)]={"_parse_error":str(e)[:200],"_raw":txt[-2000:]}
            else:
                errs.append((res.custom_id,res.result.type,str(getattr(res.result,'error',''))[:120]))
        for a,ps in parts.items():
            m=meta.get(a)
            if not m: continue
            good=[ps[k] for k in sorted(ps) if '_parse_error' not in ps[k]]
            if not good: continue
            d=merge(good) if len(good)>1 else good[0]
            d={"article":{"id":a,"url":m['url'],"title":m['title'],"published":m['date'][:10],"author":m['author'],"tags":m['tags'],"categories":m['categories']},
               "model":info['model'],**d}
            if len(good)<len(m['chunks']): d['_partial']=True
            json.dump(d,open(f"{OUT}/{a}.json",'w'),ensure_ascii=False,indent=0)
        info['status']='collected'; info['usage']=dict(usage); info['errors']=errs[:200]; info['n_err']=len(errs)
        save_batches(b); print('  collected',len(parts),'usage',dict(usage),'errors',len(errs))
def status():
    b=load_batches(); have=len(glob.glob(f"{OUT}/*.json")); rel=sum(1 for _ in open(REL)) if os.path.exists(REL) else 0
    u=collections.Counter()
    for info in b['submitted'].values():
        for k,v in (info.get('usage') or {}).items(): u[k]+=v
    print('relevant',rel,'extracted',have,'batches',collections.Counter(i['status'] for i in b['submitted'].values()),'usage',dict(u))
if __name__=='__main__':
    cmd=sys.argv[1]
    if cmd=='prepare': prepare()
    elif cmd=='submit': submit(int(sys.argv[2]) if len(sys.argv)>2 else None)
    elif cmd=='poll': poll()
    elif cmd=='status': status()
