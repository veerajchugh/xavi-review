import json,re,csv,datetime
raw=[]
for f,reg in [('w47/raw_sg.json','Singapore'),('w47/raw_ca_gh.json','US'),('w47/raw_us_gh.json','US'),('w47/raw_fw_us.json','US'),('w47/raw_fw_sg.json','Singapore')]:
    for p in json.load(open(f))['out']: p['region']=reg; raw.append(p)
seen=set()
def h(u): 
    m=re.search(r'linkedin\.com/in/([^/?#]+)',u or '',re.I); return m.group(1).lower().strip('/') if m else None
for r in csv.DictReader(open('/workspace/xavi_candidates.csv')): seen.add(h(r['linkedin_url'])); seen.add(r['name'].lower())
for r in json.load(open('/tmp/dump.json'))['candidates']: seen.add(r['handle']); seen.add((r['data'].get('name') or '').lower())
FT=re.compile(r'\bfounding\b.*\b(engineer|developer|swe|engineering|programmer)\b|\bfounding\s+(software|hardware|firmware|full[- ]?stack|backend|frontend|ml|ai|product|platform|member of technical staff)',re.I)
BAD=re.compile(r'\b(founder|co-?founder|ceo|cto|chief|owner|president|partner)\b',re.I)
HW=re.compile(r'firmware|embedded|hardware|electrical|robot|fpga|pcb|asic|silicon|mechatron|avionics|iot|sensor|camera|optic|drone|device',re.I)
HWIND=re.compile(r'semiconductor|electronic|robot|appliances|aviation|aerospace|automotive|medical equipment|machinery|computer hardware',re.I)
INTERN=re.compile(r'intern|student|teaching|research assistant|tutor|volunteer',re.I)
now=datetime.date(2026,11,13)
def ym(s):
    try: y,m=s.split('-'); return int(y)*12+int(m)
    except: return None
NOW=now.year*12+now.month
out=[];drop={};dupseen=set()
for p in raw:
    hd=h(p.get('url'))
    if hd in dupseen: continue
    dupseen.add(hd)
    if not hd or hd in seen or (p['name'] or '').lower() in seen: drop['seen']=drop.get('seen',0)+1; continue
    jobs=[dict(j,cur=True) for j in p['cur']]+[dict(j,cur=False) for j in p['past']]
    if any(BAD.search(j['t'] or '') for j in p['cur']): drop['curfounder']=drop.get('curfounder',0)+1; continue
    fj=[j for j in jobs if FT.search(j['t'] or '')]
    if not fj: drop['notitle']=drop.get('notitle',0)+1; continue
    for j in fj:
        s=ym(j['s']); e=ym(j['e']) if j['e'] else NOW
        j['mo']=(e-s+1) if s else 0
    best=max(fj,key=lambda j:j['mo'])
    if best['mo']<6: drop['short']=drop.get('short',0)+1; continue
    starts=[ym(j['s']) for j in jobs if ym(j['s']) and not INTERN.search(j['t'] or '')]
    yoe=round((NOW-min(starts))/12,1) if starts else None
    if yoe is not None and (yoe<1.8 or yoe>8.5): drop['yoe']=drop.get('yoe',0)+1; continue
    hwtxt=' '.join((j['t'] or '')+' '+(j['c'] or '') for j in jobs)+' '+(p.get('head') or '')
    hw=bool(HW.search(hwtxt)) or any(HWIND.search(j.get('ind') or '') for j in jobs)
    loc=p.get('loc') or ''
    bay=bool(re.search(r'san francisco|bay area|palo alto|mountain view|san jose|oakland|berkeley|menlo|sunnyvale|redwood|santa clara|cupertino|san mateo|fremont|burlingame|south san',loc,re.I))
    yc=bool(re.search(r'\bYC\b|Y Combinator',(p.get('head') or ''),re.I))
    cur=p['cur'][0] if p['cur'] else None
    fwsig=bool(re.search(r'firmware|embedded',hwtxt,re.I))
    out.append(dict(cid=p['id'],name=p['name'],linkedin_url=p['url'],handle=hd,region=p['region'],headline=p.get('head'),
      current_title=cur['t'] if cur else None,current_company=cur['c'] if cur else None,current_hc=cur['hc'] if cur else None,current_cid=cur.get('cid') if cur else None,firmware_signal=fwsig,
      location=loc,bay_area=bay,total_yoe=yoe,founding_role=best['t'],founding_company=best['c'],founding_tenure_months=best['mo'],
      founding_current=best['cur'],founding_hc=best['hc'],founding_industry=best.get('ind'),github_url=p.get('gh'),hardware_signal=hw,yc=yc,
      photo_url=p.get('pic') or None,jobs=[{k:j.get(k) for k in('t','c','s','e','hc','ind','cid')} for j in jobs[:6]]))
print(len(raw),drop,len(out))
import collections;print(collections.Counter(o['region'] for o in out), sum(1 for o in out if o['github_url']), sum(o['hardware_signal'] for o in out))
json.dump(out,open('w47/pool.json','w'),indent=0)
