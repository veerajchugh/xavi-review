"""Tiny client for the deployed site's admin API. Token: $XAVI_ADMIN_TOKEN or .admin_token (never printed)."""
import os,json,urllib.request
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def token():
    t=os.environ.get('XAVI_ADMIN_TOKEN')
    if not t:
        p=os.path.join(ROOT,'.admin_token'); t=open(p).read() if os.path.exists(p) else ''
    if not t.strip(): raise SystemExit('no admin token: set XAVI_ADMIN_TOKEN or create .admin_token')
    return t.strip()
def default_url(): return os.environ.get('XAVI_URL') or (open(os.path.join(ROOT,'.site_url')).read().strip() if os.path.exists(os.path.join(ROOT,'.site_url')) else None)
def call(base,path,body=None,method=None):
    data=json.dumps(body).encode() if body is not None else None
    r=urllib.request.Request(base.rstrip('/')+path,data=data,method=method or ('POST' if data else 'GET'),
        headers={'Authorization':'Bearer '+token(),'Content-Type':'application/json','User-Agent':'xavi-admin'})
    with urllib.request.urlopen(r,timeout=600) as x: return json.loads(x.read())
