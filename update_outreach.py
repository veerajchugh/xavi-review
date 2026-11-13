#!/usr/bin/env python3
"""Write outreach status for approved candidates (Gem's events API is 403/deprecated, so the weekly routine
derives it from Gmail: SENT mail to the candidate's Gem emails = contacted; inbound mail or a Gem reply notification = replied).
usage: python3 update_outreach.py status.json [--remote [URL]]
status.json: {"<linkedin handle>": {"contacted":true,"touches":2,"last_touch":1784000000,"replied":false,"reply_status":null,"source":"gmail"}}
Re-surfaces approved people contacted 60+ days ago with no reply."""
import sys,os,json,time; R=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(R,'lib')); sys.path.insert(0,R)
data=json.load(open(sys.argv[1]))
if '--remote' in sys.argv:
    import remote; i=sys.argv.index('--remote'); url=sys.argv[i+1] if len(sys.argv)>i+1 else remote.default_url()
    print(json.dumps(remote.call(url,'/api/admin/outreach',{'status':data}))); sys.exit()
import store,add_batch
c=store.conn(); n=0
for h,o in data.items():
    r=store.get(c,h)
    if not r: continue
    c.execute('update candidates set outreach=?,outreach_checked_at=? where handle=?',(json.dumps({**(r['outreach'] or {}),**o}),int(time.time()),h)); n+=1
c.commit(); print(json.dumps({'updated':n,'resurfaced':add_batch.resurface(c)}))
