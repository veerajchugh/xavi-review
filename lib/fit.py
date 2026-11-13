"""Features, fit score and taste model shared by server, add_batch and learn."""
import json,os,re,math
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASTE=os.environ.get('XAVI_TASTE',os.path.join(os.environ['DATA_DIR'],'taste.json') if os.environ.get('DATA_DIR') else os.path.join(ROOT,'taste.json'))
BIGTECH=re.compile(r'\b(google|meta|facebook|apple|amazon|microsoft|netflix|nvidia|openai|anthropic|stripe|uber|airbnb|tesla|bytedance|tiktok|salesforce|oracle|intel|ibm|linkedin|snap|grab|shopee|sea|gojek|databricks|palantir)\b',re.I)
def _num(s):
    if s is None: return None
    s=str(s).strip().lower().replace(',','')
    try: return float(s[:-1])*1000 if s.endswith('k') else float(s)
    except: return None
# ---- Standing rules from Veeraj (Nov 13, 2026): software people with a dash of firmware; avoid robotics + pure EE/hardware;
# people at buzzy/hot startups probably won't leave. Applied on top of the learned score so they hold regardless of feedback.
try: _CFG=json.load(open(os.path.join(ROOT,'config.json')))
except Exception: _CFG={}
def _norm(n): 
    n=re.sub(r'[^a-z0-9 ]+',' ',(n or '').lower()); n=re.sub(r'\b(inc|llc|ltd|corp|co|the|hq|technologies|technology)\b',' ',n)
    return re.sub(r'\s+',' ',n).strip()
def _core(n): return re.sub(r'\s+(ai|labs?|io)$','',_norm(n)).strip()
HOT={_core(x) for x in _CFG.get('hot_companies',[])}
BUZZ=_CFG.get('buzzy_funding',{'total_usd_min':150e6,'last_round_usd_min':50e6,'last_round_within_months':18})
ROBOT=re.compile(r'robot|mechatron|humanoid|motion planning|\bcontrols? engineer|autonomy engineer|embodied',re.I)
EE=re.compile(r'electrical|hardware engineer|\bhardware\b(?! *(?:/|and|&) *software)|mechanical|\bpcb\b|\basic\b|\bfpga\b|silicon|analog|rf engineer|power electronics|systems applications|manufacturing|product design engineer',re.I)
SW=re.compile(r'software|\bswe\b|full[- ]?stack|back[- ]?end|front[- ]?end|platform|infra|\bweb\b|\bios\b|android|product engineer|\bml\b|\bai\b|machine learning|data engineer|developer|programmer|member of technical staff|\bmts\b',re.I)
FW=re.compile(r'firmware|embedded|\brtos\b|bare[- ]?metal|microcontroller|\bmcu\b|device driver|kernel|\biot\b',re.I)
def discipline(c):
    roles=' | '.join(filter(None,[c.get('founding_role'),c.get('current_title')]))
    txt=' | '.join(filter(None,[roles,c.get('headline'),c.get('hardware_note')]))
    fw=bool(FW.search(txt)); sw=bool(SW.search(roles)) or (not ROBOT.search(roles) and not EE.search(roles))
    if ROBOT.search(roles): return 'robotics'
    if EE.search(roles) and not SW.search(roles) and not FW.search(roles): return 'electrical/hardware'
    if fw and (sw or FW.search(roles)): return 'software+firmware'
    return 'software' if sw else 'other'
def buzzy(c):
    """Current employer is a hot, well-funded startup (maintained list in config.json, or funding data when sourcing adds it)."""
    if BIGTECH.search(c.get('current_company') or ''): return False
    if _core(c.get('current_company')) in HOT: return True
    tot=c.get('current_company_funding_usd') or 0; last=c.get('current_company_last_round_usd') or 0; mo=c.get('current_company_last_round_months_ago')
    return tot>=BUZZ['total_usd_min'] or (last>=BUZZ['last_round_usd_min'] and (mo is None or mo<=BUZZ['last_round_within_months']))
STANDING={'discipline':{'software+firmware':8,'firmware':5,'robotics':-30,'electrical/hardware':-35},'buzzy':{'yes':-30}}
STANDING_NOTES=['Software engineers first; a dash of firmware/embedded is a plus (+8)','Robotics engineers drop to the bottom (-30)',
 'Pure electrical/hardware engineers drop to the bottom (-35)','People at buzzy, well-funded startups probably won’t leave (-30)']
def github_quality(c):
    if not c.get('github_url'): return 'none'
    r=_num(c.get('gh_repos')) or 0; f=_num(c.get('gh_followers')) or 0; k=_num(c.get('gh_contribs')) or 0
    pts=(r>=15)+(f>=20)+(k>=200)+(r>=40 or f>=100 or k>=800)
    return 'strong' if pts>=2 else ('some' if (r>=5 or k>=50) else 'thin')
def features(c):
    y=c.get('total_yoe') or 0; t=c.get('founding_tenure_months') or 0; hc=c.get('founding_hc')
    title=(c.get('founding_role') or '').lower()
    tw='robotics/hardware' if re.search(r'hardware|electrical|robot|mechanical',title) else 'firmware/embedded' if re.search(r'firmware|embedded',title) else 'ai/ml' if re.search(r'\bai\b|\bml\b|machine|llm',title) else 'full-stack/web' if re.search(r'full|stack|front|back|web|product',title) else 'software' if 'software' in title else 'generic'
    cur=c.get('current_company') or ''
    emp='founding seat now' if c.get('founding_current') else ('big tech' if BIGTECH.search(cur) else ('startup' if (c.get('current_hc') or 0) and c.get('current_hc')<500 else ('larger company' if cur else 'between roles')))
    return {
      'region':c.get('region') or 'other',
      'bay_area':'yes' if c.get('bay_area') else 'no',
      'yoe':'2-3' if y<3.5 else ('4-5' if y<5.5 else '6-8'),
      'founding_tenure':'6-11 mo' if t<12 else ('12-23 mo' if t<24 else '24+ mo'),
      'github':'yes' if c.get('github_url') else 'no',
      'github_quality':github_quality(c),
      'personal_site':'yes' if c.get('personal_site') else 'no',
      'hardware':'yes' if c.get('hardware_signal') else 'no',
      'yc':'yes' if c.get('yc') else 'no',
      'company_stage':'tiny (<=10)' if (hc or 0)<=10 else ('small (11-50)' if hc<=50 else ('mid (51-200)' if hc<=200 else 'large (200+)')),
      'employer_type':emp,
      'title_wording':tw,
      'discipline':discipline(c),
      'buzzy':'yes' if buzzy(c) else 'no',
    }
FEATURE_LABELS={'region':'Region','bay_area':'Bay Area','yoe':'Experience','founding_tenure':'Founding stint','github':'GitHub','github_quality':'GitHub depth',
 'personal_site':'Personal site','hardware':'Hardware','yc':'YC company','company_stage':'Founding co. size','employer_type':'Now','title_wording':'Title','discipline':'Discipline','buzzy':'Buzzy startup now'}
# Prior = Veeraj's stated spec, in points.
PRIOR={'founding_tenure':{'6-11 mo':4,'12-23 mo':12,'24+ mo':15},'github':{'yes':10},'github_quality':{'strong':10,'some':5},
 'personal_site':{'yes':8},'hardware':{'yes':3},'bay_area':{'yes':6},'region':{'Singapore':6},'yoe':{'4-5':4,'6-8':3,'2-3':1},
 'yc':{'yes':3},'company_stage':{'tiny (<=10)':3,'small (11-50)':4}}
PRIOR_MAX=15+10+10+8+3+6+6+4+3+4
def load_taste():
    if os.environ.get('DATABASE_URL'):
        import store; return store.taste_get() or {}
    try: return json.load(open(TASTE))
    except Exception: return {}
def fit(c,taste=None):
    taste=load_taste() if taste is None else taste
    f=features(c)
    base=sum(PRIOR.get(k,{}).get(v,0) for k,v in f.items())/PRIOR_MAX*100
    w=taste.get('weights',{}); conf=taste.get('confidence',0)
    adj=sum(w.get(k,{}).get(v,0) for k,v in f.items())  # log-odds
    learned=100/(1+math.exp(-(adj+taste.get('bias',0)))) if w else base
    s=(1-conf)*base+conf*learned
    s+=sum(STANDING.get(k,{}).get(v,0) for k,v in f.items())   # standing rules, never washed out by learning
    return round(max(1,min(99,s)))
def standing_reasons(c):
    f=features(c); out=[]
    if f['discipline'] in('robotics','electrical/hardware'): out.append(f['discipline'])
    if f['buzzy']=='yes': out.append('buzzy startup')
    return out
