"""Read only the prepared monthly Sales snapshots during an authorised planning pull."""
import base64,gzip,json,re,unicodedata,hashlib,threading
from collections import OrderedDict
_CACHE=OrderedDict()
_LOCK=threading.RLock()

def material_key(value):
    text=unicodedata.normalize('NFKC',str(value) if value is not None else '').replace('\u200b','').strip()
    whole,point,fraction=text.partition('.')
    if point and whole.lstrip('+-').isdigit() and fraction and not fraction.strip('0'):text=whole
    return text.casefold()

def norm(value):return re.sub(r'[^a-z0-9]','',str(value).casefold())

def snapshot_sales(store,actor,dataset,wanted):
    store.require_permission(actor,'download')
    wanted={material_key(x) for x in wanted}
    parents=set()
    keys={'material','materialcode','materialnumber','materialno','fgcode','fgmaterial','fgmaterialcode','fgmaterialnumber','sku','skucode'}
    for table in [*dataset.get('tables',[]),*dataset.get('sheets',[])]:
        if norm(table['name']) not in {'bom','bomcost','bomdata','billofmaterial','billofmaterials'}:continue
        key=next((i for i,h in enumerate(table['headers']) if norm(h) in keys),None)
        if key is not None:parents.update(material_key(r[key]) for r in table['rows'])
    with store.transaction() as db:
        store.require(db,actor,admin=True)
        exists=store.run(db,"SELECT name FROM sqlite_master WHERE type='table' AND name='stock_sales_documents'").fetchone() if store.sqlite else store.run(db,"SELECT to_regclass('stock_sales_documents') AS name").fetchone()
        if not exists or not exists['name']:return [],{}
        records=[dict(r) for r in store.run(db,'SELECT kind,filename,version,updated_at FROM stock_sales_documents ORDER BY kind').fetchall()]
    sheets=[];sources={}
    for record in records:
        kind=record['kind']
        if kind not in ('primary','secondary'):continue
        cache_key=(hashlib.sha256(store.url.encode()).hexdigest(),kind,record['version'])
        with _LOCK:cached=_CACHE.get(cache_key)
        if cached:data=cached[0]
        else:
            with store.transaction() as db:
                store.require(db,actor,admin=True)
                payload=store.run(db,'SELECT payload FROM stock_sales_documents WHERE kind=? AND version=?',(kind,record['version'])).fetchone()
            if not payload:raise ValueError('The Sales upload changed during the pull. Retry to capture its latest version.')
            raw=gzip.decompress(base64.b64decode(payload['payload']));data=json.loads(raw)
            if len(raw)<=32_000_000:
                with _LOCK:
                    _CACHE[cache_key]=(data,len(raw))
                    while len(_CACHE)>4 or sum(v[1] for v in _CACHE.values())>32_000_000:_CACHE.popitem(last=False)
        key=next((i for i,h in enumerate(data['headers']) if norm(h) in keys),None)
        if key is None:raise ValueError('The '+kind+' Sales upload needs a Material/SKU code column before it can be matched to products.')
        rows=[r for r in data['rows'] if material_key(r[key]) in wanted and (kind!='primary' or material_key(r[key]) in parents)]
        sheets.append({'name':'Primary Sales' if kind=='primary' else 'Secondary Sales','headers':data['headers'],'rows':rows,'skuColumn':key})
        sources[kind]={k:record[k] for k in ('filename','version','updated_at')}
    return sheets,sources
