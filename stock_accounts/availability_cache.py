"""Durable, permission-scoped material checks; summaries travel with plans.

Workbook upload time and content version, calculation revision, material and
quantity invalidate results. Full BOM rows are read only when details are opened.
"""
import hashlib,json,time
from .transfer_cache import read_rows
REVISION=3

def schema(s,db):
 s.run(db,'CREATE TABLE IF NOT EXISTS production_availability_cache (plan_id TEXT NOT NULL,scope TEXT NOT NULL,version TEXT NOT NULL,uploaded_at DOUBLE PRECISION NOT NULL,signature TEXT NOT NULL,available INTEGER NOT NULL,checked_at DOUBLE PRECISION NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(plan_id,scope))')

def signature(item):
 return hashlib.sha256(json.dumps([REVISION,item['materialCode'],float(item['row'][3])],separators=(',',':')).encode()).hexdigest()

def metadata(s,db,scope,version,uploaded_at):
 schema(s,db)
 from .batch_availability import schema as batch_schema
 batch_schema(s,db)
 return read_rows(s,db,"SELECT c.plan_id,c.signature,c.available,c.checked_at,NULL AS batch_summary FROM production_availability_cache c JOIN production_shared p ON p.kind='upcoming' AND p.id=c.plan_id WHERE c.scope=? AND c.version=? AND c.uploaded_at=? UNION ALL SELECT '__batch__',signature,0,checked_at,summary FROM production_batch_availability WHERE scope=? AND version=? AND uploaded_at=? ORDER BY 1",(scope,version,uploaded_at,scope,version,uploaded_at))

def revision(s,actor,master,identity):
 if not master:return ''
 segments=identity.get('allowedSegments')
 from .segment_access import scope_key
 scope=scope_key(segments)
 with s.transaction() as db:
  s.require(db,actor,permission='menu_3')
  rows=metadata(s,db,scope,*master)
 return hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()

def summaries(s,actor,current,items):
 with s.transaction() as db:
  s.require(db,actor,permission='menu_3')
  rows=metadata(s,db,current.get('_scope','all'),current['version'],current['updated_at'])
 index={r['plan_id']:r for r in rows}
 for item in items:
  cached=index.get(item['id'])
  if cached and item.get('materialCode') and cached['signature']==signature(item):
   item['availability']={'available':bool(cached['available']),'version':current['version'],'sourceStamp':current['updated_at'],'revision':item['revision'],'checkedAt':cached['checked_at']}

 from .batch_availability import signature as batch_signature
 batch=next((r for r in rows if r['plan_id']=='__batch__'),None)
 return json.loads(batch['batch_summary']) if batch and batch['signature']==batch_signature(items) else None

def check(s,actor,current,item):
 scope=current.get('_scope','all');sig=signature(item)
 with s.transaction() as db:
  s.require(db,actor,permission='menu_3');schema(s,db)
  if not s.sqlite:s.run(db,'SELECT pg_advisory_xact_lock(hashtext(?))',('availability:'+item['id']+':'+scope,))
  def validate():
   master=s.run(db,"SELECT version,updated_at FROM datasets WHERE id='current'").fetchone()
   plan=s.run(db,"SELECT revision FROM production_shared WHERE kind='upcoming' AND id=?",(item['id'],)).fetchone()
   if not master or (master['version'],master['updated_at'])!=(current['version'],current['updated_at']) or not plan or plan['revision']!=item['revision']:
    raise ValueError('The workbook or plan changed. Refresh Production and check again.')
  validate()
  cached=read_rows(s,db,'SELECT payload,checked_at FROM production_availability_cache WHERE plan_id=? AND scope=? AND version=? AND uploaded_at=? AND signature=?',(item['id'],scope,current['version'],current['updated_at'],sig))
  if cached:
   result=json.loads(cached[0]['payload']);checked_at=cached[0]['checked_at']
  else:
   from .production_materials import availability
   result=availability(current['data'],item['materialCode'],item['row'][3]);checked_at=time.time()
   validate()
   s.run(db,'INSERT INTO production_availability_cache VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(plan_id,scope) DO UPDATE SET version=excluded.version,uploaded_at=excluded.uploaded_at,signature=excluded.signature,available=excluded.available,checked_at=excluded.checked_at,payload=excluded.payload',
    (item['id'],scope,current['version'],current['updated_at'],sig,int(result['available']),checked_at,json.dumps(result,allow_nan=False,separators=(',',':'))))
  return {**result,'version':current['version'],'sourceStamp':current['updated_at'],'id':item['id'],'revision':item['revision'],'materialCode':item['materialCode'],'quantity':item['row'][3],'checkedAt':checked_at}
