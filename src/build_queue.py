"""Merge Crustdata pool + GitHub verification + Gem check into the 100-person review queue."""
import json,re,csv,sys,os
sys.path.insert(0,'/workspace/xavi-review/lib'); import fit
S='/workspace/xavi-review/src/'
pool=json.load(open(S+'pool.json')); gh=json.load(open(S+'gh.json')) if os.path.exists(S+'gh.json') else {}
gc=json.load(open(S+'gemcheck.json')); gm=json.load(open(S+'gmail_check.json')) if os.path.exists(S+'gmail_check.json') else {}
PN=json.load(open(S+'project_names.json'))
HWW=re.compile(r'(firmware|embedded|hardware|electrical engineer\b|robotics?\b|fpga|pcb|asic|mechatronics|avionics|\biot\b|sensors?\b|camera|drones?\b|mechanical engineer|controls engineer|silicon validation|rtl\b|verilog)',re.I)
NOTHW=re.compile(r'tutor|teaching|\bta\b|club|student|robocup',re.I)
HWIND=re.compile(r'semiconductor|electronic|robot|appliances|aviation|aerospace|automotive|medical equipment|machinery|computer hardware',re.I)
def hwnote(p):
    for j in p['jobs']:
        t=j.get('t') or ''
        if NOTHW.search(t): continue
        if HWW.search(t) or re.search(r'robotics|hardware|devices|electronics',j.get('c') or '',re.I): return f"{t} at {j.get('c')}"
    m=HWW.search(p.get('headline') or ''); return m.group(1).lower()+' in headline' if m else None
norm6=lambda l: re.sub(r'[^a-z]','',(l or '').split(',')[0].lower())[:6]
CON=json.load(open(S+'contribs.json')) if os.path.exists(S+'contribs.json') else {}
out=[]
for p in pool:
    h=p['handle']; g=(gh.get(h) or {}).get('match'); c=dict(p)
    if g and g.get('why')=='company' and fit.BIGTECH.search(g.get('company') or '') and not (g.get('location') and norm6(p['location']) in re.sub(r'[^a-z]','',g['location'].lower())):
        g=None  # company-only match on a big employer with a different location is too weak
    if g:
        c.update(github_url=g['url'],gh_repos=g.get('repos'),gh_followers=g.get('followers'),gh_contribs=CON.get(g['login']),gh_pinned=g.get('pinned'),gh_bio=g.get('bio'),gh_verified=g.get('why'))
        w=g.get('website')
        cos6={re.sub(r'[^a-z]','',(j.get('c') or '').lower()) for j in p['jobs']}
        dom=re.sub(r'^https?://(www\.)?','',w or '').split('/')[0].split('.')[0].lower()
        if w and not re.search(r'linkedin|twitter|x\.com|github\.com|medium\.com|instagram|youtube|linktr\.ee',w,re.I) and not any(dom and len(dom)>3 and dom in x for x in cos6): c['personal_site']=w if w.startswith('http') else 'https://'+w
    else: c['github_url']=None
    q=gc.get(h) or {}
    if q.get('in_gem'):
        c['gem_prior']={'gem_id':q['gem_id'],'project_ids':q.get('project_ids',[]),'projects':[PN.get(x,x) for x in q.get('project_ids',[])]}
        mm=gm.get(h) or {}
        if mm.get('contacted') or mm.get('replied'): c['gem_prior'].update(mm); c['_skip']='contacted per gmail'
    c['hardware_note']=hwnote(p); c['hardware_signal']=bool(c['hardware_note'])
    c['features']=fit.features(c); c['fit']=fit.fit(c,{})
    # why line
    t=c['founding_tenure_months']; stint=f"{t} months" if t<24 else f"{round(t/12,1):g} years"
    size=f" ({c['founding_hc']} people)" if (c.get('founding_hc') or 0)>1 else ''
    s1=f"{c['founding_role']} at {c['founding_company']}{size} for {stint}{', still there' if c['founding_current'] else ''}."
    parts=[s1]
    if g:
        pin=[x for x in (g.get('pinned') or []) if x][:3]
        gb=[f"{g['repos']} repos"] if g.get('repos') else []
        if c.get('gh_contribs') and c['gh_contribs']!='0': gb.append(f"{c['gh_contribs']} contributions this year")
        parts.append('GitHub: '+', '.join(gb)+(f"; pinned {', '.join(pin)}" if pin else '')+'.')
    if c.get('personal_site'): parts.append('Has a personal site.')
    if c.get('hardware_note'): parts.append(f"Hardware: {c['hardware_note']}.")
    prev=[j for j in p['jobs'] if j.get('c') and j.get('c')!=c['founding_company'] and not re.search('intern|student|teaching|assistant',j.get('t') or '',re.I) and j.get('c')!=c.get('current_company')]
    big=[j for j in prev if (j.get('hc') or 0)>=1000 and re.search(r'engineer|developer|scientist|swe|programmer|architect',j.get('t') or '',re.I)]
    if big: parts.append(f"Before: {big[0]['t']} at {big[0]['c']}.")
    c['why']=' '.join(parts)
    out.append(c)
ok=[c for c in out if not c.get('_skip')]
ok.sort(key=lambda c:-c['fit'])
sg=[c for c in ok if c['region']=='Singapore']; us=[c for c in ok if c['region']!='Singapore']
NSG=min(len(sg),int(sys.argv[1]) if len(sys.argv)>1 else 22)
pick=sg[:NSG]+us[:100-NSG]
pick.sort(key=lambda c:-c['fit'])
for c in pick: c.pop('_skip',None)
json.dump(pick,open('/workspace/xavi_queue.json','w'),indent=1)
cols=['name','linkedin_url','region','current_title','current_company','location','total_yoe','founding_role','founding_company','founding_tenure_months','founding_hc','github_url','gh_verified','personal_site','hardware_signal','hardware_note','yc','bay_area','fit','why','photo_url']
with open('/workspace/xavi_queue.csv','w',newline='') as f:
    w=csv.DictWriter(f,cols,extrasaction='ignore'); w.writeheader(); [w.writerow(c) for c in pick]
import collections
print(len(pick),collections.Counter(c['region'] for c in pick),'gh',sum(1 for c in pick if c['github_url']),'site',sum(1 for c in pick if c.get('personal_site')),'hw',sum(1 for c in pick if c['hardware_signal']),'ingem',sum(1 for c in pick if c.get('gem_prior')),'skipped',sum(1 for c in out if c.get('_skip')),'gh_checked',len(gh))
