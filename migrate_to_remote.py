#!/usr/bin/env python3
"""Copy the local queue + decisions into the deployed site's disk (one-time, or --force to merge).
usage: python3 migrate_to_remote.py [URL] [--force]"""
import sys,os,json; R=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(R,'lib'))
import store,remote
args=[a for a in sys.argv[1:] if not a.startswith('--')]; url=args[0] if args else remote.default_url()
c=store.conn()
body={'candidates':store.all_rows(c),'decisions':[dict(x) for x in c.execute('select * from decisions')],'force':'--force' in sys.argv}
print(json.dumps(remote.call(url,'/api/admin/import',body)))
