import json,re,time,urllib.request,os
q=json.load(open('/workspace/xavi_queue.json')); out=json.load(open('contribs.json')) if os.path.exists('contribs.json') else {}
for c in q:
    u=c.get('github_url')
    if not u: continue
    l=u.rstrip('/').split('/')[-1]
    if l in out: continue
    try:
        t=urllib.request.urlopen(urllib.request.Request(f'https://github.com/users/{l}/contributions',headers={'User-Agent':'Mozilla/5.0'}),timeout=30).read().decode()
        m=re.search(r'([\d,]+)\s+contributions?\s+in the last year',t); out[l]=m.group(1) if m else None
    except Exception as e: out[l]=None
    time.sleep(0.5)
json.dump(out,open('contribs.json','w')); print(len(out),sum(1 for v in out.values() if v))
