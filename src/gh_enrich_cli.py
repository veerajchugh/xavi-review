"""GitHub matching via the gh CLI (authenticated API). Verified only by LinkedIn link on GitHub, matching company/bio, or unique name+location."""
import json,re,time,subprocess,os,sys
sys.path.insert(0,'/workspace/xavi-review/lib'); import fit
pool=[p for p in json.load(open('pool.json')) if not (fit.buzzy(p) or fit.recent_raise(p)) and fit.discipline(p) not in('robotics','electrical/hardware')]
OUT='gh.json'; res=json.load(open(OUT)) if os.path.exists(OUT) else {}
def api(path):
    for a in range(3):
        r=subprocess.run(['gh','api','-H','Accept: application/vnd.github+json',path],capture_output=True,text=True)
        if r.returncode==0: return json.loads(r.stdout)
        if 'rate limit' in (r.stderr+r.stdout).lower(): time.sleep(30); continue
        if '404' in r.stderr or 'Not Found' in r.stdout: return None
        time.sleep(2)
    return None
def gql(login):
    q='query($l:String!){user(login:$l){contributionsCollection{contributionCalendar{totalContributions}} pinnedItems(first:6,types:REPOSITORY){nodes{... on Repository{name}}}}}'
    r=subprocess.run(['gh','api','graphql','-f','query='+q,'-f','l='+login],capture_output=True,text=True)
    try: u=json.loads(r.stdout)['data']['user']; return u['contributionsCollection']['contributionCalendar']['totalContributions'],[n['name'] for n in u['pinnedItems']['nodes'] if n]
    except Exception: return None,[]
norm=lambda s: re.sub(r'[^a-z0-9]','',(s or '').lower())
import threading,concurrent.futures as cf
LK=threading.Lock(); SL=threading.Lock(); last=[0]
def throttle():
    with SL:
        w=last[0]+2.05-time.time()
        if w>0: time.sleep(w)
        last[0]=time.time()
def one(i,p):
    if p['handle'] in res: return
    name=re.sub(r'[^\w\s\-\.]','',p['name'] or '').strip()
    if len(name.split())<2 or len(name.split()[-1].strip('.'))<2:
        with LK: res[p['handle']]={'match':None,'skipped':'abbreviated name'}
        return
    import urllib.parse
    throttle(); d=api('search/users?per_page=5&q='+urllib.parse.quote(f'fullname:"{name}"'))
    r={'tc':(d or {}).get('total_count',0),'match':None}
    cos={norm(j['c']) for j in p['jobs'] if j.get('c')}
    for it in (d or {}).get('items',[])[:3]:
        u=api('users/'+it['login']); 
        if not u: continue
        soc=api(f"users/{it['login']}/social_accounts") or []
        li=[re.search(r'linkedin\.com/in/([^/?#]+)',s.get('url',''),re.I) for s in soc]; li=[m.group(1) for m in li if m]
        if re.search(r'linkedin\.com/in/',u.get('blog') or ''): li.append(re.search(r'linkedin\.com/in/([^/?#]+)',u['blog']).group(1))
        why=None
        if any(norm(l)==norm(p['handle']) for l in li): why='linkedin_link'
        elif u.get('company') and any(c and len(c)>2 and (c in norm(u['company']) or norm(u['company']) in c) for c in cos if norm(u['company'])): why='company'
        elif u.get('bio') and any(c in norm(u['bio']) for c in cos if len(c)>3): why='bio_company'
        elif r['tc']==1 and u.get('location') and norm((p['location'] or '').split(',')[0])[:6] in norm(u['location']): why='unique_name_location'
        if why:
            k,pin=gql(it['login'])
            r['match']=dict(login=it['login'],url=u['html_url'],name=u.get('name'),bio=u.get('bio'),company=u.get('company'),location=u.get('location'),website=u.get('blog') or None,
                            repos=str(u.get('public_repos')),followers=str(u.get('followers')),contribs=str(k) if k is not None else None,pinned=pin,why=why); break
    with LK: res[p['handle']]=r; json.dump(res,open(OUT,'w'))
    print(i,len(pool),p['name'],(r['match'] or {}).get('login'),(r['match'] or {}).get('why'),flush=True)
with cf.ThreadPoolExecutor(6) as ex: list(ex.map(lambda a:one(*a),enumerate(pool)))
print('done',len(res),sum(1 for v in res.values() if v.get('match')))
