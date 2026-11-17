"""Independent monthly sales snapshots; live access checks and bounded version caches."""
import base64,copy,gzip,hashlib,json,math,threading,time,unicodedata
from collections import OrderedDict
from datetime import date,datetime
from .store import AccessDenied
from .pnl_import import open_saved,norm,segment,code
REVISION=10
KINDS=('primary','secondary')
_lock=threading.RLock()

def authorize(store,actor,admin=False):
    with store.transaction() as db:
        identity=store.require(db,actor,admin=admin)
        if identity['role']!='admin' and not identity['permissions'].get('menu_11',False):raise AccessDenied('Your administrator has not granted Sales access.')
        return identity

def schema(store):
    with _lock:
        if getattr(store,'_sales_schema',None)==REVISION:return
        with store.transaction() as db:
            store.run(db,'CREATE TABLE IF NOT EXISTS stock_sales_documents (kind TEXT PRIMARY KEY,filename TEXT NOT NULL,version TEXT NOT NULL,updated_at DOUBLE PRECISION NOT NULL,updated_by TEXT NOT NULL,metadata TEXT NOT NULL,payload TEXT NOT NULL)')
        store._sales_schema=REVISION;store._sales_cache=OrderedDict()

def kind(value):
    if value not in KINDS:raise ValueError('Choose Primary Sales or Secondary Sales.')
    return value

def header_values(values):
    headers=[]
    for i,v in enumerate(values):
        name=str(v or '').replace('\n',' ').strip() or f'Column {i+1}'
        name=name[:150];base=name;n=1
        while name in headers:n+=1;name=f'{base} ({n})'
        headers.append(name)
    return headers

def preview(raw,filename,header_row=1):
    if type(header_row) is not int or not 1<=header_row<=50:raise ValueError('Header row must be between 1 and 50.')
    wb=open_saved(raw,filename)
    try:
        out=[]
        for ws in wb:
            if ws.sheet_state!='visible':continue
            if ws.max_column>150:raise ValueError('Use a sales table with at most 150 columns.')
            headers=header_values(next(ws.iter_rows(min_row=header_row,max_row=header_row,values_only=True),()))
            out.append({'name':ws.title,'headers':headers,'rows':max(0,ws.max_row-header_row)})
        if not out:raise ValueError('The workbook has no visible worksheet.')
        return {'sheets':out}
    finally:wb.close()

def parse(raw,filename,sheet,header_row,mapping,segment_column=None):
    if type(header_row) is not int or not 1<=header_row<=50:raise ValueError('Header row must be between 1 and 50.')
    wb=open_saved(raw,filename)
    try:
        if sheet not in wb.sheetnames:raise ValueError('Choose a worksheet from the selected workbook.')
        ws=wb[sheet]
        if ws.sheet_state!='visible':raise ValueError('Choose a visible sales worksheet.')
        if ws.max_column>150 or ws.max_row-header_row>100_000:raise ValueError('Use at most 100,000 sales rows and 150 columns.')
        rows=ws.iter_rows(min_row=header_row,values_only=True);headers=header_values(next(rows,()))
        if not headers:raise ValueError('The selected header row is empty.')
        sku=next((i for i,h in enumerate(headers) if norm(h) in {'material','materialcode','materialnumber','sku','skucode','fgcode','materialno'}),None)
        supplied=segment_column not in (None,'')
        if supplied and segment_column not in headers:raise ValueError('Choose a valid segment column.')
        si=headers.index(segment_column) if supplied else next((i for i,h in enumerate(headers) if norm(h) in {'segment','segmentname','businesssegment','productsegment'}),None)
        if si is None:
            name='Segment'
            while name in headers:name='Planning '+name
            si=len(headers);headers.append(name)
        values=[];unmapped=0
        for source in rows:
            if not any(v is not None and str(v).strip() for v in source):continue
            row=[]
            for i,v in enumerate(source):
                if isinstance(v,(date,datetime)):v=v.isoformat()[:10]
                elif isinstance(v,bool):v='TRUE' if v else 'FALSE'
                elif isinstance(v,(int,float)):
                    if not math.isfinite(v):raise ValueError('Sales values must be finite numbers.')
                    if norm(headers[i]) in {'material','materialcode','materialnumber','sku','skucode','fgcode','billingdoc','billingdocument','ponumber','plant','salesorg','sostoitm'}:v=code(v)
                elif v is not None:v=str(v)[:10000]
                row.append(v)
            row=(row+[None]*len(headers))[:len(headers)]
            if row[si] is not None and str(row[si]).strip():tag=segment(row[si])
            else:
                tags=mapping.get(code(row[sku]),[]) if sku is not None else []
                tag=tags[0] if len(tags)==1 else 'Unmapped'
            row[si]=tag;unmapped+=tag=='Unmapped';values.append(row)
        if not values:raise ValueError('The selected worksheet has no sales records below its header.')
        return {'headers':headers,'rows':values,'segmentIndex':si,'unmapped':unmapped}
    finally:wb.close()

def metadata(store,actor):
    authorize(store,actor);schema(store)
    with store.transaction() as db:
        store.require(db,actor)
        rows=[dict(r) for r in store.run(db,'SELECT kind,filename,version,updated_at,updated_by,metadata FROM stock_sales_documents ORDER BY kind').fetchall()]
    from .source_freshness import uploaded
    return [uploaded(store,actor,'sales:'+r['kind'],r) for r in rows]

def all_segments(store,actor):
    authorize(store,actor,True)
    return sorted({s for r in metadata(store,actor) for s in json.loads(r['metadata'])['segments'] if s!='Unmapped'})

def save(store,actor,event):
    authorize(store,actor,True);schema(store);k=kind(event.get('kind'));filename=str(event.get('filename','Sales.xlsx'))[:255]
    raw=decode(event.get('content'));header_row=event.get('headerRow',1)
    # Resolve planning segment tags once on upload, not on every viewer login.
    from .pnl import planning_data,source_mapping
    current=planning_data(store,actor)
    mapping=source_mapping((current or {}).get('data',{'tables':[]}),{'mapping':{}})
    value=parse(raw,filename,event.get('sheet'),header_row,mapping,event.get('segmentColumn'))
    blob=json.dumps(value,allow_nan=False,separators=(',',':')).encode()
    if len(blob)>16_000_000:raise ValueError('Prepared sales data exceeds 16 MB. Narrow the file scope.')
    version=hashlib.sha256(blob).hexdigest();now=time.time()
    meta={'headers':value['headers'],'rows':len(value['rows']),'segments':sorted({r[value['segmentIndex']] for r in value['rows']}),'unmapped':value['unmapped'],'sheet':event.get('sheet'),'headerRow':header_row,'mappingVersion':(current or {}).get('version')}
    eligible=bom_fg_index(store,actor)[0] if k=='primary' else None
    args=(filename,version,now,actor.username,json.dumps(meta),base64.b64encode(gzip.compress(blob)).decode())
    with store.transaction() as db:
        store.require(db,actor,admin=True)
        from .notification_rules import schema as notification_schema,sales as capture_notifications
        notification_schema(store,db)
        if not store.run(db,'SELECT id FROM stock_notice_sources WHERE id=?',('sales:'+k,)).fetchone():
            previous=store.run(db,'SELECT version,payload,updated_at FROM stock_sales_documents WHERE kind=?',(k,)).fetchone()
            if previous:
                old_value=json.loads(gzip.decompress(base64.b64decode(previous['payload'])))
                capture_notifications(store,db,k,previous['version'],old_value,previous['updated_at'],eligible,baseline=True)
        expected=event.get('expected')
        if expected is None:
            changed=store.run(db,'INSERT INTO stock_sales_documents VALUES(?,?,?,?,?,?,?) ON CONFLICT(kind) DO NOTHING',(k,*args)).rowcount
        else:changed=store.run(db,'UPDATE stock_sales_documents SET filename=?,version=?,updated_at=?,updated_by=?,metadata=?,payload=? WHERE kind=? AND version=?',(*args,k,expected)).rowcount
        if changed!=1:raise ValueError('This sales file changed. Reload Sales before replacing it.')
        from .notification_rules import sales as capture_notifications
        capture_notifications(store,db,k,version,value,now,eligible)
        store._log(db,actor.username,'sales_'+k+'_uploaded',filename,actor.session_id,{'version':version,'rows':len(value['rows'])})
        store.history_write(db,actor,'Sales '+k,{'version':expected},{'version':version,'rows':len(value['rows'])})
    with _lock:
        store._sales_cache[(k,version)]=(copy.deepcopy(value),len(blob))
        while len(store._sales_cache)>4 or sum(v[1] for v in store._sales_cache.values())>32_000_000:store._sales_cache.popitem(last=False)
    return {'ok':True,'version':version,'unmapped':value['unmapped']}

def decode(content):
    if not isinstance(content,str) or len(content)>34_000_000:raise ValueError('Choose an XLSX file under 25 MB.')
    try:return base64.b64decode(content,validate=True)
    except (ValueError,TypeError):raise ValueError('Invalid workbook upload.') from None

def material_key(value):
    """Match SKU case/outer whitespace without dropping punctuation or leading zeros."""
    text=unicodedata.normalize('NFKC',str(value) if value is not None else '').replace('\u200b','').strip()
    whole,point,fraction=text.partition('.')
    if point and whole.lstrip('+-').isdigit() and fraction and not fraction.strip('0'):text=whole
    return text.casefold()

def bom_source_index(store,actor):
    """Membership in BOM parent/FG fields only; never infer eligibility from unrelated types."""
    authorize(store,actor)
    with store.transaction() as db:
        store.require(db,actor)
        meta=store.run(db,"SELECT version,updated_at,filename FROM datasets WHERE id='current'").fetchone()
        if not meta:return set(),{},None
        key=(meta['version'],meta['updated_at'],meta['filename'])
        with _lock:cached=getattr(store,'_sales_bom_index',None)
        if cached and cached[0]==(REVISION,key):return cached[1],cached[2],meta['version']
        shared=getattr(store,'_dataset_payload_cache',None)
        if shared and shared[0]==key:row=shared[1]
        else:
            row=store.run(db,"SELECT * FROM datasets WHERE id='current' AND version=?",(meta['version'],)).fetchone()
            if not row:raise ValueError('The BOM source changed. Reload Sales.')
            row=dict(row);store._dataset_payload_cache=(key,row)
    dataset=json.loads(gzip.decompress(base64.b64decode(row['payload'])))
    parents=set();mapping={}
    names={'bom','bomcost','bomdata','billofmaterial','billofmaterials'}
    for table in [*dataset.get('tables',[]),*dataset.get('sheets',[])]:
        if norm(table.get('name')) not in names:continue
        headers=[norm(h) for h in table['headers']]
        pi=next((i for i,h in enumerate(headers) if h in {'material','materialcode','materialnumber','materialno','fgcode','fgmaterial','fgmaterialcode','fgmaterialnumber'}),None)
        si=next((i for i,h in enumerate(headers) if h.endswith('sourcename')),next((i for i,h in enumerate(headers) if h=='segment'),None))
        if pi is not None:
            for r in table['rows']:
                if len(r)<=pi or r[pi] is None or not material_key(r[pi]):continue
                key_code=material_key(r[pi]);parents.add(key_code)
                tag=segment(r[si]) if si is not None and si<len(r) else ''
                if tag:mapping.setdefault(key_code,set()).add(tag)
    eligible=parents
    with _lock:store._sales_bom_index=((REVISION,key),eligible,{k:sorted(v) for k,v in mapping.items()})
    return eligible,{k:sorted(v) for k,v in mapping.items()},meta['version']

def bom_fg_index(store,actor):
    parents,_,version=bom_source_index(store,actor)
    return parents,version

def read(store,actor,event):
    identity=authorize(store,actor);schema(store);k=kind(event.get('kind'))
    with store.transaction() as db:
        store.require(db,actor)
        meta=store.run(db,'SELECT kind,filename,version,updated_at,updated_by,metadata FROM stock_sales_documents WHERE kind=?',(k,)).fetchone()
    if not meta:return {'available':False,'kind':k,'admin':identity['role']=='admin'}
    meta=dict(meta);info=json.loads(meta.pop('metadata'))
    allowed=identity.get('allowedSegments');scope=None if allowed is None else sorted({segment(s) for s in allowed})
    # Unchanged reads require only the BOM source version, not its payload/index.
    with store.transaction() as db:
        store.require(db,actor)
        master=store.run(db,"SELECT version FROM datasets WHERE id='current'").fetchone()
    bom_version=master['version'] if master else None
    version=hashlib.sha256(json.dumps([REVISION,k,meta['version'],meta['updated_at'],meta['filename'],scope,identity['role']=='admin',bom_version]).encode()).hexdigest()
    common={'available':True,'kind':k,'version':version,'source':meta,'admin':identity['role']=='admin','bomVersion':bom_version}
    if identity['role']=='admin':common['uploadInfo']=info
    if event.get('knownVersion')==version:
        live=authorize(store,actor)
        with store.transaction() as db:
            store.require(db,actor)
            current=store.run(db,"SELECT version FROM datasets WHERE id='current'").fetchone()
            current_sales=store.run(db,'SELECT version FROM stock_sales_documents WHERE kind=?',(k,)).fetchone()
        if live['role']!=identity['role'] or live.get('allowedSegments')!=identity.get('allowedSegments') or live['permissions']!=identity['permissions'] or (current['version'] if current else None)!=bom_version or not current_sales or current_sales['version']!=meta['version']:
            raise ValueError('Sales, BOM or access changed. Reload Sales.')
        return {**common,'notModified':True}
    fg,bom_mapping,index_version=bom_source_index(store,actor)
    if index_version!=bom_version:raise ValueError('The BOM source changed. Reload Sales.')
    key=(k,meta['version'])
    with _lock:cached=store._sales_cache.get(key)
    if cached:value=copy.deepcopy(cached[0])
    else:
        with store.transaction() as db:
            store.require(db,actor)
            row=store.run(db,'SELECT payload FROM stock_sales_documents WHERE kind=? AND version=?',(k,meta['version'])).fetchone()
        if not row:raise ValueError('The sales source changed. Reload Sales.')
        raw=gzip.decompress(base64.b64decode(row['payload']));value=json.loads(raw)
        with _lock:
            store._sales_cache[key]=(copy.deepcopy(value),len(raw))
            while len(store._sales_cache)>4 or sum(v[1] for v in store._sales_cache.values())>32_000_000:store._sales_cache.popitem(last=False)
    rows=value['rows'];si=value['segmentIndex']
    if k=='primary':
        sku=next((i for i,h in enumerate(value['headers']) if norm(h) in {'material','materialcode','materialnumber','sku','skucode','fgcode','materialno'}),None)
        rows=[r for r in rows if sku is not None and material_key(r[sku]) in fg]
        common['note']='A Material/SKU/FG Code column is required to match Primary Sales to the BOM.' if sku is None else 'Primary Sales matches Material/SKU directly to the available BOM parent FG-code list. Component-only codes are excluded.' if bom_version else 'Upload the planning BOM to display matched Primary Sales SKUs.'
    if scope is not None:rows=[r for r in rows if r[si] in scope and r[si]!='Unmapped']
    # Enrich only already-authorized rows. Shared BOM membership never duplicates a
    # transaction and must not reveal segment names outside the live account scope.
    sku=next((i for i,h in enumerate(value['headers']) if norm(h) in {'material','materialcode','materialnumber','sku','skucode','fgcode','materialno'}),None)
    header='BOM Segment'
    while header in value['headers']:header+=' (Source.Name)'
    enriched=[]
    for row in rows:
        tags=bom_mapping.get(material_key(row[sku]),[]) if sku is not None else []
        if scope is not None:tags=[tag for tag in tags if tag in scope]
        enriched.append(row+[' / '.join(tags) or 'Unmapped segment'])
    authorize(store,actor)
    with store.transaction() as db:
        live=store.require(db,actor)
        current=store.run(db,"SELECT version FROM datasets WHERE id='current'").fetchone()
        current_sales=store.run(db,'SELECT version FROM stock_sales_documents WHERE kind=?',(k,)).fetchone()
    if live['role']!=identity['role'] or live.get('allowedSegments')!=identity.get('allowedSegments') or live['permissions']!=identity['permissions'] or (current['version'] if current else None)!=bom_version or not current_sales or current_sales['version']!=meta['version']:
        raise ValueError('Sales, BOM or access changed. Reload Sales.')
    from .source_freshness import cached,table_summary
    source_dates=cached(store,actor,'sales-view:'+k,version,lambda:table_summary({'headers':value['headers'],'rows':rows}))
    common={**common,'source':{**common['source'],**source_dates}}
    return {**common,'headers':value['headers']+[header],'rows':enriched,'segmentIndex':si,'segments':sorted({r[si] for r in rows}),'bomSegmentColumn':header}

def handle(store,actor,event):
    action=event.get('action');authorize(store,actor)
    if action=='sales_read':return read(store,actor,event)
    if action=='sales_upload':return save(store,actor,event)
    if action=='sales_preview':
        authorize(store,actor,True)
        return preview(decode(event.get('content')),str(event.get('filename','Sales.xlsx')),event.get('headerRow',1))
    raise ValueError('Unknown Sales operation.')

def summarize(store,actor,plan):
    """Read-only assistant aggregation over the same authorized sales snapshot."""
    data=read(store,actor,{'kind':plan.get('kind')})
    if not data['available']:raise ValueError('Upload the selected sales type first.')
    rows=data['rows'];headers=data['headers'];stat=plan.get('statistic','count')
    if stat not in ('count','sum','average','min','max'):raise ValueError('Choose count, sum, average, min or max.')
    def column(value):
        matches=[i for i,h in enumerate(headers) if norm(h)==norm(value)]
        if len(matches)!=1:raise ValueError('Choose an exact sales column name.')
        return matches[0]
    date_group=plan.get('date_group')
    group=date_group.get('alias','Month') if isinstance(date_group,dict) else plan.get('group') or headers[data['segmentIndex']]
    gi=None if date_group else column(group)
    vi=column(plan.get('value')) if stat!='count' else None
    requested=plan.get('segments',[])
    if not isinstance(requested,list) or any(not isinstance(s,str) for s in requested):raise ValueError('Choose valid sales segments.')
    if requested:rows=[r for r in rows if r[data['segmentIndex']] in requested]
    query=plan.get('search','')
    if not isinstance(query,str) or len(query)>200:raise ValueError('Use a search phrase under 200 characters.')
    if query:rows=[r for r in rows if any(query.casefold() in str(v or '').casefold() for v in r)]
    if date_group:
        from grounded_ai import execute_query
        from .calendar_group import schema
        table={'id':'MONTH_SALES','name':str(plan.get('kind',''))+' Sales','headers':headers,'rows':rows};date_group=schema(table,date_group);group=date_group['alias']
        metric={'column':headers[vi] if vi is not None else '*','op':{'average':'mean'}.get(stat,stat)};label=metric['op']+'('+metric['column']+')'
        metrics=[metric] if stat=='count' else [metric,{'column':'*','op':'count'}]
        result=execute_query([table],{'table':table['id'],'date_group':date_group,'group_by':[group],'metrics':metrics,'sort_by':group,'descending':False,'limit':20},all_rows=True)
        if result['result_rows']>200:raise ValueError('More than 200 months. Narrow the sales period.')
        return {'headers':[group,stat.title()+(' '+headers[vi] if vi is not None else ' records'),'Source rows'],'rows':[[r[group],r[label],r['count(*)']] for r in result['records']],'source':data['source'],'limitations':'Calendar months keep their years. Saved invoice signs and cancellation flags are retained; no net-sales adjustment or unit conversion is assumed. '+result['note']}
    groups={}
    for row in rows:groups.setdefault(str(row[gi] if row[gi] is not None else 'Blank'),[]).append(row)
    if len(groups)>200:raise ValueError('More than 200 groups. Narrow the sales search or group by a broader column.')
    out=[]
    for name,rr in sorted(groups.items()):
        values=[r[vi] for r in rr if type(r[vi]) in (int,float)] if vi is not None else []
        value=len(rr) if stat=='count' else (None if not values else sum(values) if stat=='sum' else sum(values)/len(values) if stat=='average' else min(values) if stat=='min' else max(values))
        out.append([name,value,len(rr)])
    return {'headers':[headers[gi],stat.title()+(' '+headers[vi] if vi is not None else ' records'),'Source rows'],'rows':out,'source':data['source'],'limitations':'Saved source values and cancellation flags are retained. No net-sales sign adjustment or unit conversion is assumed; filter compatible units/statuses before interpreting totals.'}

