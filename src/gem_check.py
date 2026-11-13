import json,sys,os
sys.path.insert(0,'/workspace/xavi-review/lib'); import gemapi as g
pool=json.load(open('/workspace/xavi-review/src/pool.json'))
OUT='/workspace/xavi-review/src/gemcheck.json'; res=json.load(open(OUT)) if os.path.exists(OUT) else {}
for i,p in enumerate(pool):
    if p['handle'] in res: continue
    c=g.lookup_handle(p['handle'])
    r={'in_gem':bool(c)}
    if c:
        r['gem_id']=c['id']; r['project_ids']=c.get('project_ids') or []
        r.update(g.outreach_summary(c['id']) or {})
    res[p['handle']]=r; json.dump(res,open(OUT,'w'))
    if c: print(i,p['name'],r,flush=True)
print('done',len(res),sum(1 for v in res.values() if v['in_gem']),sum(1 for v in res.values() if v.get('contacted')))
