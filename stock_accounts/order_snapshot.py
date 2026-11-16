"""Master-version material catalogue and Order Requirements bootstrap."""
from collections import OrderedDict
from copy import deepcopy
from threading import RLock
import json

REVISION=2
_cache=OrderedDict()
_lock=RLock()

def build(current):
    from .planning import options
    from .production_materials import catalogue
    from workbook import segment_map
    data=current['data'];materials={m['code']:m for m in catalogue(data)}
    try:choices=options(data);error=''
    except ValueError as exc:choices=[];error=str(exc)
    mapping=segment_map(data.get('tables',[]));by_code={str(m['code']):m for m in choices}
    rows=[]
    for code in sorted(set(materials)|set(by_code)):
        item=materials.get(code,{})
        option=by_code.get(code,{})
        rows.append([code,option.get('description') or item.get('description',''),item.get('type') or 'Not specified',', '.join(sorted(mapping.get(code,set()))) or option.get('segment',''),option.get('unit') or item.get('unit',''),'Available' if code in by_code else 'Not in master BOM'])
    return {'version':current['version'],'options':choices,'error':error,'summary':{'headers':['Material','Description','Material Type','Segment','Unit','BOM planning'],'rows':rows}}

def read(store,actor,current):
    key=(store.url,current['version'],current['updated_at'],REVISION,current.get('_scope','all'))
    with _lock:
        if key in _cache:return deepcopy(_cache[key])
        with store.transaction() as db:
            store.require(db,actor)
            if not store.sqlite:store.run(db,'SELECT pg_advisory_xact_lock(hashtext(?))',('order-material-snapshot',))
            store.run(db,'CREATE TABLE IF NOT EXISTS order_material_snapshot (id TEXT PRIMARY KEY,version TEXT NOT NULL,uploaded_at DOUBLE PRECISION NOT NULL,revision INTEGER NOT NULL,payload TEXT NOT NULL)')
            latest=store.run(db,"SELECT version,updated_at FROM datasets WHERE id='current'").fetchone()
            if not latest or (latest['version'],latest['updated_at'])!=(current['version'],current['updated_at']):raise ValueError('The workbook changed. Reload Order requirements.')
            snapshot_id='current:'+current.get('_scope','all')
            row=store.run(db,'SELECT * FROM order_material_snapshot WHERE id=?',(snapshot_id,)).fetchone()
            if row and (row['version'],row['uploaded_at'],row['revision'])==key[1:4]:value=json.loads(row['payload'])
            else:
                value=build(current)
                store.run(db,"INSERT INTO order_material_snapshot VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET version=excluded.version,uploaded_at=excluded.uploaded_at,revision=excluded.revision,payload=excluded.payload",(snapshot_id,*key[1:4],json.dumps(value,allow_nan=False)))
        _cache[key]=deepcopy(value)
        while len(_cache)>4:_cache.popitem(last=False)
        return deepcopy(value)

