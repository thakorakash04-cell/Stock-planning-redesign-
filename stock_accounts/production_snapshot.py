"""Immutable production source rows, shared across logins per master revision."""
from collections import OrderedDict
from copy import deepcopy
from threading import RLock
import json

REVISION=1
_cache=OrderedDict()
_lock=RLock()
_durable=set()

def key(current):
    from .production import REVISION
    return (current['version'],current['updated_at'],REVISION,current.get('_scope','all'))

def remember(current,value):
    cache_key=key(current)
    _cache[cache_key]=deepcopy(value);_cache.move_to_end(cache_key)
    while len(_cache)>4:
        evicted,_=_cache.popitem(last=False)
        _durable.difference_update({entry for entry in _durable if entry[1]==evicted})
    return deepcopy(value)

def calculate(current):
    from .production import build,ident,QC_HEADERS,ONGOING_HEADERS,PLAN_HEADERS
    from .production_materials import catalogue,records
    from workbook import segment_map
    try:value=build(current)
    except ValueError as exc:value={'version':current['version'],'error':str(exc),'ongoing':[],'qc':{'headers':QC_HEADERS,'rows':[]},'ongoingHeaders':ONGOING_HEADERS,'upcomingHeaders':PLAN_HEADERS}
    data=current['data'];mapping=segment_map(data.get('tables',[]))
    value['segmentMap']={k:sorted(v) for k,v in mapping.items()}
    value['segments']=sorted({s for v in mapping.values() for s in v}|{s for item in value['ongoing'] for s in item.get('segments',[])}|{s for values in value['qc'].get('segments',[]) for s in values})
    value['materials']=catalogue(data)
    descriptions={}
    for table in data.get('tables',[]):
        headers=table['headers']
        code=next((h for h in ('Material','Material Number','Material Code') if h in headers),None)
        desc=next((h for h in ('Material(text)','Material description','Material Description','Material Name') if h in headers),None)
        if code and desc:
            for row in table['rows']:
                descriptions.setdefault(str(row[headers.index(desc)] or '').strip().casefold(),set()).update(mapping.get(ident(row[headers.index(code)]),set()))
    value['_productSegments']={k:sorted(v) for k,v in descriptions.items()}
    value['_productionPairs']=[list(pair) for pair in {(ident(row.get('Material Number')).casefold(),ident(row.get('Batch')).casefold()) for row in records(data,'Production Order Details') if ident(row.get('Material Number')) and ident(row.get('Batch'))}]
    return value

def cached_build(current):
    """Used by planning calculations too; never share mutable override rows."""
    from .production import build
    with _lock:
        cache_key=key(current)
        if cache_key in _cache:
            return deepcopy(_cache[cache_key])
        return remember(current,calculate(current))

def read(store,actor,current):
    """Persist once so process restarts do not recalculate an unchanged master."""
    from .production import REVISION,build,QC_HEADERS,ONGOING_HEADERS,PLAN_HEADERS
    with _lock:
        cache_key=key(current)
        if cache_key in _cache and (store.url,cache_key) in _durable:return deepcopy(_cache[cache_key])
        with store.transaction() as db:
            store.require(db,actor)
            if not store.sqlite:store.run(db,'SELECT pg_advisory_xact_lock(hashtext(?))',('production-source-snapshot',))
            store.run(db,'CREATE TABLE IF NOT EXISTS production_source_snapshot (id TEXT PRIMARY KEY,version TEXT NOT NULL,uploaded_at DOUBLE PRECISION NOT NULL,revision INTEGER NOT NULL,payload TEXT NOT NULL)')
            latest=store.run(db,"SELECT version,updated_at FROM datasets WHERE id='current'").fetchone()
            if not latest or (latest['version'],latest['updated_at'])!=(current['version'],current['updated_at']):raise ValueError('The workbook changed. Refresh Production.')
            snapshot_id='current:'+current.get('_scope','all')
            row=store.run(db,'SELECT * FROM production_source_snapshot WHERE id=?',(snapshot_id,)).fetchone()
            if row and (row['version'],row['uploaded_at'],row['revision'])==cache_key[:3]:
                value=json.loads(row['payload'])
            else:
                try:value=cached_build(current)
                except ValueError as exc:value={'version':current['version'],'error':str(exc),'ongoing':[],'qc':{'headers':QC_HEADERS,'rows':[]},'ongoingHeaders':ONGOING_HEADERS,'upcomingHeaders':PLAN_HEADERS}
                store.run(db,"INSERT INTO production_source_snapshot VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET version=excluded.version,uploaded_at=excluded.uploaded_at,revision=excluded.revision,payload=excluded.payload",(snapshot_id,*cache_key[:3],json.dumps(value,allow_nan=False)))
        _durable.add((store.url,cache_key))
        return remember(current,value)

