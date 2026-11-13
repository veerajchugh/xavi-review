import json,sys,os,concurrent.futures as cf
sys.path.insert(0,'/workspace/xavi-review/lib'); import gemapi as g, fit
pool=[p for p in json.load(open('pool.json')) if not (fit.buzzy(p) or fit.recent_raise(p)) and fit.discipline(p) not in('robotics','electrical/hardware')]
def one(p):
    c=g.lookup_handle(p['handle']); r={'in_gem':bool(c)}
    if c: r.update(gem_id=c['id'],project_ids=c.get('project_ids') or [],emails=[e.get('email_address') for e in (c.get('emails') or []) if e.get('email_address')])
    return p['handle'],r
with cf.ThreadPoolExecutor(4) as ex: res=dict(ex.map(one,pool))
json.dump(res,open('gemcheck.json','w'))
print('checked',len(res),'in gem',sum(v['in_gem'] for v in res.values()),'with emails',sum(1 for v in res.values() if v.get('emails')))
