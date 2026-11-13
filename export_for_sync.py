#!/usr/bin/env python3
"""List approved candidates with their Gem emails for the weekly Gmail outreach sync. usage: export_for_sync.py [--remote [URL]]"""
import sys,os,json; R=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(R,'lib'))
if '--remote' in sys.argv:
    import remote; i=sys.argv.index('--remote'); url=sys.argv[i+1] if len(sys.argv)>i+1 else remote.default_url()
    print(json.dumps(remote.call(url,'/api/admin/export_for_sync'),indent=1)); sys.exit()
import store,gemapi
c=store.conn(); out=[]
rows=[r for r in store.all_rows(c) if r['status'] in('approved','resurface') and r['gem_id']]
for i in range(0,len(rows),20):
    s,d,_=gemapi.req('GET','v0/candidates',{'candidate_ids':','.join(r['gem_id'] for r in rows[i:i+20]),'page_size':20})
    by={x['id']:x for x in d} if isinstance(d,list) else {}
    for r in rows[i:i+20]:
        out.append({'handle':r['handle'],'name':r['data'].get('name'),'gem_id':r['gem_id'],'emails':[e['email_address'] for e in (by.get(r['gem_id'],{}).get('emails') or [])],'approved_at':r['decided_at']})
print(json.dumps(out,indent=1))
