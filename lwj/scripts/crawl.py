import asyncio, aiohttp, json, re, sys, os, random, time
from lxml import html as LH
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT="corpus.jsonl"; FAIL="failed.txt"
KW=re.compile(r"afghan|pakistan|taliban|haqqani|qaeda|qaida|waziristan|quetta|kabul|peshawar|zawahiri|bin_laden|binladen|osama|omar|mansour|mansur|akhundzada|siraj|hekmatyar|hezb|tnsm|baitullah|hakeemullah|hakimullah|mehsud|wazir|kunar|helmand|kandahar|nangarhar|paktika|paktia|khost|nuristan|zabul|ghazni|wardak|logar|kunduz|badakhshan|herat|farah|uzbekistan|imu|turkistan|isaf|predator|drone|airstrike|strike|lashkar|jaish|ttp|khorasan|swat|bajaur|khyber|fata|nwfp|mohmand|orakzai|kurram|balochistan|baluch|karachi|lahore|islamabad|kashmir|punjab|isi|zardari|musharraf|kayani|gilani|sharif|karzai|ghani|kabul|bagram|guantanamo|gitmo|libi|yazid|rauf|kashmiri|hafiz", re.I)
done=set()
if os.path.exists(OUT):
    for l in open(OUT):
        try: done.add(json.loads(l)["url"])
        except: pass
urls=[u for u,_ in json.load(open("all_posts.json")) if u not in done and "/archives/" in u]
extra=[l.strip() for l in open("pages.txt")] if os.path.exists("pages.txt") else []
urls=[u for u in extra if u not in done]+sorted([u for u in urls if KW.search(u.rsplit('/',1)[-1])],key=lambda u:u,reverse=True)+sorted([u for u in urls if not KW.search(u.rsplit('/',1)[-1])],reverse=True)
print("todo",len(urls),"done",len(done),flush=True)
CONC=int(sys.argv[1]) if len(sys.argv)>1 else 4
def text_of(el):
    for bad in el.xpath('.//script|.//style|.//noscript|.//iframe'): bad.getparent().remove(bad)
    paras=[]
    for p in el.xpath('.//p|.//h2|.//h3|.//h4|.//li|.//blockquote'):
        t=re.sub(r'\s+',' ',p.text_content()).strip()
        if t: paras.append(t)
    if not paras:
        paras=[re.sub(r'\s+',' ',el.text_content()).strip()]
    # dedupe nested (blockquote contains p)
    out=[]
    for t in paras:
        if out and t in out[-1]: continue
        out.append(t)
    return "\n".join(out)
def parse(url,h):
    d=LH.fromstring(h)
    g=lambda xp:(d.xpath(xp) or [None])[0]
    title=g('//h1//text()') or g('//meta[@property="og:title"]/@content') or ''
    title=re.sub(r'\s+',' ',title).strip()
    date=g('//meta[@property="article:published_time"]/@content') or ''
    mod=g('//meta[@property="article:modified_time"]/@content') or ''
    author=g('//meta[@name="author"]/@content') or ''
    tags=[t.strip() for t in d.xpath('//a[contains(@href,"/tags/")][@rel="tag"]/text()')]
    cats=[t.strip() for t in d.xpath('//a[contains(@href,"/category/")][@rel="tag"]/text()')]
    desc=g('//meta[@property="og:description"]/@content') or ''
    body_el=(d.xpath('//div[contains(@class,"entry-content")]') or d.xpath('//article') or d.xpath('//main') or [None])[0]
    body=text_of(body_el) if body_el is not None else ''
    links=[]
    if body_el is not None:
        for a in body_el.xpath('.//a[@href]'):
            t=re.sub(r'\s+',' ',a.text_content()).strip()
            if t: links.append([t,a.get('href')])
    return dict(url=url,title=title,date=date,modified=mod,author=author,tags=tags,categories=cats,description=desc,body=body,links=links[:200])
async def worker(q,sess,fo,ff,stats):
    while True:
        url=await q.get()
        try:
            for attempt in range(5):
                try:
                    async with sess.get(url,headers={"User-Agent":UA,"Accept-Language":"en-US,en;q=0.9"}) as r:
                        if r.status==200:
                            h=await r.text(errors='replace'); rec=parse(url,h)
                            fo.write(json.dumps(rec,ensure_ascii=False)+"\n"); stats['ok']+=1; break
                        elif r.status in (403,429,503,502,500):
                            stats['throttle']+=1; await asyncio.sleep(5*(attempt+1)+random.random()*3)
                        elif r.status==404:
                            ff.write(url+" 404\n"); stats['404']+=1; break
                        else:
                            await asyncio.sleep(2)
                except (aiohttp.ClientError,asyncio.TimeoutError) as e:
                    await asyncio.sleep(3*(attempt+1))
            else:
                ff.write(url+" giveup\n"); stats['fail']+=1
        finally:
            q.task_done()
            n=stats['ok']+stats['404']+stats['fail']
            if n%200==0:
                fo.flush(); ff.flush()
                print(time.strftime('%H:%M:%S'),dict(stats),f"{n/(time.time()-stats['t0']):.1f}/s",flush=True)
            await asyncio.sleep(stats['delay'])
async def main():
    q=asyncio.Queue()
    for u in urls: q.put_nowait(u)
    stats=dict(ok=0,throttle=0,fail=0,t0=time.time(),delay=float(os.environ.get('DELAY','0.3')),**{'404':0})
    timeout=aiohttp.ClientTimeout(total=40)
    fo=open(OUT,'a'); ff=open(FAIL,'a')
    async with aiohttp.ClientSession(timeout=timeout,connector=aiohttp.TCPConnector(limit=CONC)) as sess:
        ws=[asyncio.create_task(worker(q,sess,fo,ff,stats)) for _ in range(CONC)]
        await q.join()
        for w in ws: w.cancel()
    fo.close(); ff.close()
    print("done",dict(stats))
asyncio.run(main())
