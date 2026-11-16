"""Upload deltas and first-authenticated-visit reports; no workbook reads on login.

Upload/edit hooks commit compact events with the source change. Only fingerprints
of the preceding upload are retained. Delivery is opt-in after an admin preview.
"""
import base64,gzip,hashlib,json,math,re,time
from collections import Counter,defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
REVISION=8
IST=ZoneInfo('Asia/Kolkata')
RULES={
 'packaging':('1 · Listed packaging materials below saved stock threshold','New master workbook',0),
 'production':('2 · New completed, under-QC and ongoing entries','New master workbook',3),
 'sales':('3 · New Primary / Secondary Sales entries','New sales workbook',11),
 'due':('4 · Ongoing batch due or overdue','Daily 02:30 IST · authenticated-visit fallback',3),
 'plan':('5 · New production plans','Daily · saved changes before today',3),
 'forecast':('6 · Forecast need to order above zero','New master workbook',5),
 'qc':('7 · Under-QC batches pending at least saved days (default 7)','New master workbook',3),
 'batch_required':('9 · New Production Batch Required · full table','Daily 02:30 IST · latest saved requirement table',13),
 'edit':('8 · Ongoing / upcoming plan modifications','Daily · saved changes before today',3),
}
DEFAULT={'enabled':False,'rules':list(RULES),'threshold':3000,'qcDays':7,'policyRevision':3,
 'packagingWords':['label','pouch','polybag','poly bag','blister','leaflet','insert','wrapper'],
 'packagingTypes':[],'includeMaterials':[],'excludeMaterials':[]}

def dumps(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False,default=str)
def digest(v):return hashlib.sha256(dumps(v).encode()).hexdigest()
def key(v):
 from .production import ident
 return ident(v)
def num(v):
 try:n=float(v);return n if math.isfinite(n) else None
 except (TypeError,ValueError):return None
def rows(data,name,source='tables'):
 t=next((t for t in data.get(source,[]) if t['name']==name),{})
 return [dict(zip(t.get('headers',[]),r)) for r in t.get('rows',[])]
def schema(s,db):
 # Acquire the advisory lock before notification DDL on every path.
 lock(s,db)
 for sql in [
  'CREATE TABLE IF NOT EXISTS stock_open_orders (id TEXT PRIMARY KEY,filename TEXT NOT NULL,version TEXT NOT NULL,updated_at DOUBLE PRECISION NOT NULL,updated_by TEXT NOT NULL,payload TEXT NOT NULL)',
  'CREATE TABLE IF NOT EXISTS stock_notice_config (id TEXT PRIMARY KEY,payload TEXT NOT NULL)',
  'CREATE TABLE IF NOT EXISTS stock_notice_sources (id TEXT PRIMARY KEY,version TEXT NOT NULL,fingerprints TEXT NOT NULL)',
  'CREATE TABLE IF NOT EXISTS stock_notice_events (id TEXT PRIMARY KEY,batch TEXT NOT NULL,rule TEXT NOT NULL,menu INTEGER NOT NULL,segments TEXT NOT NULL,strict INTEGER NOT NULL,occurred DOUBLE PRECISION NOT NULL,payload TEXT NOT NULL)',
  'CREATE INDEX IF NOT EXISTS stock_notice_event_time ON stock_notice_events(rule,occurred)',
  'CREATE INDEX IF NOT EXISTS stock_notice_event_batch ON stock_notice_events(batch)',
  'CREATE TABLE IF NOT EXISTS stock_notice_due (id TEXT PRIMARY KEY,due TEXT NOT NULL,segments TEXT NOT NULL,payload TEXT NOT NULL)',
  'CREATE TABLE IF NOT EXISTS stock_notice_batches (id TEXT PRIMARY KEY,created DOUBLE PRECISION NOT NULL,status TEXT NOT NULL)',
  'CREATE TABLE IF NOT EXISTS stock_notice_jobs (id TEXT PRIMARY KEY,batch TEXT NOT NULL,recipient TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,created DOUBLE PRECISION NOT NULL,error TEXT NOT NULL)',
  'CREATE INDEX IF NOT EXISTS stock_notice_job_pending ON stock_notice_jobs(status,created)',
  'CREATE TABLE IF NOT EXISTS stock_notice_cursor (id TEXT PRIMARY KEY,value TEXT NOT NULL)',
 ]:s.run(db,sql)
def lock(s,db,wait=True):
 if s.sqlite:return True
 if wait:
  s.run(db,'SELECT pg_advisory_xact_lock(hashtext(?))',('stock-notice',));return True
 return bool(s.run(db,'SELECT pg_try_advisory_xact_lock(hashtext(?)) AS acquired',('stock-notice',)).fetchone()['acquired'])
def config(s,db):
 r=s.run(db,"SELECT payload FROM stock_notice_config WHERE id='current'").fetchone()
 saved=json.loads(r['payload']) if r else {}
 if saved.get('policyRevision',0)<3 and saved.get('qcDays',14)==14:saved['qcDays']=7
 legacy_words=['label','packaging','packing','carton','box','pouch','polybag','poly bag','blister','leaflet','insert','wrapper','shipper']
 if saved.get('policyRevision',0)<3 and saved.get('packagingWords')==legacy_words:saved['packagingWords']=DEFAULT['packagingWords']
 return {**DEFAULT,**saved,'policyRevision':3}
def packaging_match(cfg,code,description,typ):
 if code in cfg['excludeMaterials']:return False
 if code in cfg['includeMaterials']:return True
 words=[w.strip() for w in cfg['packagingWords'] if w.strip()]
 # A configured description list is authoritative; broad material types must
 # never silently expand it to every carton/box in the packaging class.
 return any(re.search(r'\b'+re.escape(w)+r's?\b',description,re.I) for w in words) if words else typ in cfg['packagingTypes']
def matches_saved_policy(cfg,rule,payload):
 if rule=='packaging':
  v=payload['values'];quantity=num(v.get('Current Stock'))
  return quantity is not None and quantity<cfg['threshold'] and packaging_match(cfg,key(v.get('Material')),str(v.get('Description') or ''),str(v.get('Material Type') or '').upper())
 if rule=='qc':return payload.get('daysPending',-1)>=cfg['qcDays']
 return True
def emit(s,db,batch,rule,identity,segments,payload,at,strict=False):
 s.run(db,'INSERT INTO stock_notice_events VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING',
 (digest([batch,rule,identity]),batch,rule,RULES[rule][2],dumps(sorted(set(segments))),int(strict),at,dumps(payload)))
def source(s,db,name,version,items):
 """Compare a multiset of identities, preserving legitimate duplicate sales rows."""
 previous=s.run(db,'SELECT version,fingerprints FROM stock_notice_sources WHERE id=?',(name,)).fetchone()
 if previous and previous['version']==version:return None
 old=Counter(json.loads(previous['fingerprints'])) if previous else None
 counts=Counter(i[0] for i in items);seen=Counter();added=[]
 for ident,payload,segments in items:
  seen[ident]+=1
  if old is not None and seen[ident]>old[ident]:added.append((ident+':'+str(seen[ident]),payload,segments))
 s.run(db,'INSERT INTO stock_notice_sources VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET version=excluded.version,fingerprints=excluded.fingerprints',(name,version,dumps(dict(counts))))
 return added
def material_segments(data):
 from workbook import segment_map
 return segment_map(data.get('tables',[]))
def record_payload(title,record,**extra):return {'section':title,'values':record,**extra}

def master(s,db,current,baseline=False):
 """Called in the master upload transaction, using the already parsed workbook."""
 schema(s,db);cfg=config(s,db)
 data=current['data'];version=current['version'];at=current['updated_at'];batch='master:'+version
 exists=s.run(db,"SELECT version FROM stock_notice_sources WHERE id='master'").fetchone()
 if exists and exists['version']==version:return
 mapping=material_segments(data)
 from .production import day
 from .production_snapshot import cached_build
 try:production=cached_build(current)
 except ValueError as exc:production={'ongoing':[],'qc':{'rows':[],'headers':[]},'referenceDate':None,'error':str(exc)}
 # Source failures are visible in preview, and do not erase a previous baseline.
 warnings=[]
 if production.get('error'):warnings.append(production['error'])
 windows=[]
 completed=next((t for t in data.get('sheets',[]) if t['name']=='Production Data'),None)
 if completed:
  items=[]
  for r in completed['rows']:
   values=dict(zip(completed['headers'],r));code=key(values.get('Material') or values.get('Material Code') or (r[3] if len(r)>3 else None))
   # The completed table is the saved Excel QC-released view, not inferred status.
   identity={k:v for k,v in values.items() if not any(w in k.lower() for w in ('quantity','qty','description','text','value','cost'))}
   items.append((digest(identity or values),record_payload('Production · Completed',values),mapping.get(code,[])))
  windows.append(('completed',items))
 if not production.get('error'):
  windows.extend([
   ('ongoing',[(i['id'],record_payload('Production · Ongoing',dict(zip(production['ongoingHeaders'],i['row']))),mapping.get(key(i['row'][2]),[])) for i in production['ongoing']]),
   ('qc',[(digest([key(r[0]),key(r[2]),key(r[6])]),record_payload('Production · Under QC',dict(zip(production['qc']['headers'],r))),mapping.get(key(r[0]),[])) for r in production['qc']['rows']])])
 for name,items in windows:
  added=source(s,db,'production:'+name,version,items)
  if not baseline:
   for ident,payload,segments in added or []:emit(s,db,batch,'production',[name,ident],segments,payload,at)
 # Compact ongoing list is the ONLY source read by the daily date rule.
 if not production.get('error'):
  s.run(db,'DELETE FROM stock_notice_due')
  from .production import schema as plan_schema
  plan_schema(s,db)
  overrides={r['id']:json.loads(r['payload']) for r in s.run(db,"SELECT id,payload FROM production_shared WHERE kind='ongoing'").fetchall()}
  for i in production['ongoing']:
   r=i['row'];override=overrides.get(i['id'])
   if override:r[7:9]=[override['endDate'],override['quantity']]
   if r[7]:s.run(db,'INSERT INTO stock_notice_due VALUES(?,?,?,?)',(i['id'],r[7],dumps(sorted(mapping.get(key(r[2]),[]))),dumps(record_payload('Ongoing · Due / overdue',dict(zip(production['ongoingHeaders'],r))))))
 if not baseline:
  # Packaging must actually occur as a BOM component. Sum physical stock once;
  # do not sum repeated BOM rows or add quantities of unrelated materials.
  stock=defaultdict(float);stock_seen=set()
  stock_rows=rows(data,'Stock Data')
  for r in stock_rows:
   code=key(r.get('Material'));a=num(r.get('Unrestricted'));b=num(r.get('In Quality Insp.'))
   if a is not None or b is not None:stock[code]+=(a or 0)+(b or 0);stock_seen.add(code)
  components={};fallback={}
  for r in rows(data,'BOM'):
   code=key(r.get('Component'));description=str(r.get('Component(text)') or r.get('Component Description') or '')
   typ=str(r.get('Material Type') or '').upper()
   match=packaging_match(cfg,code,description,typ)
   if code and match and code not in cfg['excludeMaterials']:
    components[code]=(description,typ,r.get('Component unit'))
    n=num(r.get('Sum of Stock Data.Current Stock'))
    if n is not None:fallback.setdefault(code,n)
  for code,(description,typ,unit) in components.items():
   quantity=stock[code] if code in stock_seen else fallback.get(code,0 if stock_rows else None)
   if quantity is None:warnings.append('Packaging stock unavailable: '+code);continue
   if quantity<cfg['threshold']:emit(s,db,batch,'packaging',code,mapping.get(code,[]),record_payload('Packaging · Low stock',{'Material':code,'Description':description,'Material Type':typ,'Unit':unit,'Current Stock':quantity,'Threshold':cfg['threshold']}),at)
  # Forecast purchasing retains the source row and current FG forecast context.
  forecast=next((t for t in data.get('sheets',[]) if t['name']=='Forecast Planning'),None)
  fg=[]
  if forecast and len(forecast['headers'])>=7:
   from workbook import forecast_summary
   import pandas as pd
   f=forecast_summary(pd.DataFrame(forecast['rows'],columns=forecast['headers']))
   fg=[dict(zip(f.columns,r)) for r in f.values.tolist()]
  bom=rows(data,'BOM');parents=defaultdict(set)
  for r in bom:parents[key(r.get('Component'))].add(key(r.get('Material')))
  for _ in range(20):
   changed=False
   for code,ps in list(parents.items()):
    extra=set().union(*(parents.get(p,set()) for p in list(ps))) if ps else set()
    if not extra.issubset(ps):ps.update(extra);changed=True
   if not changed:break
  for r in rows(data,'Forecast Need to Order List','sheets'):
   quantity=num(r.get('Need to Order Quantity'));code=key(r.get('Component') or r.get('Material'))
   if quantity is not None and quantity>0:
    linked=[f for f in fg if key(f['Material']) in parents.get(code,set()) or key(f['Material'])==code]
    emit(s,db,batch,'forecast',digest(r),mapping.get(code,[]),record_payload('Forecast · Need to order',r,forecast=linked,forecastSegments={key(f['Material']):sorted(mapping.get(key(f['Material']),[])) for f in linked}),at,strict=True)
  ref=day(production.get('referenceDate'))
  for r in production['qc']['rows']:
   latest=day(r[5]);age=(ref-latest).days if ref and latest else -1
   if age>=cfg['qcDays']:
    history=[m for m in rows(data,'Material Document List') if key(m.get('Material'))==key(r[0]) and key(m.get('Batch'))==key(r[2]) and day(m.get('Posting Date')) and day(m.get('Posting Date'))<=ref]
    history.sort(key=lambda m:day(m.get('Posting Date')),reverse=True)
    emit(s,db,batch,'qc',[key(r[0]),key(r[2]),key(r[6])],mapping.get(key(r[0]),[]),record_payload('Under QC · Pending history',dict(zip(production['qc']['headers'],r)),daysPending=age,referenceDate=ref.isoformat(),history=history[:50],historyCount=len(history)),at)
 s.run(db,"INSERT INTO stock_notice_sources VALUES('master',?,?) ON CONFLICT(id) DO UPDATE SET version=excluded.version,fingerprints=excluded.fingerprints",(version,dumps({'warnings':warnings,'baseline':baseline})))

def sales(s,db,kind,version,value,at,eligible=None,baseline=False):
 schema(s,db);items=[]
 for r in value['rows']:
  record=dict(zip(value['headers'],r))
  if kind=='primary' and eligible is not None:
   from .sales import material_key
   code=next((v for h,v in record.items() if re.sub('[^a-z]','',h.lower()) in ('material','materialcode','materialnumber','materialno','skucode','sku','fgcode','fgmaterialcode')),None)
   if material_key(code) not in eligible:continue
  segment=str(r[value['segmentIndex']]);segments=[] if segment=='Unmapped' else [segment]
  items.append((digest(record),record_payload(kind.title()+' Sales · New entries',record),segments))
 added=source(s,db,'sales:'+kind,version,items)
 if not baseline:
  for ident,payload,segments in added or []:emit(s,db,'sales:'+kind+':'+version,'sales',ident,segments,payload,at)

def plan(s,db,current,ident,kind,before,after,username,at,created=False):
 schema(s,db);mapping=material_segments(current['data'])
 code=key(after.get('materialCode') or after.get('product'))
 segments=[after['segment']] if after.get('segment') else sorted(mapping.get(code,[]))
 previous_code=key(before.get('materialCode') or before.get('product'))
 previous_segments=[before['segment']] if before.get('segment') else sorted(mapping.get(previous_code,[]))
 crosses_segment=bool(before) and set(previous_segments)!=set(segments)
 if crosses_segment:segments=sorted(set(segments)|set(previous_segments))
 changed={k:{'before':before.get(k),'after':after.get(k)} for k in set(before)|set(after) if before.get(k)!=after.get(k)}
 if not changed:return
 emit(s,db,'daily-events','plan' if created and kind=='upcoming' else 'edit',[ident,at,digest(changed)],segments,record_payload('Production plan · '+('Added' if created else 'Modified'),after,before=before,changes=changed,username=username,changedAt=datetime.fromtimestamp(at,IST).isoformat(),planKind=kind),at,strict=crosses_segment)
 if kind=='ongoing':
  row=s.run(db,'SELECT payload FROM stock_notice_due WHERE id=?',(ident,)).fetchone()
  if row:
   payload=json.loads(row['payload']);payload['values'].update({'Expected End Date':after['endDate'],'Expected FG Quantity':after['quantity']})
   s.run(db,'UPDATE stock_notice_due SET due=?,payload=? WHERE id=?',(after['endDate'],dumps(payload),ident))

def people(s,db):
 return [dict(r) for r in s.run(db,f'SELECT a.username,a.role,a.active,a.permissions,a.allowed_segments,p.email FROM {s.account_table} a JOIN portal_profiles p ON a.username=p.username WHERE a.active=1 AND p.email IS NOT NULL ORDER BY p.email').fetchall() if r['email']]
def permitted(person,event):
 if person['role']=='admin':return True
 from .access import allowed
 if not allowed({'role':person['role'],'permissions':json.loads(person['permissions'] or '{}')},event['menu']):return False
 wanted=json.loads(person['allowed_segments']) if person['allowed_segments'] is not None else None
 if wanted is None:return True
 segments=set(json.loads(event['segments']))
 return bool(segments) and (segments.issubset(wanted) if event['strict'] else bool(segments.intersection(wanted)))
def today(now):return datetime.fromtimestamp(now,IST).date().isoformat()
def events(s,db,now,preview=False,include_daily=True):
 cfg=config(s,db);day=today(now);cutoff=datetime.fromisoformat(day).replace(tzinfo=IST).timestamp()
 out=[]
 # Uploaded versions are processed independently; no repeated source evaluation.
 for r in s.run(db,"SELECT id,batch,rule,menu,segments,strict,occurred,payload FROM stock_notice_events e WHERE batch<>'daily-events' AND NOT EXISTS (SELECT 1 FROM stock_notice_batches b WHERE b.id=e.batch) ORDER BY occurred,id").fetchall():
  payload=json.loads(r['payload'])
  if r['rule'] in cfg['rules'] and matches_saved_policy(cfg,r['rule'],payload):
   if r['rule']=='packaging':payload['values']['Threshold']=cfg['threshold']
   out.append({**dict(r),'payload':dumps(payload)})
 daily='daily:'+day
 if include_daily and not s.run(db,'SELECT id FROM stock_notice_batches WHERE id=?',(daily,)).fetchone():
  cursor=s.run(db,"SELECT value FROM stock_notice_cursor WHERE id='history'").fetchone();start=float(cursor['value']) if cursor else 0
  for r in s.run(db,"SELECT id,batch,rule,menu,segments,strict,occurred,payload FROM stock_notice_events WHERE batch='daily-events' AND occurred>=? AND occurred<? ORDER BY occurred,id",(start,cutoff)).fetchall():
   if r['rule'] in cfg['rules']:out.append({**dict(r),'batch':daily})
  if 'due' in cfg['rules']:
   for r in s.run(db,'SELECT id,due,segments,payload FROM stock_notice_due WHERE due<=? ORDER BY due,id',(day,)).fetchall():
    out.append({'id':digest([daily,r['id']]),'batch':daily,'rule':'due','menu':3,'segments':r['segments'],'strict':0,'occurred':now,'payload':r['payload']})
 return out,daily,cutoff
def reports(s,db,candidates):
 output={}
 if not candidates:return output
 for person in people(s,db):
  groups=defaultdict(list)
  for e in candidates:
   if permitted(person,e):groups[(e['batch'],e['rule'])].append({**json.loads(e['payload']),'_segments':json.loads(e['segments']),'_strict':e['strict']})
  for (batch,rule),items in groups.items():
   output.setdefault((batch,person['email']),[]).append({'rule':rule,'title':RULES[rule][0],'count':len(items),'rows':items[:50],'scope':digest(person)})
 return output
def body(points,batch):
 parts=['Stock & Planning report','Source / batch: '+batch,'Dates and change timestamps use IST.']
 def line(record):return '; '.join(str(k)+': '+('—' if v is None else str(v)) for k,v in record.items())
 for p in points:
  parts.append('\n'+p['title']+' · '+str(p['count'])+' matching records')
  for row in p['rows']:
   parts.append('\n'+row['section']+'\n'+line(row['values']))
   if row.get('changes'):
    parts.append('Changed by: '+str(row.get('username',''))+' · '+str(row.get('changedAt','')))
    for field,change in sorted(row['changes'].items()):parts.append(field+': '+str(change['before'])+' → '+str(change['after']))
   if 'daysPending' in row:parts.append('QC pending: '+str(row['daysPending'])+' days · statement reference: '+row['referenceDate'])
   if row.get('forecast'):
    parts.append('Linked FG forecast / transfers / pending quantity:')
    parts.extend(line(r) for r in row['forecast'])
   if row.get('history'):
    parts.append('Pending movement history · '+str(row['historyCount'])+' records (up to 50 shown):')
    parts.extend(line(r) for r in row['history'])
   if row.get('table'):
    table=row['table'];parts.extend(line(dict(zip(table['headers'],r))) for r in table['rows'])
  if p['count']>len(p['rows']) and p['rule']!='batch_required':parts.append('First 50 matching records shown. Open the permitted table for all records.')
 return '\n'.join(parts)
def format_report(points,batch,use_ai=False):
 import notification_format as formatter
 if getattr(formatter,'REVISION',0)!=3:
  import importlib
  formatter=importlib.reload(formatter)
 compose=formatter.compose
 sections=[]
 def table(title,records,count=None):
  headers=list(dict.fromkeys(k for r in records for k in r))
  return {'title':title,'headers':headers,'rows':[[r.get(k) for k in headers] for r in records],'count':len(records) if count is None else count}
 for p in points:
  details=[];forecasts=[];history=[];custom=[];history_count=0
  for row in p['rows']:
   record=dict(row['values']);code=record.get('Material') or record.get('Component') or record.get('Material Code') or ''
   if row.get('changes'):
    record.update({'Changed by':row.get('username'),'Changed at (IST)':row.get('changedAt'),'Changes':'; '.join(k+': '+str(v['before'])+' → '+str(v['after']) for k,v in sorted(row['changes'].items()))})
   if 'daysPending' in row:record.update({'QC pending days':row['daysPending'],'Reference date':row['referenceDate']})
   details.append(record)
   forecasts.extend({'Notification material':code,**r} for r in row.get('forecast',[]))
   history.extend({'Notification material':code,**r} for r in row.get('history',[]));history_count+=row.get('historyCount',0)
   if row.get('table'):custom.append({**row['table'],'title':row['section'],'count':p['count']})
  tables=[table('Report context' if p['rule']=='batch_required' else 'Matched records',details,len(details) if p['rule']=='batch_required' else p['count'])]
  if forecasts:tables.append(table('Linked FG forecast, transfer and pending quantities',forecasts))
  if history:tables.append(table('Pending movement history',history,history_count))
  tables.extend(custom)
  trigger=RULES[p['rule']][1] if p.get('rule') in RULES else 'Saved worksheet notification policy'
  sections.append({'title':p['title'],'count':p['count'],'intro':['This section covers '+p['title']+'.','Results were captured for: '+trigger+'.','The tables show saved matching details within your permitted segment and section access.'],'bullets':[str(p['count'])+' matching records for this notification rule.'],'tables':tables})
 writer=None
 if use_ai:
  try:
   import grounded_ai
   key,model=grounded_ai.settings()
   if key:writer=lambda instruction,payload:grounded_ai.generate(key,model,instruction,payload,True,max_output_tokens=1600)
  except Exception:pass
 return compose('Stock & Planning · Combined notification report','Batch: '+batch+' · dates and timestamps in IST',sections,writer)

def custom_settings(s,db):
 if not s.sqlite:
  row=s.run(db,"SELECT (payload::jsonb->'email_rules')::text AS rules,(payload::jsonb->'email_schedule')::text AS schedule FROM portal_settings WHERE id='workspace'").fetchone()
  return {'rules':json.loads(row['rules'] or '[]') if row else [],'schedule':json.loads(row['schedule'] or '{}') if row else {}}
 row=s.run(db,"SELECT payload FROM portal_settings WHERE id='workspace'").fetchone()
 settings=json.loads(row['payload']) if row else {}
 return {'rules':settings.get('email_rules',[]),'schedule':settings.get('email_schedule',{})}
def custom_reports(s,db,daily,settings):
 """Preserve saved worksheet rules in the same daily message, if any are live.

Only installations with enabled custom worksheet rules need one version-cached
master payload on the first visit. The eight built-in rules never need it.
"""
 if settings['schedule'].get('enabled',True) is not True:return {}
 rules=[r for r in settings['rules'] if r.get('enabled')]
 if not rules:return {}
 revision=s.run(db,"SELECT version,updated_at,filename FROM datasets WHERE id='current'").fetchone()
 if not revision:return {}
 cached=getattr(s,'_dataset_payload_cache',None)
 cache_key=(revision['version'],revision['updated_at'],revision['filename'])
 if cached and cached[0]==cache_key:row=cached[1]
 else:
  row={**dict(revision),**dict(s.run(db,"SELECT payload,uploaded_by FROM datasets WHERE id='current'").fetchone())}
  s._dataset_payload_cache=(cache_key,row)
 data=json.loads(gzip.decompress(base64.b64decode(row['payload'])))
 from .segment_access import scope_data
 from .console_rules import points
 from .access import allowed
 names=['Summary','BOM Cost','Sales Data','Production Data','Forecast Planning','Forecast Need to Order List','Need to Order Sheet-B.O. PS']
 output={}
 for person in people(s,db):
  identity={'role':person['role'],'permissions':json.loads(person['permissions'] or '{}')}
  wanted=json.loads(person['allowed_segments']) if person['role']!='admin' and person['allowed_segments'] is not None else None
  visible=scope_data(data,wanted);tables=[];used=set()
  for t in visible.get('sheets',[])+visible.get('tables',[]):
   name=t['name'] if t['name'] not in used else t['name']+' (model)'
   if name in used:continue
   used.add(name);tables.append({**t,'name':name})
  for rule in rules:
   menus=[names.index(rule['section'])] if rule['section'] in names else list(range(7))
   if rule.get('recipient')!=person['email'] or not all(allowed(identity,i) for i in menus):continue
   matches=points([rule],tables)
   for report in matches:
    for p in report['points']:
     if p['count']:output.setdefault((daily,person['email']),[]).append({'rule':'custom','menus':menus,'title':p['title'],'count':p['count'],'scope':digest(person),'rows':[record_payload(p['title'],{'Matching records':p['count']},table=p['table'])]})
 return output
def demand_reports(s,db,daily):
 """One complete, recipient-scoped demand table in the existing daily digest.

 Source payloads and calculations are reused by version and access scope. No
 workbook is read when the rule is off, no open orders exist or nobody has access.
 """
 if 'batch_required' not in config(s,db)['rules']:return {}
 from .access import allowed
 from .pending_sales import build,unpack,REVISION as calculation_revision
 recipients=[]
 for person in people(s,db):
  identity={'role':person['role'],'permissions':json.loads(person['permissions'] or '{}'),
   'allowedSegments':None if person['role']=='admin' or person['allowed_segments'] is None else json.loads(person['allowed_segments'])}
  if allowed(identity,13):recipients.append((person,identity))
 if not recipients:return {}
 orders=s.run(db,"SELECT version FROM stock_open_orders WHERE id='current'").fetchone()
 master=s.run(db,"SELECT version,updated_at,filename FROM datasets WHERE id='current'").fetchone()
 if not orders or not master:return {}
 version=(master['version'],master['updated_at'],orders['version'],calculation_revision)
 cached=getattr(s,'_notice_demand_cache',None)
 if not cached or cached[0]!=version:
  master_key=(master['version'],master['updated_at'],master['filename'])
  saved=getattr(s,'_dataset_payload_cache',None)
  if saved and saved[0]==master_key:data=unpack(saved[1]['payload'])
  else:
   row=dict(s.run(db,"SELECT * FROM datasets WHERE id='current'").fetchone())
   s._dataset_payload_cache=(master_key,row);data=unpack(row['payload'])
  source=unpack(s.run(db,"SELECT payload FROM stock_open_orders WHERE id='current'").fetchone()['payload'])
  cached=(version,data,source,{})
  s._notice_demand_cache=cached
 output={}
 for person,identity in recipients:
  scope=digest(identity)
  if scope not in cached[3]:
   if len(cached[3])>=32:cached[3].clear()
   cached[3][scope]=build(cached[1],cached[2],identity)
  result=cached[3][scope]
  if not result['rows']:continue
  table={'headers':result['headers'],'rows':result['rows'],'complete':True}
  output.setdefault((daily,person['email']),[]).append({'rule':'batch_required','title':RULES['batch_required'][0],
   'count':len(table['rows']),'scope':digest(person),'rows':[record_payload('New Production Batch Required',
    {'Matching products / units':len(table['rows']),'Master workbook':master['filename'],'Notes':' '.join(result['notes']),'Review warnings':' '.join(result['warnings'])},table=table)]})
 return output

def info(s,actor,preview=False,now=None):
 now=time.time() if now is None else now
 with s.transaction() as db:
  s.require(db,actor,admin=True);schema(s,db)
  needs_baseline=not s.run(db,"SELECT id FROM stock_notice_sources WHERE id='master'").fetchone()
 if needs_baseline:
  current=s.get_dataset(actor)
  if current:
   with s.transaction() as db:
    s.require(db,actor,admin=True)
    master(s,db,current,baseline=True)
 with s.transaction() as db:
  s.require(db,actor,admin=True);schema(s,db);cfg=config(s,db)
  latest=s.run(db,"SELECT fingerprints FROM stock_notice_sources WHERE id='master'").fetchone()
  result={'config':cfg,'version':digest(cfg),'rules':[{'id':k,'title':v[0],'trigger':v[1]} for k,v in RULES.items()],
   'source':json.loads(latest['fingerprints']) if latest else {'warnings':['Upload a master workbook to establish a notification baseline.']},
   'jobs':[dict(r) for r in s.run(db,'SELECT batch,recipient,status,created,error FROM stock_notice_jobs ORDER BY created DESC,id LIMIT 30').fetchall()]}
  if preview:
   pending,daily,_=events(s,db,now,True);grouped=reports(s,db,pending)
   if not s.run(db,'SELECT id FROM stock_notice_batches WHERE id=?',(daily,)).fetchone():
    for report in (custom_reports(s,db,daily,custom_settings(s,db)),demand_reports(s,db,daily)):
     for k,p in report.items():grouped.setdefault(k,[]).extend(p)
   result['reports']=[{'batch':b,'recipient':email,'points':p,'body':body(p,b)} for (b,email),p in grouped.items()]
 return result
def save_config(s,actor,event):
 value=event.get('config');expected=event.get('version')
 if not isinstance(value,dict) or set(value)!=set(DEFAULT) or type(value['enabled']) is not bool:raise ValueError('Invalid notification configuration.')
 if value['policyRevision']!=3:raise ValueError('Reload current notification settings before saving.')
 if not isinstance(value['rules'],list) or set(value['rules'])-set(RULES):raise ValueError('Choose known notification rules.')
 for k in ('threshold','qcDays'):
  if type(value[k]) is not int or not 1<=value[k]<=1000000:raise ValueError('Use positive whole-number thresholds.')
 for k in ('packagingWords','packagingTypes','includeMaterials','excludeMaterials'):
  if not isinstance(value[k],list) or len(value[k])>200 or any(not isinstance(v,str) or not v.strip() or len(v)>100 for v in value[k]):raise ValueError('Use at most 200 nonempty matching terms or material codes.')
 with s.transaction() as db:
  s.require(db,actor,admin=True);schema(s,db);lock(s,db)
  if digest(config(s,db))!=expected:raise ValueError('Notification settings changed. Reload before saving.')
  s.run(db,"INSERT INTO stock_notice_config VALUES('current',?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",(dumps(value),))
  s.history_write(db,actor,'Stock notification settings',None,value)
 return info(s,actor)

def tick(s,actor,configuration,send,now=None):
 with s.transaction() as db:s.require(db,actor)
 return _dispatch(s,actor,configuration,send,now)

def _dispatch(s,actor,configuration,send,now=None):
 """Any authenticated visit may trigger; it never grants that visitor admin rights."""
 now=time.time() if now is None else now
 from .scheduled_delivery import configured
 if not configured(configuration):return {'sent':0,'state':'not_configured'}
 clock=datetime.fromtimestamp(now,IST)
 daily_ready=(clock.hour,clock.minute)>=(2,30)
 with s.transaction() as db:
  if not s.sqlite:
   s.run(db,"SET LOCAL lock_timeout = '2s'")
   s.run(db,"SET LOCAL statement_timeout = '8s'")
  if not lock(s,db,wait=False):return {'sent':0,'state':'busy'}
  if actor is not None:s.require(db,actor)
  schema(s,db);cfg=config(s,db)
  if not cfg['enabled']:return {'sent':0,'state':'preview_only'}
  # Expired claims may already have reached SMTP. Never automatically retry.
  s.run(db,"UPDATE stock_notice_jobs SET status='uncertain',error='Delivery outcome unknown; check sender logs.' WHERE status='sending' AND created<?",(now-300,))
  candidates,daily,cutoff=events(s,db,now,include_daily=daily_ready)
  grouped=reports(s,db,candidates)
  custom=custom_settings(s,db)
  if daily_ready and not s.run(db,'SELECT id FROM stock_notice_batches WHERE id=?',(daily,)).fetchone():
   for report in (custom_reports(s,db,daily,custom),demand_reports(s,db,daily)):
    for k,p in report.items():grouped.setdefault(k,[]).extend(p)
  prepared={}
  for (batch,email),points in grouped.items():
   identifier=digest([batch,email]);payload={'points':points,'body':body(points,batch),'config':digest(cfg),'custom':digest(custom)}
   inserted=s.run(db,'INSERT INTO stock_notice_jobs VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING',(identifier,batch,email,dumps(payload),'queued',now,''))
   if inserted.rowcount==1:prepared[identifier]=payload
  uploads=[r['batch'] for r in s.run(db,"SELECT DISTINCT e.batch FROM stock_notice_events e WHERE e.batch<>'daily-events' AND NOT EXISTS (SELECT 1 FROM stock_notice_batches b WHERE b.id=e.batch)").fetchall()]
  for batch in ({daily,*uploads} if daily_ready else set(uploads)):
   s.run(db,"INSERT INTO stock_notice_batches VALUES(?,?,'checked') ON CONFLICT(id) DO NOTHING",(batch,now))
  if daily_ready:s.run(db,"INSERT INTO stock_notice_cursor VALUES('history',?) ON CONFLICT(id) DO UPDATE SET value=excluded.value",(str(cutoff),))
  pending=[dict(r) for r in s.run(db,"SELECT id,batch,recipient FROM stock_notice_jobs WHERE status='queued' AND (batch NOT LIKE ? OR ?=1) ORDER BY created,batch,recipient LIMIT 20",('daily:%',int(daily_ready))).fetchall()]
 sent=0
 for job in pending:
  payload=prepared.get(job['id'])
  if payload is None:
   with s.transaction() as db:payload=json.loads(s.run(db,'SELECT payload FROM stock_notice_jobs WHERE id=?',(job['id'],)).fetchone()['payload'])
  with s.transaction() as db:
   if actor is not None:s.require(db,actor)
   lock(s,db);fresh=config(s,db)
   person=next((p for p in people(s,db) if p['email']==job['recipient']),None)
   # Revalidate rights against the exact stored rows, including section access.
   from .access import allowed
   identity={'role':person['role'],'permissions':json.loads(person['permissions'] or '{}')} if person else {}
   allowed_rows=bool(person) and all(p['scope']==digest(person) for p in payload['points']) and all(all(allowed(identity,i) for i in p['menus']) if p['rule']=='custom' else allowed(identity,13) if p['rule']=='batch_required' else all(permitted(person,{'menu':RULES[p['rule']][2],'segments':dumps(row.get('_segments',[])),'strict':row.get('_strict',0)}) for row in p['rows']) for p in payload['points'])
   if not fresh['enabled'] or digest(fresh)!=payload['config'] or digest(custom_settings(s,db))!=payload['custom'] or not allowed_rows:
    s.run(db,"UPDATE stock_notice_jobs SET status='cancelled',error='Settings or recipient access changed; preview again.' WHERE id=? AND status='queued'",(job['id'],));continue
   claim=s.run(db,"UPDATE stock_notice_jobs SET status='sending',created=? WHERE id=? AND status='queued'",(now,job['id']))
   if claim.rowcount!=1:continue
  status='sent';error=''
  try:
   label='Daily report' if job['batch'].startswith('daily:') else 'Sales workbook update' if job['batch'].startswith('sales:') else 'Master workbook update'
   message=format_report(payload['points'],job['batch'],use_ai=True)
   send(job['recipient'],'Stock & Planning · '+label+' · '+today(now),message,job['id']);sent+=1
  except Exception:status='uncertain';error='Provider may have accepted this report. Inspect sender logs before retrying.'
  with s.transaction() as db:
   s.run(db,"UPDATE stock_notice_jobs SET status=?,error=? WHERE id=? AND status='sending'",(status,error,job['id']))
 return {'sent':sent,'state':'checked' if daily_ready else 'waiting_for_schedule'}

