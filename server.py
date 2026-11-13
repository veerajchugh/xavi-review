#!/usr/bin/env python3
"""Xavi review site: password-protected, Gem key stays server-side. stdlib only.
run: python3 server.py [--port 8787]
"""
import sys,os,json,time,hmac,hashlib,secrets,threading,argparse,http.cookies,urllib.parse,collections,datetime,traceback
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
ROOT=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(ROOT,'lib'))
import store,fit,gemapi,learn_core
CFG=json.load(open(os.path.join(ROOT,'config.json')))
PW_FILE=os.path.join(ROOT,'.site_password'); SECRET_FILE=os.path.join(ROOT,'.site_secret'); ADMIN_FILE=os.path.join(ROOT,'.admin_token')
def _secret(env,f,n):
    v=os.environ.get(env)
    if v: return v.strip()
    if not os.path.exists(f):
        open(f,'w').write(secrets.token_urlsafe(n)); os.chmod(f,0o600)
    return open(f).read().strip()
# On Render these come from env vars (SITE_PASSWORD, SITE_SECRET, ADMIN_TOKEN, GEM_API_KEY); locally from dotfiles.
PW=_secret('SITE_PASSWORD',PW_FILE,18); SECRET=_secret('SITE_SECRET',SECRET_FILE,32).encode(); ADMIN=_secret('ADMIN_TOKEN',ADMIN_FILE,32)
NO_AUTH=os.environ.get('NO_AUTH','').strip().lower() in('1','true','yes')  # open link, no password; /api/admin/* still needs ADMIN_TOKEN
LOCK=threading.Lock()
ENABLE_SEQUENCE_ENROLL=False  # Gem public API has no enroll endpoint (GET /v0/sequences only). Keep False.
def sign(v): return v+'.'+hmac.new(SECRET,v.encode(),hashlib.sha256).hexdigest()[:32]
def valid(tok):
    try: v,s=tok.rsplit('.',1); return hmac.compare_digest(sign(v),tok) and int(v)>time.time()
    except Exception: return False
def public(r):
    d=dict(r['data']); d.pop('gem_prior',None) if False else None
    return {'handle':r['handle'],'status':r['status'],'fit':r['fit'],'batch':r['batch'],'added_at':r['added_at'],'decided_at':r['decided_at'],
            'reasons':r['reasons'] or [],'gem_id':r['gem_id'],'gem_projects':r['gem_projects'] or [],'outreach':r['outreach'],'outreach_checked_at':r['outreach_checked_at'],
            **{k:d.get(k) for k in('name','linkedin_url','region','current_title','current_company','location','total_yoe','founding_role','founding_company',
               'founding_tenure_months','founding_current','founding_hc','github_url','gh_repos','gh_followers','gh_contribs','gh_pinned','gh_bio','gh_verified','personal_site',
               'hardware_signal','hardware_note','yc','bay_area','why','photo_url','headline','jobs','gem_prior')},'features':fit.features(d)}
def stats(c,rows):
    D=[dict(x) for x in c.execute('select * from decisions where undone=0 order by ts')]
    weeks=collections.OrderedDict()
    for d in D:
        w=datetime.datetime.fromtimestamp(d['ts']).strftime('%G-W%V'); s=weeks.setdefault(w,{'week':w,'reviewed':0,'approved':0,'contacted':0,'replied':0})
        s['reviewed']+=1; s['approved']+=d['decision']=='approve'
    appr=[r for r in rows if r['status'] in('approved','resurface')]
    for r in appr:
        o=r['outreach'] or {}; w=datetime.datetime.fromtimestamp(r['decided_at'] or 0).strftime('%G-W%V')
        if w in weeks: weeks[w]['contacted']+=bool(o.get('contacted')); weeks[w]['replied']+=bool(o.get('replied'))
    cont=sum(1 for r in appr if (r['outreach'] or {}).get('contacted')); rep=sum(1 for r in appr if (r['outreach'] or {}).get('replied'))
    n=len({d['handle'] for d in D}); a=sum(1 for r in rows if r['status'] in('approved','resurface'))
    return {'reviewed':sum(1 for r in rows if r['status'] in('approved','passed','resurface')),'approved':a,'passed':sum(1 for r in rows if r['status']=='passed'),
            'queue':sum(1 for r in rows if r['status'] in('queue','resurface')),'contacted':cont,'replied':rep,
            'approve_rate':round(a/max(1,a+sum(1 for r in rows if r['status']=='passed')),3),'reply_rate':round(rep/cont,3) if cont else None,
            'weeks':list(weeks.values())[::-1]}
def gem_approve(r):
    d=r['data']; d['handle']=r['handle']
    gid,how=gemapi.ensure_candidate(d)
    projs=[CFG['outreach_project_id']]+([CFG['singapore_project_id']] if d.get('region')=='Singapore' else [CFG['us_project_id']])
    prior=set((d.get('gem_prior') or {}).get('project_ids') or [])
    if how=='existing':
        g=gemapi.lookup_handle(r['handle']); prior|=set((g or {}).get('project_ids') or [])
    added=[]
    for p in projs:
        if p in prior: continue
        gemapi.add_to_project(p,[gid]); added.append(p)
    enrolled=None
    if ENABLE_SEQUENCE_ENROLL: enrolled='unsupported_by_gem_public_api'
    return gid,{'created':how=='created','added_projects':added,'all_projects':projs,'enrolled':enrolled}
def gem_unapprove(r):
    gp=r['gem_projects'] or {}
    for p in (gp.get('added_projects') if isinstance(gp,dict) else []) or []:
        gemapi.remove_from_project(p,[r['gem_id']])
def refresh_outreach(c,handles=None):
    n=0
    for r in store.all_rows(c):
        if r['status'] not in('approved','resurface') or not r['gem_id']: continue
        if handles and r['handle'] not in handles: continue
        o=gemapi.outreach_summary(r['gem_id'])
        if o is None: o={**(r['outreach'] or {}),'source':(r['outreach'] or {}).get('source') or 'awaiting gmail sync','gem_events':'unavailable'}
        c.execute('update candidates set outreach=?,outreach_checked_at=? where handle=?',(json.dumps(o),int(time.time()),r['handle'])); n+=1
    c.commit()
    import add_batch; rs=add_batch.resurface(c)
    return n,rs
HTML=open(os.path.join(ROOT,'web','index.html')).read()
LOGIN=open(os.path.join(ROOT,'web','login.html')).read()
class H(BaseHTTPRequestHandler):
    server_version='xavi'
    def log_message(self,fmt,*a): sys.stderr.write('%s %s\n'%(time.strftime('%H:%M:%S'),fmt%a))
    def authed(self):
        if NO_AUTH: return True
        ck=http.cookies.SimpleCookie(self.headers.get('Cookie',''))
        return 'xr' in ck and valid(ck['xr'].value)
    def send(self,code,body,ctype='application/json',extra=None):
        b=body if isinstance(body,bytes) else (body.encode() if isinstance(body,str) else json.dumps(body).encode())
        self.send_response(code); self.send_header('Content-Type',ctype+'; charset=utf-8'); self.send_header('Content-Length',str(len(b)))
        self.send_header('Cache-Control','no-store'); self.send_header('X-Frame-Options','DENY'); self.send_header('Referrer-Policy','no-referrer')
        for k,v in (extra or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(b)
    def body(self):
        n=int(self.headers.get('Content-Length') or 0); raw=self.rfile.read(n) if n else b''
        if 'json' in (self.headers.get('Content-Type') or ''): return json.loads(raw or b'{}')
        return {k:v[0] for k,v in urllib.parse.parse_qs(raw.decode()).items()}
    def admin(self):
        a=self.headers.get('Authorization','')
        return a.startswith('Bearer ') and hmac.compare_digest(a[7:].strip(),ADMIN)
    def do_admin(self,method,path):
        if not self.admin(): time.sleep(1); return self.send(401,{'error':'admin auth'})
        b=self.body() if method=='POST' else {}
        with LOCK:
            c=store.conn()
            if path=='/api/admin/add_batch':
                import add_batch; r=add_batch.add_items(c,b.get('items') or [],b.get('batch'),bool(b.get('gem_check',True)),bool(b.get('dry_run')))
                t=learn_core.learn(); self._rescore(c,t); return self.send(200,r)
            if path=='/api/admin/import':
                n=c.execute('select count(*) from candidates').fetchone()[0]
                if n and not b.get('force'): return self.send(409,{'error':f'db has {n} rows; pass force:true to merge'})
                k=0
                for r in b.get('candidates') or []:
                    c.execute('insert or replace into candidates(handle,data,batch,added_at,fit,status,decided_at,reasons,gem_id,gem_projects,outreach,outreach_checked_at) values(?,?,?,?,?,?,?,?,?,?,?,?)',
                      (r['handle'],json.dumps(r['data']),r.get('batch'),r.get('added_at'),r.get('fit'),r.get('status','queue'),r.get('decided_at'),json.dumps(r['reasons']) if r.get('reasons') is not None else None,
                       r.get('gem_id'),json.dumps(r['gem_projects']) if r.get('gem_projects') else None,json.dumps(r['outreach']) if r.get('outreach') else None,r.get('outreach_checked_at'))); k+=1
                for d in b.get('decisions') or []:
                    c.execute('insert into decisions(handle,decision,reasons,features,fit,ts,undone,batch) values(?,?,?,?,?,?,?,?)',(d['handle'],d['decision'],d.get('reasons'),d.get('features'),d.get('fit'),d['ts'],d.get('undone',0),d.get('batch')))
                c.commit(); t=learn_core.learn(); self._rescore(c,t)
                return self.send(200,{'imported':k,'decisions':len(b.get('decisions') or []),'total':c.execute('select count(*) from candidates').fetchone()[0]})
            if path=='/api/admin/outreach':
                import add_batch; k=0
                for h,o in (b.get('status') or {}).items():
                    r=store.get(c,h)
                    if r: c.execute('update candidates set outreach=?,outreach_checked_at=? where handle=?',(json.dumps({**(r['outreach'] or {}),**o}),int(time.time()),h)); k+=1
                c.commit(); return self.send(200,{'updated':k,'resurfaced':add_batch.resurface(c)})
            if path=='/api/admin/rescore':   # re-learn + rescore undecided people (decisions untouched)
                before={x['handle']:x['fit'] for x in store.all_rows(c) if x['status'] in('queue','resurface')}
                t=learn_core.learn(); self._rescore(c,t); after=store.all_rows(c)
                und=[x for x in after if x['status'] in('queue','resurface')]
                return self.send(200,{'undecided':len(und),'demoted':[{'name':x['data'].get('name'),'from':before.get(x['handle']),'to':x['fit'],'why':fit.standing_reasons(x['data'])} for x in und if fit.standing_reasons(x['data'])],
                                      'top':[{'name':x['data'].get('name'),'fit':x['fit']} for x in sorted(und,key=lambda x:-(x['fit'] or 0))[:5]],'standing':t.get('standing_priors')})
            if path=='/api/admin/dump':
                return self.send(200,{'candidates':store.all_rows(c),'decisions':[dict(x) for x in c.execute('select * from decisions')],'taste':fit.load_taste()})
            if path=='/api/admin/export_for_sync':
                rows=[r for r in store.all_rows(c) if r['status'] in('approved','resurface') and r['gem_id']]; out=[]
                for i in range(0,len(rows),20):
                    st,d,_=gemapi.req('GET','v0/candidates',{'candidate_ids':','.join(r['gem_id'] for r in rows[i:i+20]),'page_size':20})
                    by={x['id']:x for x in d} if isinstance(d,list) else {}
                    for r in rows[i:i+20]: out.append({'handle':r['handle'],'name':r['data'].get('name'),'gem_id':r['gem_id'],'emails':[e['email_address'] for e in (by.get(r['gem_id'],{}).get('emails') or [])],'approved_at':r['decided_at'],'outreach':r['outreach']})
                return self.send(200,out)
        return self.send(404,{'error':'not found'})
    def do_GET(self):
        u=urllib.parse.urlparse(self.path)
        if u.path=='/healthz': return self.send(200,{'ok':True})
        if u.path.startswith('/api/admin/'): return self.do_admin('GET',u.path)
        if not self.authed():
            if u.path.startswith('/api/'): return self.send(401,{'error':'auth'})
            return self.send(200,LOGIN.replace('{{ERR}}',''),'text/html')
        if u.path in('/','/index.html'): return self.send(200,HTML,'text/html')
        if u.path=='/api/state':
            with LOCK:
                c=store.conn(); rows=store.all_rows(c)
                return self.send(200,{'candidates':[public(r) for r in rows],'stats':stats(c,rows),'taste':fit.load_taste(),'config':{k:CFG[k] for k in('outreach_project_url','us_project_url','singapore_project_url')},
                                      'sequence_enroll_supported':False,'chips':CFG['chips']})
        return self.send(404,{'error':'not found'})
    def do_POST(self):
        u=urllib.parse.urlparse(self.path)
        if u.path.startswith('/api/admin/'): return self.do_admin('POST',u.path)
        if u.path=='/login':
            b=self.body()
            if hmac.compare_digest((b.get('password') or '').strip(),PW):
                tok=sign(str(int(time.time())+60*86400))
                return self.send(303,'',extra={'Location':'/','Set-Cookie':f'xr={tok}; HttpOnly; SameSite=Lax; Path=/; Max-Age={60*86400}'+('; Secure' if self.headers.get('X-Forwarded-Proto')=='https' else '')})
            time.sleep(1); return self.send(200,LOGIN.replace('{{ERR}}','That password didn’t work.'),'text/html')
        if u.path=='/logout': return self.send(303,'',extra={'Location':'/','Set-Cookie':'xr=; Path=/; Max-Age=0'})
        if not self.authed(): return self.send(401,{'error':'auth'})
        b=self.body(); h=b.get('handle')
        try:
            with LOCK:
                c=store.conn(); r=store.get(c,h) if h else None
                if u.path=='/api/decide':
                    if not r: return self.send(404,{'error':'unknown'})
                    dec=b['decision']; now=int(time.time())
                    reasons=b.get('reasons') if b.get('reasons') is not None else (r['reasons'] or [])  # free-text note (list of strings); falls back to a draft note saved before deciding
                    reasons=[x.strip()[:1000] for x in reasons if isinstance(x,str) and x.strip()]
                    gid=r['gem_id']; gp=r['gem_projects']
                    if dec=='approve' and r['status']!='approved':
                        gid,gp=gem_approve(r)
                    c.execute('update candidates set status=?,decided_at=?,reasons=?,gem_id=?,gem_projects=? where handle=?',
                              ('approved' if dec=='approve' else 'passed',now,json.dumps(reasons),gid,json.dumps(gp) if gp else None,h))
                    c.execute('insert into decisions(handle,decision,reasons,features,fit,ts,batch) values(?,?,?,?,?,?,?)',(h,dec,json.dumps(reasons),json.dumps(fit.features(r['data'])),r['fit'],now,r['batch']))
                    c.commit(); t=learn_core.learn(); self._rescore(c,t)
                    return self.send(200,{'ok':True,'candidate':public(store.get(c,h)),'taste':t})
                if u.path=='/api/note':   # draft note typed before deciding
                    if not r: return self.send(404,{'error':'unknown'})
                    n=(b.get('note') or '').strip()[:1000]
                    c.execute('update candidates set reasons=? where handle=?',(json.dumps([n]) if n else None,h)); c.commit()
                    return self.send(200,{'ok':True,'candidate':public(store.get(c,h))})
                if u.path=='/api/reasons':
                    c.execute('update candidates set reasons=? where handle=?',(json.dumps(b.get('reasons') or []),h))
                    c.execute('update decisions set reasons=? where id=(select max(id) from decisions where handle=? and undone=0)',(json.dumps(b.get('reasons') or []),h))
                    c.commit(); t=learn_core.learn(); return self.send(200,{'ok':True,'taste':t})
                if u.path in('/api/undo','/api/restore'):
                    if not r: return self.send(404,{'error':'unknown'})
                    if r['status']=='approved' and r['gem_id']: gem_unapprove(r)
                    c.execute("update candidates set status='queue',decided_at=null,gem_projects=null where handle=?",(h,))  # keep the note as a draft
                    c.execute('update decisions set undone=1 where handle=? and undone=0',(h,)); c.commit()
                    t=learn_core.learn(); self._rescore(c,t)
                    return self.send(200,{'ok':True,'candidate':public(store.get(c,h)),'taste':t})
                if u.path=='/api/refresh':
                    n,rs=refresh_outreach(c); return self.send(200,{'ok':True,'checked':n,'resurfaced':rs})
        except Exception as e:
            traceback.print_exc(); return self.send(500,{'error':str(e)[:300]})
        return self.send(404,{'error':'not found'})
    def _rescore(self,c,t):
        for x in store.all_rows(c):
            if x['status'] in('queue','resurface'): c.execute('update candidates set fit=? where handle=?',(fit.fit(x['data'],t),x['handle']))
        c.commit()
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--port',type=int,default=int(os.environ.get('PORT',8787))); ap.add_argument('--host',default='0.0.0.0'); a=ap.parse_args()
    print(f'xavi review on :{a.port}',flush=True); ThreadingHTTPServer((a.host,a.port),H).serve_forever()
