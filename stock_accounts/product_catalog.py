"""Versioned imported product catalogue and separately cached read-only snapshots."""
import hashlib,json,time,copy,threading,uuid
from collections import OrderedDict
from urllib.parse import urlsplit,urlunsplit
from .snapshot_sales import material_key
REVISION=6
_DETAIL_LOCK=threading.RLock()

def schema(store):
    if getattr(store,'_product_catalog_schema',False)==REVISION:return
    with store.transaction() as db:
        store.run(db,'CREATE TABLE IF NOT EXISTS stock_product_catalog (id TEXT PRIMARY KEY,version TEXT NOT NULL,updated_at DOUBLE PRECISION NOT NULL,payload TEXT NOT NULL)')
        store.run(db,'CREATE TABLE IF NOT EXISTS stock_product_snapshots (product_id TEXT PRIMARY KEY,version TEXT NOT NULL,updated_at DOUBLE PRECISION NOT NULL,payload TEXT NOT NULL)')
    store._product_catalog_schema=REVISION

def publish(store,actor,products,url):
    with store.transaction() as db:store.require(db,actor,admin=True)
    parsed=urlsplit(str(url or ''))
    if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password:url=''
    else:url=urlunsplit((parsed.scheme,parsed.netloc,parsed.path,'',''))
    rows=[];snapshots=[]
    for p in products:
        codes=sorted({str(r['code']).strip() for s in p.get('sections',[]) if s.get('kind')=='variants' for r in [*s.get('rows',[]),*(s.get('sfgRows',[]) if s.get('hasSfg') else [])] if r.get('code')})
        sections=copy.deepcopy(p.get('sections',[]))
        for section in sections:
            if section.get('kind')=='briefs':
                for row in section.get('rows',[]):row.pop('images',None);row.pop('image',None)
        links=[{'id':str(section.get('id',''))+':'+str(item.get('id','')),'section':section.get('title',''),'title':item.get('title',''),'status':item.get('status',''),'owner':item.get('owner',''),'due':item.get('due',''),'remark':item.get('remark',''),'evidence':item['evidence']} for section in sections if section.get('kind')=='status' for item in section.get('items',[]) if str(item.get('evidence','')).lower().startswith(('http://','https://'))]
        detail={'id':p['id'],'name':p['name'],'division':p['division'],'brand':p.get('brand',''),'category':p.get('category',''),'sections':sections,'documentLinks':links}
        blob=json.dumps(detail,sort_keys=True,separators=(',',':'))
        if len(blob)>1_000_000:raise ValueError('A product snapshot exceeds 1 MB. Narrow its saved text.')
        detail_version=hashlib.sha256(blob.encode()).hexdigest();snapshots.append((p['id'],detail_version,time.time(),blob))
        rows.append({'id':p['id'],'name':p['name'],'division':p['division'],'codes':codes,'url':url,'snapshotVersion':detail_version,'skuMetadata':[{'code':str(r['code']).strip(),'pack':r.get('pack'),'uom':r.get('uom')} for section in sections if section.get('kind')=='variants' for r in [*section.get('rows',[]),*(section.get('sfgRows',[]) if section.get('hasSfg') else [])] if r.get('code')]})
    rows.sort(key=lambda p:p['id']);payload=json.dumps(rows,sort_keys=True,separators=(',',':'));version=hashlib.sha256(payload.encode()).hexdigest()
    schema(store)
    with store.transaction() as db:
        store.require(db,actor,admin=True)
        revision=store.run(db,"SELECT version FROM stock_product_catalog WHERE id='current'").fetchone()
        if revision and revision['version']==version:return {'ok':True,'version':version,'products':len(rows)}
        existing={r['product_id']:r['version'] for r in store.run(db,'SELECT product_id,version FROM stock_product_snapshots').fetchall()}
        for item in snapshots:
            if existing.get(item[0])==item[1]:continue
            store.run(db,'INSERT INTO stock_product_snapshots VALUES(?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET version=excluded.version,updated_at=excluded.updated_at,payload=excluded.payload',item)
        valid={p['id'] for p in rows}
        for old in existing:
            if old not in valid:store.run(db,'DELETE FROM stock_product_snapshots WHERE product_id=?',(old,))
        previous=store.run(db,"SELECT version,payload FROM stock_product_catalog WHERE id='current'").fetchone()
        old_fields=sku_metadata({'products':json.loads(previous['payload'])}) if previous else {}
        new_fields=sku_metadata({'products':rows})
        for code in sorted(set(old_fields)|set(new_fields)):
            before=old_fields.get(code,{})
            after=new_fields.get(code,{})
            if before!=after:
                # Both portals share this history schema, but the sync worker's
                # minimal Planning client intentionally has no UI mixin.
                store.run(db,'CREATE TABLE IF NOT EXISTS portal_history (id TEXT PRIMARY KEY,occurred_at DOUBLE PRECISION NOT NULL,username TEXT NOT NULL,section TEXT NOT NULL,before_value TEXT NOT NULL,after_value TEXT NOT NULL)')
                store.run(db,'INSERT INTO portal_history VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,time.time(),actor.username,'Product Status SKU pack / unit · '+code,json.dumps(before),json.dumps(after)))
        if not previous or previous['version']!=version:store.run(db,"INSERT INTO stock_product_catalog VALUES('current',?,?,?) ON CONFLICT(id) DO UPDATE SET version=excluded.version,updated_at=excluded.updated_at,payload=excluded.payload",(version,time.time(),payload))
    return {'ok':True,'version':version,'products':len(rows)}

def metadata(store,actor):
    schema(store)
    with store.transaction() as db:
        store.require(db,actor)
        row=store.run(db,"SELECT version FROM stock_product_catalog WHERE id='current'").fetchone()
    return row['version'] if row else 'empty'

def read(store,actor,version=None):
    identity=store.identity(actor);version=version or metadata(store,actor)
    if version=='empty':return {'version':version,'products':[]}
    cached=getattr(store,'_product_catalog_cache',None)
    if not cached or cached[0]!=version:
        with store.transaction() as db:
            store.require(db,actor)
            row=store.run(db,"SELECT payload FROM stock_product_catalog WHERE id='current' AND version=?",(version,)).fetchone()
        if not row:raise ValueError('Product names changed during loading. Refresh the workspace.')
        cached=store._product_catalog_cache=(version,json.loads(row['payload']))
    scope=identity.get('allowedSegments')
    def segment(value):
        key=''.join(c for c in str(value).casefold() if c.isalnum())
        return {'ostomy':'ostomycare','advancedwoundcare':'advancewoundcare','endovascularsolutions':'endovascularsolution'}.get(key,key)
    products=[p for p in cached[1] if scope is None or segment(p['division']) in {segment(s) for s in scope}]
    details=identity['role']=='admin' or identity.get('permissions',{}).get('view_product_details',False)
    access_version=hashlib.sha256(json.dumps([identity.get('role'),identity.get('permissions',{}),scope],sort_keys=True).encode()).hexdigest()
    return {'version':hashlib.sha256(json.dumps([version,access_version],sort_keys=True).encode()).hexdigest(),'products':products,'detailsAllowed':details,'accessVersion':access_version}


def read_detail(store,actor,event):
    from .store import AccessDenied
    identity=store.identity(actor)
    if identity['role']!='admin' and not identity.get('permissions',{}).get('view_product_details',False):raise AccessDenied('Your administrator has not granted Product Status details access.')
    catalogue=read(store,actor)
    product=next((p for p in catalogue['products'] if p['id']==event.get('productId')),None)
    if not product:raise AccessDenied('This product is unavailable for your assigned segments.')
    version=product.get('snapshotVersion')
    if not version:raise ValueError('Sync product details from Product Status once to populate this saved product.')
    if event.get('knownVersion')==version and event.get('accessVersion')==catalogue['accessVersion']:return {'notModified':True,'id':product['id'],'version':version,'accessVersion':catalogue['accessVersion']}
    key=(product['id'],version)
    with _DETAIL_LOCK:
        cache=getattr(store,'_product_detail_cache',None)
        if cache is None:cache=store._product_detail_cache=OrderedDict()
        cached=cache.get(key)
        if cached:result=copy.deepcopy(cached[0]);cache.move_to_end(key)
    if not cached:
        with store.transaction() as db:
            store.require(db,actor)
            row=store.run(db,'SELECT payload,updated_at FROM stock_product_snapshots WHERE product_id=? AND version=?',key).fetchone()
        if not row:raise ValueError('The product snapshot changed. Refresh Planning before opening it again.')
        result={'product':json.loads(row['payload']),'version':version,'syncedAt':row['updated_at']}
        with _DETAIL_LOCK:
            cache[key]=(copy.deepcopy(result),len(row['payload']))
            while len(cache)>20 or sum(v[1] for v in cache.values())>8_000_000:cache.popitem(last=False)
    # Section notes attached to operational tabs obey their corresponding menu grant.
    from .access import allowed
    menus={'summary':0,'bom':1,'production':3,'sales':2,'salesRecords':11,'pricing':1,'assistant':7,'insights':8}
    result['product']['sections']=[s for s in result['product']['sections'] if s.get('tab') not in menus or allowed(identity,menus[s['tab']])]
    result['accessVersion']=catalogue['accessVersion']
    return result



def sku_metadata(catalogue):
    """Compact synced SKU fields; product dimensions are never pack quantities."""
    values={}
    for product in catalogue.get('products',[]):
        for row in product.get('skuMetadata',[]):
            code=material_key(row.get('code'))
            if not code:continue
            for source,target in [('pack','packSize'),('uom','unit')]:
                raw=row.get(source)
                if raw is None or isinstance(raw,bool) or not str(raw).strip():continue
                value=str(raw).strip()
                if source=='pack':
                    try:
                        import math
                        number=float(value.replace(',',''))
                        if not math.isfinite(number) or number<=0:continue
                        value=int(number) if number.is_integer() else number
                    except ValueError:pass
                else:value=value.upper()
                values.setdefault(code,{}).setdefault(target,set()).add(value)
    return {code:{field:next(iter(items)) if len(items)==1 else None for field,items in fields.items()} for code,fields in values.items()}

def enrich_display(payload,pending,catalogue):
    """Overlay latest synced fields on cached displays without changing source rows."""
    metadata=sku_metadata(catalogue)
    if not metadata:return payload,pending
    from .bom_prices import norm
    sheets=[]
    for sheet in payload.get('sheets',[]):
        if norm(sheet.get('name',''))!='bomcost':sheets.append(sheet);continue
        headers=sheet['headers'];names=[norm(h) for h in headers]
        ci=next((i for i,h in enumerate(names) if h in ('material','materialcode','materialnumber','fgcode','sku','skucode')),0)
        fields=[(i,'packSize' if h=='packsize' else 'unit') for i,h in enumerate(names) if h in ('packsize','baseunitofmeasure','unitofmeasure','uom','baseunit')]
        rows=[]
        for row in sheet['rows']:
            found=metadata.get(material_key(row[ci]),{}) if len(row)>ci else {}
            result=list(row)
            for index,field in fields:
                if field in found and index<len(result):result[index]=found[field]
            rows.append(result)
        sheets.append({**sheet,'rows':rows})
    if pending and pending.get('result'):
        original=pending['result'];details={k:dict(v) for k,v in original.get('productDetails',{}).items()}
        for code in set(original.get('visibleStock',[]))|set(details):
            if code in metadata:details[code]={**details.get(code,{}),**metadata[code]}
        pending={**pending,'result':{**original,'productDetails':details}}
    return {**payload,'sheets':sheets},pending
