import json
pool=json.load(open('pool.json'))
for p in pool:
    s=min(p['founding_tenure_months'],24)/24*30
    s+=12 if p['hardware_signal'] else 0
    s+=10 if p['bay_area'] else 0
    s+=25 if p['region']=='Singapore' else 0
    y=p['total_yoe'] or 0; s+=10 if 3<=y<=7 else 4
    s+=6 if p['yc'] else 0
    s+=5 if (p['founding_hc'] or 999)<=50 else 0
    p['pre']=round(s,1)
json.dump(pool,open('pool.json','w'))
