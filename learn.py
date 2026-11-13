#!/usr/bin/env python3
"""Recompute taste.json from logged thumbs and re-score the queue. Usage: python3 learn.py"""
import sys,os,json; sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'lib'))
import learn_core,fit,store
t=learn_core.learn()
c=store.conn()
for r in store.all_rows(c):
    c.execute('update candidates set fit=? where handle=?',(fit.fit(r['data'],t),r['handle']))
c.commit()
print(json.dumps({k:t[k] for k in('n_decisions','approve_rate','confidence','likes','passes_on','sourcing')},indent=1))
