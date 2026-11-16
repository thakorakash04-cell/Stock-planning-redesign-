"""Bounded process-local payload cache; PostgreSQL checks content before every reuse.

Call only after authorization. Never use for accounts, credentials or rights.
The SQL is application-owned SELECT text, never browser/model-provided SQL.
No stale fallback is returned on a database error.
"""
import copy,hashlib,json,threading
from collections import OrderedDict
REVISION=1
_MAX_BYTES=32*1024*1024
_MAX_ENTRIES=16
_LOCK=threading.RLock()
def read_rows(store,db,sql,args=()):
    args=tuple(args)
    key=(sql,json.dumps(args,default=str))
    rows=None
    if store.sqlite:
        # SQLite is local and has no network egress or row_to_json function.
        rows=[dict(r) for r in store.run(db,sql,args).fetchall()]
        signature=hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()
    else:
        check="SELECT md5(COALESCE(string_agg(row_to_json(source)::text, ''), '')) AS signature FROM ("+sql+") AS source"
        signature=store.run(db,check,args).fetchone()['signature']
    with _LOCK:
        cache=getattr(store,'_transfer_rows_cache',None)
        if cache is None:cache=store._transfer_rows_cache=OrderedDict()
        cached=cache.get(key)
        if cached and cached[0]==signature:
            cache.move_to_end(key)
            return copy.deepcopy(cached[1])
    if rows is None:
        # Fetch rows and their digest in one statement so a concurrent edit
        # cannot tag a payload with another transaction's fingerprint.
        fetch="SELECT COALESCE(json_agg(source), '[]'::json) AS cached_rows, md5(COALESCE(string_agg(row_to_json(source)::text, ''), '')) AS signature FROM ("+sql+") AS source"
        result=store.run(db,fetch,args).fetchone()
        rows=result['cached_rows']
        if isinstance(rows,str):rows=json.loads(rows)
        signature=result['signature']
    size=len(json.dumps(rows,default=str).encode())
    with _LOCK:
        cache=store._transfer_rows_cache
        cache.pop(key,None)
        if size<=_MAX_BYTES:
            cache[key]=(signature,copy.deepcopy(rows),size)
            while len(cache)>_MAX_ENTRIES or sum(v[2] for v in cache.values())>_MAX_BYTES:cache.popitem(last=False)
    return rows
