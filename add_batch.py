#!/usr/bin/env python3
"""Append a weekly batch of candidates to the review queue (local DB or the deployed site).

usage:
  python3 add_batch.py candidates.json [--batch 2026-W47] [--no-gem-check] [--dry-run]           # local DB
  python3 add_batch.py candidates.json --remote https://xavi-review.onrender.com                 # deployed site
      (--remote with no URL uses $XAVI_URL or .site_url; admin token from $XAVI_ADMIN_TOKEN or .admin_token)

candidates.json: list of objects with at least name and linkedin_url (from Crustdata/Juicebox only, never guessed).
Optional: region, current_title, current_company, location, total_yoe, founding_role, founding_company,
founding_tenure_months, founding_hc, founding_current, github_url, personal_site, hardware_signal, hardware_note,
why, photo_url, yc, bay_area, jobs, outreach_hint {contacted,last_touch,replied}.

Skips anyone already queued or decided (passes are permanent), and anyone Gem/Gmail shows was contacted in the
last 60 days or replied. Scores with taste.json so the queue sorts by learned fit. Re-surfaces approved people
contacted 60+ days ago with no reply.
"""
import sys,os,json,time,re,argparse,datetime
ROOT=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(ROOT,'lib'))
import store,fit,gemapi
DAY=86400
def handle(u):
    m=re.search(r'linkedin\.com/in/([^/?#]+)',u or '',re.I); return m.group(1).strip('/').lower() if m else None
def _secs(t): return t/1000 if t and t>1e11 else t
def resurface(c,now=None):
    now=now or time.time(); n=0
    for r in store.all_rows(c):
        o=r.get('outreach') or {}
        if r['status']=='approved' and o.get('contacted') and not o.get('replied') and o.get('last_touch') and now-_secs(o['last_touch'])>60*DAY:
            c.execute("update candidates set status='resurface' where handle=?",(r['handle'],)); n+=1
    c.commit(); return n
def add_items(c,items,batch=None,gem_check=True,dry_run=False):
    batch=batch or datetime.date.today().strftime('%G-W%V')
    taste=fit.load_taste(); now=time.time()
    S={'batch':batch,'added':0,'skipped_already_in_queue_or_decided':0,'skipped_gem_contacted_60d_or_replied':0,'skipped_no_linkedin':0}
    for it in items:
        it=dict(it); h=it.get('handle') or handle(it.get('linkedin_url'))
        if not h or 'linkedin.com/in/' not in (it.get('linkedin_url') or ''): S['skipped_no_linkedin']+=1; continue
        it['handle']=h
        if store.get(c,h): S['skipped_already_in_queue_or_decided']+=1; continue
        hint={k:v for k,v in (it.get('outreach_hint') or {}).items() if v}
        if gem_check:
            g=gemapi.lookup_handle(h)
            if g:
                o={**(gemapi.outreach_summary(g['id']) or {}),**hint}   # Gem events API is 403/deprecated; Gmail hint fills in
                it['gem_prior']={'gem_id':g['id'],'project_ids':g.get('project_ids') or [],**o}
        o=it.get('gem_prior') or hint
        lt=_secs(o.get('last_touch'))
        if o.get('replied') or (lt and now-lt<60*DAY): S['skipped_gem_contacted_60d_or_replied']+=1; continue
        f=fit.fit(it,taste)
        if not dry_run:
            c.execute('insert into candidates(handle,data,batch,added_at,fit,status) values(?,?,?,?,?,?)',(h,json.dumps(it),batch,int(now),f,'queue'))
        S['added']+=1
    c.commit(); S['resurfaced_after_60d']=0 if dry_run else resurface(c)
    S['queue_size']=c.execute("select count(*) from candidates where status in ('queue','resurface')").fetchone()[0]
    S['taste_decisions']=taste.get('n_decisions',0); S['over_source']=taste.get('sourcing',{}).get('over_source',[])
    return S
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--batch'); ap.add_argument('--no-gem-check',action='store_true'); ap.add_argument('--dry-run',action='store_true')
    ap.add_argument('--remote',nargs='?',const='DEFAULT',help='push to the deployed site instead of the local DB')
    a=ap.parse_args(); items=json.load(open(a.file))
    if a.remote:
        import remote; url=remote.default_url() if a.remote=='DEFAULT' else a.remote
        if not url: raise SystemExit('no URL: pass --remote URL or set XAVI_URL')
        print(json.dumps(remote.call(url,'/api/admin/add_batch',{'items':items,'batch':a.batch,'gem_check':not a.no_gem_check,'dry_run':a.dry_run}),indent=1)); return
    print(json.dumps(add_items(store.conn(),items,a.batch,not a.no_gem_check,a.dry_run),indent=1))
if __name__=='__main__': main()
