"""Versioned combined sales/forecast demand, FG shortages and category evidence."""
import base64,copy,gzip,hashlib,json,math,re,threading,time
from collections import OrderedDict,defaultdict
from datetime import date,datetime
REVISION=4
_lock=threading.RLock()
REASONS={'creditholdnostock':'Credit Hold No Stock','releasenostock':'Credit Release No Stock'}
BATCH_HEADERS=['Product Code','Description','Quantity','Unit','Suggestions','Pending Sales + Forecast Qty','FG Stock Applied to Sales','Segment']
def norm(v):return re.sub('[^a-z0-9]','',str(v or '').casefold())
def sku(v):
 from .sales import material_key
 return material_key(v)
def number(v):
 if isinstance(v,bool):raise ValueError('Quantity must be numeric.')
 try:n=float(v)
 except (TypeError,ValueError):raise ValueError('Pending Qty must contain numeric quantities.') from None
 if not math.isfinite(n) or n<0:raise ValueError('Pending Qty must be finite and non-negative.')
 return n
def pack(v):return base64.b64encode(gzip.compress(json.dumps(v,allow_nan=False,separators=(',',':')).encode())).decode()
def unpack(v):return json.loads(gzip.decompress(base64.b64decode(v)))
def schema(store):
 with _lock:
  if getattr(store,'_pending_sales_schema',None)==REVISION:return
  with store.transaction() as db:
   store.run(db,'CREATE TABLE IF NOT EXISTS stock_open_orders (id TEXT PRIMARY KEY,filename TEXT NOT NULL,version TEXT NOT NULL,updated_at DOUBLE PRECISION NOT NULL,updated_by TEXT NOT NULL,payload TEXT NOT NULL)')
   store.run(db,'CREATE TABLE IF NOT EXISTS stock_pending_sales_cache (cache_key TEXT PRIMARY KEY,payload TEXT NOT NULL,created_at DOUBLE PRECISION NOT NULL)')
  store._pending_sales_schema=REVISION;store._pending_sales_values=OrderedDict();store._pending_sales_sources=OrderedDict()
def parse(raw,filename):
 from .pnl_import import open_saved
 from .sales import header_values
 wb=open_saved(raw,filename)
 try:
  candidates=[]
  for ws in wb:
   if ws.sheet_state!='visible':continue
   rows=ws.iter_rows(values_only=True);headers=header_values(next(rows,()))
   indexes={norm(h):i for i,h in enumerate(headers)}
   if {'material','pendingqty','remarks','salesunit'}.issubset(indexes):candidates.append((ws,headers,indexes))
  if len(candidates)!=1:raise ValueError('Choose a workbook with exactly one visible table containing Material, Pending Qty, Remarks and Sales unit on row 1.')
  ws,headers,ix=candidates[0]
  if ws.max_row>100001 or ws.max_column>150:raise ValueError('Use at most 100,000 order rows and 150 columns.')
  out=[];seen={}
  for line,rawrow in enumerate(ws.iter_rows(min_row=2,values_only=True),2):
   if not any(v is not None for v in rawrow):continue
   row=[]
   for v in rawrow:
    if isinstance(v,(date,datetime)):v=v.isoformat()
    elif isinstance(v,float) and not math.isfinite(v):raise ValueError('The report contains a non-finite number.')
    elif v is not None and not isinstance(v,(str,int,float,bool)):v=str(v)
    row.append(v)
   row=(row+[None]*len(headers))[:len(headers)]
   code=sku(row[ix['material']]);reason=REASONS.get(norm(row[ix['remarks']]))
   if code and reason:
    row[ix['material']]=str(row[ix['material']]).strip();row[ix['pendingqty']]=number(row[ix['pendingqty']])
    if not str(row[ix['salesunit']] or '').strip():raise ValueError(f'Missing Sales unit on row {line}.')
    key=tuple(str(row[ix[k]] or '').strip() for k in ('salesdocument','salesdocumentitem','material') if k in ix)
    if 'salesdocument' in ix and 'salesdocumentitem' in ix:
     if key in seen:raise ValueError(f'Duplicate sales document/item/material on rows {seen[key]} and {line}. Resolve duplicates before uploading.')
     seen[key]=line
   out.append(row)
  if not out:raise ValueError('The open-order report is empty.')
  return {'name':ws.title,'headers':headers,'rows':out,'indexes':ix}
 finally:wb.close()
def info(store,actor):
 schema(store)
 with store.transaction() as db:
  store.require(db,actor)
  row=store.run(db,"SELECT filename,version,updated_at,updated_by FROM stock_open_orders WHERE id='current'").fetchone()
 return dict(row) if row else None
def save(store,actor,event):
 with store.transaction() as db:store.require(db,actor,admin=True)
 schema(store)
 from .sales import decode
 filename=str(event.get('filename','Open orders.xlsx'))[:255];raw=decode(event.get('content'))
 if len(raw)>25_000_000:raise ValueError('Choose a workbook under 25 MB.')
 value=parse(raw,filename);payload=pack(value);version=hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
 if len(payload)>24_000_000:raise ValueError('The prepared open-order report is too large.')
 with store.transaction() as db:
  store.require(db,actor,admin=True)
  old=store.run(db,"SELECT version FROM stock_open_orders WHERE id='current'").fetchone()
  if (old['version'] if old else None)!=event.get('expected'):raise ValueError('The open-order report changed. Reopen Uploads before replacing it.')
  store.run(db,"INSERT INTO stock_open_orders(id,filename,version,updated_at,updated_by,payload) VALUES('current',?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET filename=excluded.filename,version=excluded.version,updated_at=excluded.updated_at,updated_by=excluded.updated_by,payload=excluded.payload",(filename,version,time.time(),actor.username,payload))
  store._log(db,actor.username,'open_orders_uploaded',filename,actor.session_id,{'version':version,'rows':len(value['rows'])})
 return {'ok':True,'version':version,'rows':len(value['rows'])}
def context(store,actor):
 schema(store)
 from .access import allowed
 from .store import AccessDenied
 with store.transaction() as db:
  identity=store.require(db,actor)
  if not allowed(identity,0):raise AccessDenied('Your administrator has disabled Stock overview access.')
  master=store.run(db,"SELECT version,updated_at FROM datasets WHERE id='current'").fetchone()
  source=store.run(db,"SELECT filename,version,updated_at FROM stock_open_orders WHERE id='current'").fetchone()
 access=[identity['role'],identity['permissions'],identity.get('allowedSegments')]
 key=hashlib.sha256(json.dumps([REVISION,dict(master) if master else None,dict(source) if source else None,access],sort_keys=True,default=str).encode()).hexdigest()
 return key,identity,dict(source) if source else None
def source(store,actor,version):
 if not version:return None
 with _lock:cached=store._pending_sales_sources.get(version)
 if cached is not None:return cached
 with store.transaction() as db:
  store.require(db,actor);row=store.run(db,"SELECT version,payload FROM stock_open_orders WHERE id='current'").fetchone()
 if not row or row['version']!=version:raise ValueError('Open orders changed while loading. Retry.')
 value=unpack(row['payload'])
 with _lock:
  store._pending_sales_sources[version]=value
  while len(store._pending_sales_sources)>2:store._pending_sales_sources.popitem(last=False)
 return value

def master_data(store,actor):
 """Internal full-source read; build filters the complete contributing SKU scope."""
 with store.transaction() as db:
  store.require(db,actor)
  meta=store.run(db,"SELECT version,updated_at,filename FROM datasets WHERE id='current'").fetchone()
  if not meta:return {'sheets':[],'tables':[]}
  key=(meta['version'],meta['updated_at'],meta['filename']);cached=getattr(store,'_dataset_payload_cache',None)
  if cached and cached[0]==key:row=cached[1]
  else:
   row=store.run(db,"SELECT * FROM datasets WHERE id='current' AND version=?",(meta['version'],)).fetchone()
   if not row:raise ValueError('Master workbook changed while loading demand. Retry.')
   row=dict(row);store._dataset_payload_cache=(key,row)
 return unpack(row['payload'])

def build(data,orders,identity):
 """Apply stock once to sales, then add forecast pending with category evidence."""
 from workbook import segment_map
 from .access import allowed
 from .model_views import apply
 data=apply(data);mapping={sku(k):sorted(v) for k,v in segment_map(data.get('tables',[])).items()}
 permitted=identity.get('allowedSegments');wanted=None if permitted is None else set(permitted)
 def visible(code):return wanted is None or bool(mapping.get(code)) and set(mapping[code]).issubset(wanted)
 stocks=defaultdict(set);descriptions={};units=defaultdict(set)
 sheets=data.get('sheets',[])
 for r in sheets[0]['rows'] if sheets else []:
  if not r:continue
  k=sku(r[0]);descriptions[k]=r[1] if len(r)>1 else ''
  if len(r)>2 and isinstance(r[2],(int,float)) and math.isfinite(r[2]):stocks[k].add(float(r[2]))
 for t in data.get('tables',[])+sheets:
  hs=[norm(h) for h in t['headers']]
  ci=next((i for i,h in enumerate(hs) if h in ('material','materialcode','materialnumber','fgcode')),None)
  ui=next((i for i,h in enumerate(hs) if h in ('baseunitofmeasure','baseunit','baseuom')),None)
  if ci is not None and ui is not None:
   for r in t['rows']:
    if len(r)>max(ci,ui) and r[ui]:units[sku(r[ci])].add(str(r[ui]).strip().upper())
 bom_codes=set()
 for t in data.get('tables',[]):
  hs=[norm(h) for h in t['headers']]
  if norm(t['name']) in ('bom','bomcost') and 'material' in hs:
   ci=hs.index('material');bom_codes.update(sku(r[ci]) for r in t['rows'] if len(r)>ci)
 groups={};warnings=[]
 if orders:
  ix=orders['indexes']
  for r in orders['rows']:
   k=sku(r[ix['material']]);reason=REASONS.get(norm(r[ix['remarks']]))
   if not k or not reason or not visible(k):continue
   qty=r[ix['pendingqty']]
   if qty<=0:continue
   unit=str(r[ix['salesunit']]).strip().upper();key=(k,unit)
   g=groups.setdefault(key,{'code':str(r[ix['material']]),'description':r[ix.get('description',ix['material'])],'unit':unit,'Credit Release No Stock':0.,'Credit Hold No Stock':0.})
   g[reason]+=qty
 summary={};batch=[];breakdowns=defaultdict(list);sales_allocations={}
 by_code=defaultdict(list)
 for (k,unit),g in groups.items():by_code[k].append(g)
 for k,gs in by_code.items():
  total=sum(g['Credit Release No Stock']+g['Credit Hold No Stock'] for g in gs)
  summary[k]={'quantity':total if len(gs)==1 else None,'units':[g['unit'] for g in gs],'code':gs[0]['code']}
  for g in gs:
   for reason in ('Credit Release No Stock','Credit Hold No Stock'):
    if g[reason]>0:breakdowns[k].append({'category':reason,'unit':g['unit'],'quantity':g[reason],'requiredQuantity':None,'stockApplied':None})
  stock=next(iter(stocks[k])) if len(stocks[k])==1 else None
  summary[k].update(stockQuantity=stock,bomMatched=k in bom_codes,workbookUnits=sorted(units[k]))
  if stock is None:
   warnings.append(gs[0]['code']+': current FG stock is missing or ambiguous; sales shortage not calculated.');continue
  for g in gs:
   if units[k]!={g['unit']}:
    warnings.append(g['code']+': sales unit '+g['unit']+' does not have one matching workbook base unit; sales shortage not calculated.');continue
   available=stock
   sales_allocations[(k,g['unit'])]={'gross':g['Credit Release No Stock']+g['Credit Hold No Stock'],'applied':min(stock,g['Credit Release No Stock']+g['Credit Hold No Stock'])}
   for reason in ('Credit Release No Stock','Credit Hold No Stock'):
    demand=g[reason]
    if demand<=0:continue
    applied=min(demand,available);available-=applied;need=demand-applied
    for detail in breakdowns[k]:
     if detail['category']==reason and detail['unit']==g['unit']:detail.update(requiredQuantity=max(0.,need),stockApplied=applied)
    if need>0:batch.append([g['code'],g['description'],need,g['unit'],reason,demand,applied,' / '.join(mapping.get(k,[])) or 'Unmapped'])
 # Forecast Pending Quantity already deducts transfers and FG stock once.
 if allowed(identity,4) and len(sheets)>4:
  from workbook import forecast_summary
  import pandas as pd
  forecast_rows=forecast_summary(pd.DataFrame(sheets[4]['rows'])).values.tolist() if sheets[4]['rows'] and len(sheets[4]['headers'])>=7 else []
  for r in forecast_rows:
   k=sku(r[0])
   if visible(k) and isinstance(r[5],(int,float)) and r[5]>0:
    unit=next(iter(units[k])) if len(units[k])==1 else 'Workbook unit'
    batch.append([r[0],r[1],r[5],unit,'Forecast demand',r[2],r[4],' / '.join(mapping.get(k,[])) or 'Unmapped'])
    breakdowns[k].append({'category':'Forecast demand','unit':unit,'quantity':r[5],'requiredQuantity':r[5],'stockApplied':0.})
    if k not in summary:summary[k]={'code':r[0],'stockQuantity':next(iter(stocks[k])) if len(stocks[k])==1 else None,'bomMatched':k in bom_codes,'workbookUnits':sorted(units[k])}
 for k,item in summary.items():
  details=breakdowns[k];labels=sorted({d['unit'] for d in details})
  item.update(units=labels,breakdown=details,salesQuantity=sum(d['quantity'] for d in details if d['category']!='Forecast demand') if len({d['unit'] for d in details if d['category']!='Forecast demand'})<=1 else None,forecastQuantity=sum(d['quantity'] for d in details if d['category']=='Forecast demand'),quantity=sum(d['quantity'] for d in details) if len(labels)==1 else None)
 combined={}
 for r in batch:
  key=(sku(r[0]),r[3]);allocation=sales_allocations.get(key,{'gross':0.,'applied':0.})
  row=combined.setdefault(key,[r[0],r[1],0.,r[3],[],allocation['gross'],allocation['applied'],r[7]])
  row[2]+=r[2];row[4].append(str(r[4])+': '+format(r[2],'.12g'))
  if r[4]=='Forecast demand':row[5]+=r[2]
 rows=[[*r[:4],'; '.join(r[4]),*r[5:]] for r in combined.values()]
 from .bom_prices import pack_index
 packs=pack_index(data)
 product_details={k:{'unit':next(iter(units[k])) if len(units[k])==1 else None,'packSize':next(iter(packs[k])) if len(packs.get(k,set()))==1 else None} for k in stocks if visible(k)}
 from .demand_readiness import build as readiness_build
 from .segment_access import scope_data
 readiness=readiness_build(scope_data(data,identity.get('allowedSegments')),rows) if allowed(identity,3) else {}
 return {'materialReadiness':readiness,'productDetails':product_details,'visibleStock':[k for k in stocks if visible(k)],'summary':summary,'headers':BATCH_HEADERS,'rows':rows,'components':batch,'warnings':warnings,'notes':['Combined requirement = positive sales shortage (credit hold + credit release no stock, less FG stock once) + positive forecast pending quantity. Suggestions show each contributing requirement category.','Stock Overview Pending Sales Quantity = credit hold no-stock Pending Qty + credit release no-stock Pending Qty + permitted forecast pending quantity. The drill-through shows both pending quantities and production requirements.','Forecast pending already deducts transfers and FG stock; do not deduct stock from it again. Sales and forecast are added together as requested, even if the underlying business demand overlaps.','Different units are never added. Missing stock or unit matches remain review warnings. Quantities are requirements, not a calculated count of batches.']}


def read(store,actor,event=None):
 event=event or {};key,identity,meta=context(store,actor)
 if event.get('known_stamp')==key:return {'stamp':key,'not_modified':True}
 with _lock:cached=store._pending_sales_values.get(key)
 if cached is None:
  with store.transaction() as db:
   store.require(db,actor);row=store.run(db,'SELECT payload FROM stock_pending_sales_cache WHERE cache_key=?',(key,)).fetchone()
  if row:cached=unpack(row['payload'])
  else:
   data=master_data(store,actor);orders=source(store,actor,meta['version'] if meta else None)
   cached=build(data,orders,identity)
   if context(store,actor)[0]!=key:raise ValueError('Workbook, open orders or permissions changed while loading. Retry.')
   with store.transaction() as db:
    store.require(db,actor);store.run(db,'INSERT INTO stock_pending_sales_cache(cache_key,payload,created_at) VALUES(?,?,?) ON CONFLICT(cache_key) DO NOTHING',(key,pack(cached),time.time()))
  with _lock:
   store._pending_sales_values[key]=cached
   while len(store._pending_sales_values)>12:store._pending_sales_values.popitem(last=False)
 return {'stamp':key,'not_modified':False,'source':meta,'result':copy.deepcopy(cached)}
def records(store,actor,event):
 key,identity,meta=context(store,actor)
 if event.get('stamp')!=key:raise ValueError('Demand data changed. Reopen the requirement before viewing records.')
 code=sku(event.get('material'));value=read(store,actor)['result']
 current=store.get_dataset(actor);data=(current or {}).get('data',{'sheets':[],'tables':[]})
 visible_stock=set(value.get('visibleStock',[]))
 if not code or not (code in value['summary'] or code in visible_stock or any(sku(r[0])==code for r in value['rows'])):raise ValueError('Choose a visible demand product.')
 kind=event.get('source','breakdown');unit=event.get('unit')
 if unit is not None and (not isinstance(unit,str) or len(unit)>100):raise ValueError('Invalid quantity unit.')
 if kind=='breakdown':
  details=value['summary'].get(code,{}).get('breakdown',[])
  table={'headers':['Category','Unit','Pending Quantity','Production Required','FG Stock Applied to Sales'],'rows':[[d['category'],d['unit'],d['quantity'],d['requiredQuantity'],d['stockApplied']] for d in details if not unit or d['unit'].casefold()==unit.casefold()]}
 elif kind=='orders':
  t=source(store,actor,meta['version'] if meta else None) or {'headers':[],'rows':[],'indexes':{}}
  ix=t.get('indexes',{});reason=event.get('reason')
  rows=[r for r in t['rows'] if sku(r[ix['material']])==code and norm(r[ix['remarks']]) in REASONS and (not reason or REASONS[norm(r[ix['remarks']])]==reason) and (not unit or str(r[ix['salesunit']]).strip().casefold()==unit.casefold())] if ix else []
  table={'headers':t['headers'],'rows':rows}
 elif kind=='forecast':
  from .access import require_menu
  require_menu(store,actor,4)
  t=data['sheets'][4];table={**t,'rows':[r for r in t['rows'] if sku(r[0])==code]}
 elif kind in ('stock','bom'):
  names=('stockdata','mb52') if kind=='stock' else ('bom','bomcost')
  candidates=[t for t in data.get('tables',[]) if norm(t['name']) in names]
  t=next((t for t in candidates if norm(t['name'])==names[0]),None)
  if not t:table={'headers':[],'rows':[]}
  else:
   ci=next((i for i,h in enumerate(t['headers']) if norm(h) in ('material','materialcode','materialnumber')),None)
   table={**t,'rows':[r for r in t['rows'] if ci is not None and sku(r[ci])==code]}
 else:raise ValueError('Choose Breakup, Orders, Forecast, Stock or BOM records.')
 if kind=='bom':
  from .access import require_menu
  require_menu(store,actor,1)
 if context(store,actor)[0]!=key:raise ValueError('Demand data changed while loading matching records. Retry.')
 if event.get('export') is True:
  store.require_permission(actor,'download');return {**table,'stamp':key,'total':len(table['rows'])}
 page=event.get('page',0)
 if type(page) is not int or page<0:raise ValueError('Invalid record page.')
 return {**table,'stamp':key,'rows':table['rows'][page*200:(page+1)*200],'total':len(table['rows']),'page':page}
