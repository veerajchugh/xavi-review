"""Learn which candidate features predict Veeraj's approvals. Writes taste.json."""
import json,math,time,collections,os,sys,re
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import fit as F, store as S
CHIP_MAP={  # reason chip -> (feature, value, direction)
 'No side projects':[('github','no',-1),('personal_site','no',-1)],'Too senior':[('yoe','6-8',-1)],'Too junior':[('yoe','2-3',-1)],
 'Weak company':[('company_stage','large (200+)',-1)],'Short stint':[('founding_tenure','6-11 mo',-1)],'Wrong domain':[],
 'Great GitHub':[('github_quality','strong',1),('github','yes',1)],'Hardware':[('hardware','yes',1)],'Strong founding stint':[('founding_tenure','24+ mo',1),('founding_tenure','12-23 mo',1)],
 'Bay Area':[('bay_area','yes',1)],'Singapore':[('region','Singapore',1)],'Great company':[]}
# Free-text notes -> traits. Each rule: (label, regex, [(feature, value_if_affirmed)]).
# A note on an approve pushes the trait up, on a pass pushes it down. "no/not/lacks X" flips yes<->no.
NOTE_RULES=[
 ('side projects / GitHub',r'github|side[- ]?projects?|portfolio|personal (?:site|website)|\brepos?\b|open[- ]source|builds? (?:stuff|things)',[('github','yes'),('personal_site','yes')]),
 ('too senior',r'too senior|over-?qualified|too experienced|too expensive|too old',[('yoe','6-8')]),
 ('too junior',r'too junior|too green|inexperienced|not enough experience|too new|too early in career',[('yoe','2-3')]),
 ('hardware',r'hardware|embedded|firmware|robot\w*|electrical|\bpcb\b|camera|optics|sensor',[('hardware','yes')]),
 ('short founding stint',r'short (?:stint|tenure|time)|not long enough|left (?:too )?quick\w*|job[- ]?hop\w*',[('founding_tenure','6-11 mo')]),
 ('long founding stint',r'long (?:stint|tenure)|stayed|strong founding|founding (?:stint|experience)|built (?:it )?from (?:zero|scratch)|0 ?(?:to|->|-) ?1',[('founding_tenure','24+ mo'),('founding_tenure','12-23 mo')]),
 ('big company',r'big ?co\b|big tech|large company|corporate|faang|bureaucra',[('employer_type','big tech'),('company_stage','large (200+)')]),
 ('Bay Area',r'bay area|\bsf\b|san francisco|silicon valley|palo alto|mountain view|\blocal\b',[('bay_area','yes')]),
 ('Singapore',r'singapore|\bsg\b',[('region','Singapore')]),
 ('YC',r'\byc\b|y ?combinator',[('yc','yes')]),
 ('AI/ML',r'\bai\b|\bml\b|\bllms?\b|machine learning',[('title_wording','ai/ml')]),
 ('web / full-stack',r'web ?dev|front-?end|full[- ]?stack|\bcrud\b|\bsaas\b',[('title_wording','full-stack/web')]),
 ('wrong domain',r'wrong domain|not relevant|irrelevant|different (?:field|domain)|not our space',[]),
]
_NEG=re.compile(r'\b(?:no|not|lacks?|lacking|without|zero|never|weak|thin|little|missing)\b[^.,;!?]{0,22}$',re.I)
_FLIP={'yes':'no','no':'yes'}
def note_traits(text):
    """-> [(label, [(feature,value)...]), ...] for one free-text note."""
    out=[]
    for label,rx,traits in NOTE_RULES:
        m=re.search(rx,text,re.I)
        if not m: continue
        neg=bool(_NEG.search(text[max(0,m.start()-30):m.start()]))
        if neg: traits=[(k,_FLIP.get(v,v)) for k,v in traits if v in _FLIP]; label='no '+label
        out.append((label,traits))
    return out
def reason_traits(rs):
    """Legacy chip -> its mapped traits (with sign); free text -> extracted traits (sign from the decision)."""
    if rs in CHIP_MAP: return [(rs,[(k,v) for k,v,_ in CHIP_MAP[rs]],{(k,v):sgn for k,v,sgn in CHIP_MAP[rs]})]
    return [(l,t,None) for l,t in note_traits(rs)]
def learn(write=True):
    c=S.conn()
    rows=[dict(r) for r in c.execute('select * from decisions where undone=0 order by ts')]
    last={}
    for r in rows: last[r['handle']]=r          # latest live decision per person
    D=list(last.values()); n=len(D); a=sum(1 for d in D if d['decision']=='approve')
    out={'updated_at':int(time.time()),'n_decisions':n,'n_approved':a,'approve_rate':round(a/n,3) if n else None,'weights':{},'bias':0,'confidence':0,
         'likes':[],'passes_on':[],'reasons':{'approve':{},'pass':{}},'notes':[],'sourcing':{}}
    if n:
        p=(a+1)/(n+2); out['bias']=round(math.log(p/(1-p)),3)
        stats=collections.defaultdict(lambda:collections.defaultdict(lambda:[0,0])); tv={}
        for d in D:
            for k,v in json.loads(d['features'] or '{}').items(): stats[k][v][0 if d['decision']=='approve' else 1]+=1
            side='approve' if d['decision']=='approve' else 'pass'
            for rs in json.loads(d['reasons'] or '[]'):
                if not isinstance(rs,str) or not rs.strip(): continue
                if rs not in CHIP_MAP: out['notes'].append({'decision':side,'note':rs[:300],'ts':d['ts']})
                for label,traits,sg in reason_traits(rs.strip()):
                    out['reasons'][side][label]=out['reasons'][side].get(label,0)+1
                    for k,v in traits:
                        sgn=sg[(k,v)] if sg else (1 if side=='approve' else -1)
                        tv[(k,v)]=tv.get((k,v),0)+sgn
        ins=[]
        for k,vals in stats.items():
            for v,(ap,pa) in vals.items():
                tot=ap+pa
                # smoothed log-odds vs overall rate, shrunk toward 0 with small samples
                lo=math.log((ap+p*2)/(pa+(1-p)*2))-out['bias']
                w=lo*tot/(tot+5)
                out['weights'].setdefault(k,{})[v]=round(w,3)
                if tot>=3: ins.append((w,k,v,ap,tot))
        for (k,v),net in tv.items():   # explicit notes/chips: a strong, quickly-saturating nudge
            if net: out['weights'].setdefault(k,{})[v]=round(out['weights'].get(k,{}).get(v,0)+(1 if net>0 else -1)*0.8*abs(net)/(abs(net)+4),3)
        out['confidence']=round(min(0.8,n/(n+40)),3)
        ins.sort(reverse=True)
        def phr(k,v):
            L=F.FEATURE_LABELS.get(k,k)
            if v=='yes': return L
            if v=='no': return 'No '+L[0].lower()+L[1:] if k!='bay_area' else 'Outside the Bay Area'
            return f"{L}: {v}"
        lab=lambda k,v,ap,tot:f"{phr(k,v)} · {ap} of {tot} approved"
        base=round(100*a/n)
        out['likes']=[lab(k,v,ap,t) for w,k,v,ap,t in ins if w>0.15][:6]
        out['passes_on']=[lab(k,v,ap,t) for w,k,v,ap,t in reversed(ins) if w<-0.15][:6]
        top=lambda side:sorted(out['reasons'][side].items(),key=lambda x:-x[1])[:2]
        out['likes']=[f"Approved for “{r}” {c}×" for r,c in top('approve')]+out['likes']
        out['passes_on']=[f"Passed for “{r}” {c}×" for r,c in top('pass')]+out['passes_on']
        # Sourcing guidance consumed by the weekly sourcing run and add_batch.py
        def best(k):
            vals={v:w for v,w in out['weights'].get(k,{}).items()}
            return sorted(vals,key=vals.get,reverse=True)
        out['sourcing']={
          'over_source':[f"{k}={v}" for w,k,v,ap,t in ins if w>0.3][:6],
          'down_rank':[f"{k}={v}" for w,k,v,ap,t in reversed(ins) if w<-0.3][:6],
          'region_split_singapore':0.2 if out['weights'].get('region',{}).get('Singapore',0)>=-0.2 else 0.1,
          'require_github':out['weights'].get('github',{}).get('no',0)<-0.7,
          'note':f'baseline approve rate {base}%. weights are log-odds vs baseline; confidence grows with decisions.'}
    out['notes']=out['notes'][-25:]   # recent free-text notes, read by the weekly sourcing run
    if write:
        if S.DATABASE_URL: S.taste_set(out)
        else: json.dump(out,open(F.TASTE,'w'),indent=1)
    return out
