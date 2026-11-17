"""Observed dates in uploaded sources, separate from upload times and planned dates."""
import base64,gzip,json,re
from datetime import date,datetime
from .pnl_import import day,norm
REVISION=1
DATE_COLUMNS=('billingdate','billdate','invoicedate','postingdate','documentdate','salesdocumentdate','createdon','creationdate','date','attribute')

def table_summary(table):
 headers=table.get('headers',[]);rows=table.get('rows',[])
 for field in DATE_COLUMNS:
  indexes=[i for i,h in enumerate(headers) if norm(h)==field]
  latest=None;label=None
  for i in indexes:
   for row in rows:
    value=row[i] if i<len(row) else None
    # Attribute is frequently a pivot label, so only accept explicit dates there.
    if field=='attribute' and not isinstance(value,(date,datetime)) and not re.match(r'^\d{4}-\d{2}-\d{2}',str(value or '')):continue
    parsed=day(value)
    if parsed and 1900<=parsed.year<=2200 and (latest is None or parsed>latest):latest=parsed;label=headers[i]
  if latest:return {'dataUpTo':latest.isoformat(),'dataDateBasis':str(table.get('name') or 'Uploaded records')+' · '+str(label)}
 return {'dataUpTo':None,'dataDateBasis':'No dated transaction or snapshot records found in the file'}

def workbook_summary(data):
 values=[]
 # Calendar, forecasts, validity dates and future production plans do not establish freshness.
 for table in data.get('tables',[])+data.get('sheets',[]):
  name=norm(table.get('name'))
  if name in {'calendar','forecastplanning','forecastdata','productionorderdetails','planningquantity'}:continue
  if name not in {'materialdocumentlist','stockdata','salesdata','orderlist','summary','bom','bomcost','transferdetails','productiondata'}:continue
  value=table_summary(table)
  if value['dataUpTo']:values.append(value)
 if values:return max(values,key=lambda v:v['dataUpTo'])
 snapshot=day(data.get('productionSnapshotDate'))
 return {'dataUpTo':snapshot.isoformat() if snapshot else None,'dataDateBasis':'Workbook snapshot date' if snapshot else 'No dated transaction or snapshot records found in the file'}

def pnl_summary(value,kind):
 if kind=='salary':return {'dataUpTo':None,'dataDateBasis':'Annual CTC reference; employee join/leave dates do not establish data coverage'}
 months=[str(r.get('month',''))[:7] for r in value.get('production',[]) if re.fullmatch(r'\d{4}-\d{2}',str(r.get('month',''))[:7])]
 return {'dataUpTo':max(months) if months else None,'dataDateBasis':'Latest production month in the uploaded PnL file' if months else 'No dated records found in the file'}

def cached(store,actor,key,version,loader):
 """Persist small summaries; unchanged reads never download/scan source payloads."""
 with store.transaction() as db:
  store.require(db,actor)
  if not getattr(store,'_source_freshness_schema',False):
   store.run(db,'CREATE TABLE IF NOT EXISTS source_freshness_cache (source_key TEXT NOT NULL,version TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(source_key,version))')
   store._source_freshness_schema=True
  row=store.run(db,'SELECT payload FROM source_freshness_cache WHERE source_key=? AND version=?',(str(REVISION)+':'+key,version)).fetchone()
 if row:return json.loads(row['payload'])
 value=loader()
 with store.transaction() as db:
  store.require(db,actor)
  store.run(db,'INSERT INTO source_freshness_cache VALUES(?,?,?) ON CONFLICT(source_key,version) DO NOTHING',(str(REVISION)+':'+key,version,json.dumps(value)))
 return value

def uploaded(store,actor,kind,meta):
 if not meta:return None
 meta=dict(meta)
 def load():
  with store.transaction() as db:
   store.require(db,actor)
   if kind=='master':row=store.run(db,"SELECT payload FROM datasets WHERE id='current' AND version=?",(meta['version'],)).fetchone()
   elif kind=='orders':row=store.run(db,"SELECT payload FROM stock_open_orders WHERE id='current' AND version=?",(meta['version'],)).fetchone()
   elif kind.startswith('sales:'):row=store.run(db,'SELECT payload FROM stock_sales_documents WHERE kind=? AND version=?',(kind.split(':',1)[1],meta['version'])).fetchone()
   else:row=store.run(db,'SELECT payload FROM stock_pnl_documents WHERE id=? AND version=?',(meta['id'],meta['version'])).fetchone()
  if not row:raise ValueError('The source file changed. Refresh source details.')
  value=json.loads(gzip.decompress(base64.b64decode(row['payload'])))
  return workbook_summary(value) if kind=='master' else pnl_summary(value,meta['kind']) if kind.startswith('pnl:') else table_summary(value)
 return {**meta,**cached(store,actor,kind,meta['version'],load)}
