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
# Standing rule (Nov 13, 2026): software people with a dash of firmware. No robotics/EE pull any more.
FW=[['OR',[['experience.employment_details.title','(.)','firmware'],['experience.employment_details.title','(.)','embedded']]]]
pulls.append({'label':'software + firmware/embedded (US)','country':'United States','pages':1,'extra':FW})
pulls.append({'label':'software + firmware/embedded (Singapore)','country':'Singapore','pages':1,'extra':FW})
if g('github','no')>-0.5:
    pulls.append({'label':'bay area, no github filter','country':'United States','pages':1,'extra':[['basic_profile.location.state','=','California']]})
EXCLUDE_TITLES=['robotics','robot','electrical','mechanical','hardware engineer','mechatronics','controls engineer']
for p in pulls: p['exclude']=seen[-2000:]; p['exclude_titles']=EXCLUDE_TITLES; p['exclude_companies']=fit._CFG.get('hot_companies',[])
print(json.dumps({'target':target,'singapore_share':sg_share,'over_source':t.get('sourcing',{}).get('over_source',[]),'down_rank':t.get('sourcing',{}).get('down_rank',[]),'standing_rules':fit.STANDING_NOTES,'pulls':pulls},indent=1)[:200000])
