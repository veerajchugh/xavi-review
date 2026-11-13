#!/usr/bin/env python3
"""Turn taste.json into next week's Crustdata pulls (over-source what Veeraj approves, under-source what he passes).
usage: python3 sourcing_plan.py [--remote [URL]] > plan.json   (each entry = `inputs` for src/crust_pull.js via Crustdata execute)
"""
import sys,os,json; R=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(R,'lib'))
import fit,store
if '--remote' in sys.argv:   # read taste + everyone already seen from the deployed site
    import remote; i=sys.argv.index('--remote'); url=sys.argv[i+1] if len(sys.argv)>i+1 else remote.default_url()
    d=remote.call(url,'/api/admin/dump'); t=d.get('taste') or {}; rows=d['candidates']
else:
    t=fit.load_taste(); rows=store.all_rows(store.conn())
w=t.get('weights',{}); conf=t.get('confidence',0)
seen=[r['data'].get('linkedin_url') for r in rows if r['data'].get('linkedin_url')]
g=lambda k,v:w.get(k,{}).get(v,0)
target=int(os.environ.get('WEEKLY_TARGET',100))
sg_share=t.get('sourcing',{}).get('region_split_singapore',0.2)
pulls=[]
# Singapore always broken out (visa-friendly)
pulls.append({'label':'singapore','country':'Singapore','pages':2,'extra':[]})
ca_pages=3+(1 if g('bay_area','yes')>0.3 else 0)-(1 if g('bay_area','yes')<-0.3 else 0)
pulls.append({'label':'california+github','country':'United States','pages':max(1,ca_pages),'extra':[['dev_platform_profiles.all_languages','is_not_null',''],['basic_profile.location.state','=','California']]})
pulls.append({'label':'rest of us+github','country':'United States','pages':2 if g('bay_area','no')>=-0.3 else 1,'extra':[['dev_platform_profiles.all_languages','is_not_null',''],['basic_profile.location.state','!=','California']]})
if g('hardware','yes')>0.2 or conf<0.2:
    pulls.append({'label':'hardware founding engineers','country':'United States','pages':1+(g('hardware','yes')>0.5),'extra':[['experience.employment_details.title','(.)','firmware embedded hardware robotics']]})
if g('github','no')>-0.5:
    pulls.append({'label':'bay area, no github filter','country':'United States','pages':1,'extra':[['basic_profile.location.state','=','California']]})
for p in pulls: p['exclude']=seen[-2000:]
print(json.dumps({'target':target,'singapore_share':sg_share,'over_source':t.get('sourcing',{}).get('over_source',[]),'down_rank':t.get('sourcing',{}).get('down_rank',[]),'pulls':pulls},indent=1)[:200000])
