"""Server-side Gem API helper for the Xavi review site. Never print or return the key."""
import json,time,os,urllib.request,urllib.parse,urllib.error
KEY_PATH=os.environ.get('GEM_KEY_PATH','/workspace/apple-pdes/.gem_key')
BASE='https://api.gem.com/'
VEERAJ='dXNlcnM6MjI1NTk='
def _key(): return (os.environ.get('GEM_API_KEY') or open(KEY_PATH).read()).strip()
def req(method,path,params=None,body=None):
    url=BASE+path+('?'+urllib.parse.urlencode(params,doseq=True) if params else '')
    h={'X-API-Key':_key()}; data=None
    if body is not None: data=json.dumps(body).encode(); h['Content-Type']='application/json'
    for a in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,data=data,headers=h,method=method),timeout=60) as r:
                raw=r.read(); time.sleep(0.08)
                return r.status,(json.loads(raw) if raw else None),r.headers.get('x-pagination')
        except urllib.error.HTTPError as e:
            raw=e.read().decode(errors='replace')
            if e.code==429: time.sleep(2+a); continue
            try: return e.code,json.loads(raw),None
            except Exception: return e.code,{'_raw':raw[:500]},None
        except Exception as e:
            if a<5: time.sleep(1+a); continue
            return 0,{'_error':str(e)[:200]},None
def lookup_handle(h):
    s,d,_=req('GET','v0/candidates',{'linked_in_handle':h,'page_size':5})
    return d[0] if s==200 and isinstance(d,list) and d else None
class EventsUnavailable(Exception): pass
def events(cid):
    out=[];p=1
    while True:
        s,d,pg=req('GET',f'v0/candidates/{cid}/events',{'page':p,'page_size':100})
        if s==403: raise EventsUnavailable('Gem API: events are deprecated for this key (403)')
        if s!=200 or not isinstance(d,list): break
        out+=d; pg=json.loads(pg) if pg else {}
        if not pg.get('next_page'): break
        p=pg['next_page']
    return out
def outreach_summary(cid):
    """Returns None when Gem's API won't expose activity (events endpoint deprecated -> 403)."""
    try: ev=events(cid)
    except EventsUnavailable: return None
    sent=[e for e in ev if e.get('type') in('sequences','manual_touchpoints') and e.get('subtype') in('first_outreach','follow_up')]
    rep=[e for e in ev if e.get('type')=='sequence_replies' or e.get('subtype')=='reply']
    ts=lambda L: max((e.get('timestamp') or 0) for e in L) if L else None
    return {'contacted':bool(sent),'touches':len(sent),'last_touch':ts(sent),'first_touch':min((e.get('timestamp') or 0) for e in sent) if sent else None,
            'replied':bool(rep),'last_reply':ts(rep),'reply_status':(sorted(rep,key=lambda e:e.get('timestamp') or 0)[-1].get('reply_status') if rep else None),
            'sequence_ids':sorted({e.get('sequence_id') for e in sent if e.get('sequence_id')})}
def create_candidate(c):
    parts=(c.get('name') or '').split()
    urls=[u for u in [c.get('linkedin_url'),c.get('github_url'),c.get('personal_site')] if u]
    body={k:v for k,v in {'created_by':VEERAJ,'first_name':parts[0] if parts else None,'last_name':' '.join(parts[1:]) or None,
        'linked_in_handle':c.get('handle'),'profile_urls':urls or None,'title':c.get('current_title') or c.get('founding_role'),
        'company':c.get('current_company') or c.get('founding_company'),'location':c.get('location')}.items() if v}
    s,d,_=req('POST','v0/candidates',body=body)
    if s in(200,201) and isinstance(d,dict) and d.get('id'): return d['id'],'created'
    if s==400 and isinstance(d,dict):
        dup=(d.get('errors') or {}).get('duplicate_candidate') or {}
        if isinstance(dup,dict) and dup.get('id'): return dup['id'],'existing'
    raise RuntimeError(f'gem create failed {s} {json.dumps(d)[:300]}')
def ensure_candidate(c):
    f=lookup_handle(c.get('handle')) if c.get('handle') else None
    if f: return f['id'],'existing'
    return create_candidate(c)
def add_to_project(pid,ids):
    s,d,_=req('PUT',f'v0/projects/{pid}/candidates',body={'candidate_ids':ids,'user_id':VEERAJ})
    if s in(200,204): return True
    if s==400 and 'already' in json.dumps(d).lower(): return True
    raise RuntimeError(f'gem add failed {s} {json.dumps(d)[:300]}')
def remove_from_project(pid,ids):
    s,d,_=req('DELETE',f'v0/projects/{pid}/candidates',body={'candidate_ids':ids,'user_id':VEERAJ})
    return s,d
def list_projects():
    out=[]
    for arch in (False,True):
        p=1
        while True:
            s,d,pg=req('GET','v0/projects',{'page':p,'page_size':100,'is_archived':arch})
            if s!=200 or not isinstance(d,list): break
            out+=d; pg=json.loads(pg) if pg else {}
            if not pg.get('next_page'): break
            p=pg['next_page']
    return out
def ensure_project(name,desc=''):
    for p in list_projects():
        if p.get('name')==name and not p.get('is_archived'): return p['id'],'existing'
    s,d,_=req('POST','v0/projects',body={'name':name,'user_id':VEERAJ,'privacy_type':'shared','description':desc})
    if s in(200,201) and d.get('id'): return d['id'],'created'
    raise RuntimeError(f'project create failed {s} {json.dumps(d)[:300]}')
def project_members(pid):
    out=[];p=1
    while True:
        s,d,pg=req('GET',f'v0/projects/{pid}/candidates',{'page':p,'page_size':100})
        if s!=200 or not isinstance(d,list): break
        out+=d; pg=json.loads(pg) if pg else {}
        if not pg.get('next_page'): break
        p=pg['next_page']
    return out
def sequences():
    s,d,_=req('GET','v0/sequences',{'page_size':100})
    return d if s==200 else []
