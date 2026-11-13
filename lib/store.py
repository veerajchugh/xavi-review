"""SQLite store for queue + decisions. Durable on disk at data/xavi.db."""
import sqlite3,json,time,os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR=os.environ.get('DATA_DIR',os.path.join(ROOT,'data'))
DB=os.environ.get('XAVI_DB',os.path.join(DATA_DIR,'xavi.db'))
SCHEMA='''
create table if not exists candidates(
  handle text primary key, data text not null, batch text, added_at integer, fit integer,
  status text not null default 'queue',  -- queue | approved | passed | resurface
  decided_at integer, reasons text, gem_id text, gem_projects text, outreach text, outreach_checked_at integer);
create table if not exists decisions(
  id integer primary key autoincrement, handle text, decision text, reasons text, features text, fit integer,
  ts integer, undone integer default 0, batch text);
create table if not exists meta(k text primary key, v text);
'''
def conn():
    os.makedirs(os.path.dirname(DB),exist_ok=True)
    c=sqlite3.connect(DB,timeout=30); c.row_factory=sqlite3.Row; c.executescript(SCHEMA); return c
def row(r):
    d=dict(r); d['data']=json.loads(d['data'])
    for k in('reasons','gem_projects','outreach'): d[k]=json.loads(d[k]) if d.get(k) else None
    return d
def get(c,h):
    r=c.execute('select * from candidates where handle=?',(h,)).fetchone(); return row(r) if r else None
def all_rows(c): return [row(r) for r in c.execute('select * from candidates')]
def meta_get(c,k,default=None):
    r=c.execute('select v from meta where k=?',(k,)).fetchone(); return json.loads(r[0]) if r else default
def meta_set(c,k,v): c.execute('insert or replace into meta values(?,?)',(k,json.dumps(v))); c.commit()
