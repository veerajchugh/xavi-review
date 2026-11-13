import json,re,time,urllib.request,urllib.parse,html,os,sys
pool=json.load(open('pool.json'))
OUT='gh.json'; res=json.load(open(OUT)) if os.path.exists(OUT) else {}
UA={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) Chrome/124 Safari/537.36','Accept':'text/html'}
def fetch(u,hdr=UA):
    for a in range(4):
        try: return urllib.request.urlopen(urllib.request.Request(u,headers=hdr),timeout=30).read().decode('utf-8','replace')
        except urllib.error.HTTPError as e:
            if e.code in (403,429): time.sleep(30); continue
            if e.code==404: return None
            time.sleep(3)
        except Exception: time.sleep(3)
    return None
def norm(s): return re.sub(r'[^a-z0-9]','',(s or '').lower())
def profile(login):
    t=fetch('https://github.com/'+login)
    if not t: return None
    g=lambda pat: (html.unescape(m.group(1)).strip() if (m:=re.search(pat,t,re.S)) else None)
    d=dict(login=login,url='https://github.com/'+login,
      name=g(r'itemprop="name">\s*(.*?)\s*</span>'),
      bio=g(r'class="p-note user-profile-bio[^"]*"[^>]*>\s*<div>(.*?)</div>'),
      company=g(r'itemprop="worksFor".*?<span class="p-org"><div>(.*?)</div>'),
      location=g(r'itemprop="homeLocation".*?<span class="p-label">(.*?)</span>'),
      website=g(r'itemprop="url"[^>]*>.*?href="(https?://[^"]+)"'),
      repos=g(r'Repositories\s*<span[^>]*class="Counter[^"]*"[^>]*>(.*?)</span>'),
      followers=g(r'<span class="text-bold color-fg-default">([\d.,k]+)</span>\s*followers'),
      linkedin=re.findall(r'href="https?://(?:www\.)?linkedin\.com/in/([^"/?]+)',t),
      pinned=re.findall(r'<span class="repo"[^>]*>\s*(.*?)\s*</span>',t)[:6],
      contribs=g(r'([\d,]+)\s+contributions\s+in the last year'))
    return d
for i,p in enumerate(sorted(pool,key=lambda p:-p.get('pre',0))):
    if p['handle'] in res: continue
    name=re.sub(r'[^\w\s\-\.]','',p['name'] or '').strip()
    if len(name.split())<2 or len(name.split()[-1].strip('.'))<2:
        res[p['handle']]={'tc':None,'match':None,'skipped':'abbreviated name'}; continue
    q=urllib.parse.quote(f'fullname:"{name}"')
    t=fetch(f'https://api.github.com/search/users?q={q}&per_page=5',{'User-Agent':'xavi-review','Accept':'application/vnd.github+json'})
    time.sleep(6.2)
    r={'tc':0,'match':None}
    if t:
        d=json.loads(t); r['tc']=d.get('total_count',0)
        cos={norm(j['c']) for j in p['jobs'] if j.get('c')}
        for it in d.get('items',[])[:3]:
            pr=profile(it['login']); time.sleep(0.3)
            if not pr: continue
            why=None
            if any(norm(l)==norm(p['handle']) for l in pr['linkedin']): why='linkedin_link'
            elif pr['company'] and any(c and (c in norm(pr['company']) or norm(pr['company']).strip('') in c) for c in cos if len(c)>2): why='company'
            elif pr['bio'] and any(c in norm(pr['bio']) for c in cos if len(c)>3): why='bio_company'
            elif r['tc']==1 and pr['location'] and norm(p['location'].split(',')[0])[:6] in norm(pr['location']): why='unique_name_location'
            if why: pr['why']=why; r['match']=pr; break
    res[p['handle']]=r; json.dump(res,open(OUT,'w'))
    print(i,p['name'],r['tc'],(r['match'] or {}).get('login'),(r['match'] or {}).get('why'),flush=True)
