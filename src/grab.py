import sys,re,json
p=sys.argv[1]; t=open(p).read()
m=re.search(r'Full text: (\S+?\.txt)',t)
if m: t=open(m.group(1)).read()
i=t.index('{"ok"'); d,_=json.JSONDecoder().raw_decode(t[i:])
v=d['value']; json.dump(v,open(sys.argv[2],'w')); print(v.get('total'),v.get('n'),v.get('cursor'),d.get('credits_remaining'), v.get('err'))
