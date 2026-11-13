"""Storage for queue + decisions. Postgres when DATABASE_URL is set (Render), else SQLite at data/xavi.db (box)."""
import sqlite3,json,time,os,re,threading
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR=os.environ.get('DATA_DIR',os.path.join(ROOT,'data'))
DB=os.environ.get('XAVI_DB',os.path.join(DATA_DIR,'xavi.db'))
DATABASE_URL=os.environ.get('DATABASE_URL')
COLS=['handle','data','batch','added_at','fit','status','decided_at','reasons','gem_id','gem_projects','outreach','outreach_checked_at']
SCHEMA='''
create table if not exists candidates(
  handle text primary key, data text not null, batch text, added_at bigint, fit integer,
  status text not null default 'queue',  -- queue | approved | passed | resurface
  decided_at bigint, reasons text, gem_id text, gem_projects text, outreach text, outreach_checked_at bigint);
create table if not exists decisions(
  id integer primary key autoincrement, handle text, decision text, reasons text, features text, fit integer,
  ts bigint, undone integer default 0, batch text);
create table if not exists meta(k text primary key, v text);
'''
class Row(dict):
    """dict that also supports r[0] like sqlite3.Row."""
    def __init__(self,cols,vals): super().__init__(zip(cols,vals)); self._v=list(vals)
    def __getitem__(self,k): return self._v[k] if isinstance(k,int) else dict.__getitem__(self,k)
def _pg_sql(sql):
    s=sql.replace('?','%s')
    m=re.match(r'\s*insert or replace into (\w+)\s*(\(([^)]*)\))?\s*values',s,re.I)
    if m:
        t=m.group(1); cols=[c.strip() for c in m.group(3).split(',')] if m.group(3) else (COLS if t=='candidates' else ['k','v'])
        key='handle' if t=='candidates' else 'k'
        s=re.sub(r'insert or replace into',"insert into",s,count=1,flags=re.I)
        if not m.group(2): s=s.replace(f'into {t}',f"into {t}({','.join(cols)})",1)
        s+=f" on conflict ({key}) do update set "+','.join(f"{c}=excluded.{c}" for c in cols if c!=key)
    return s
class _Cur:
    def __init__(self,cur):
        self.c=cur; self.cols=[d.name for d in cur.description] if cur.description else []
    def fetchone(self):
        r=self.c.fetchone(); return Row(self.cols,r) if r is not None else None
    def fetchall(self): return [Row(self.cols,r) for r in self.c.fetchall()]
    def __iter__(self): return iter(self.fetchall())
_PG_LOCK=threading.Lock(); _PG=None
class PGConn:
    def __init__(self):
        import psycopg; global _PG
        with _PG_LOCK:
            if _PG is None or _PG.closed:
                _PG=psycopg.connect(DATABASE_URL,autocommit=True)
                _PG.execute(SCHEMA.replace('integer primary key autoincrement','serial primary key').replace('--','-- '))
        self.db=_PG
    def execute(self,sql,params=()):
        with _PG_LOCK: return _Cur(self.db.execute(_pg_sql(sql),tuple(params)))
    def executescript(self,s): pass
    def commit(self): pass
def conn():
    if DATABASE_URL: return PGConn()
    os.makedirs(os.path.dirname(DB),exist_ok=True)
    c=sqlite3.connect(DB,timeout=30); c.row_factory=sqlite3.Row; c.executescript(SCHEMA); return c
def row(r):
    d=dict(r); d.pop('_v',None); d['data']=json.loads(d['data'])
    for k in('reasons','gem_projects','outreach'): d[k]=json.loads(d[k]) if d.get(k) else None
    return d
def get(c,h):
    r=c.execute('select * from candidates where handle=?',(h,)).fetchone(); return row(r) if r else None
def all_rows(c): return [row(r) for r in c.execute('select * from candidates')]
def meta_get(c,k,default=None):
    r=c.execute('select v from meta where k=?',(k,)).fetchone(); return json.loads(r[0]) if r else default
def meta_set(c,k,v): c.execute('insert or replace into meta values(?,?)',(k,json.dumps(v))); c.commit()
# taste.json lives in the DB on Postgres so it survives deploys (no disk on Render web service)
def taste_get():
    if not DATABASE_URL: return None
    return meta_get(conn(),'taste',{})
def taste_set(t):
    if DATABASE_URL: meta_set(conn(),'taste',t)
