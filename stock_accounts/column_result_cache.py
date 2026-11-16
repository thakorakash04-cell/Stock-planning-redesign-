"""Private durable added-column results, reused only for an identical source scope."""
import base64,gzip,hashlib,json,time,math
REVISION=1
MAX_RAW=32*1024*1024
MAX_ENTRY=4*1024*1024
MAX_USER=16*1024*1024

def fingerprint(base,definitions,revision,role):
    return hashlib.sha256(json.dumps([REVISION,revision,role,base['headers'],base['rows'],definitions],ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()

def schema(store,db):
    store.run(db,'''CREATE TABLE IF NOT EXISTS user_column_results (
        username TEXT NOT NULL,scope TEXT NOT NULL,fingerprint TEXT NOT NULL,
        payload TEXT NOT NULL,updated_at DOUBLE PRECISION NOT NULL,
        PRIMARY KEY(username,scope))''')

def read(store,actor,scope,key,definitions,row_count):
    with store.transaction() as db:
        store.require(db,actor);schema(store,db)
        row=store.run(db,'SELECT payload FROM user_column_results WHERE username=? AND scope=? AND fingerprint=?',(actor.username,scope,key)).fetchone()
    if not row:return None
    try:
        import io
        with gzip.GzipFile(fileobj=io.BytesIO(base64.b64decode(row['payload']))) as stream:raw=stream.read(MAX_RAW+1)
        if len(raw)>MAX_RAW:return None
        value=json.loads(raw)
        if not isinstance(value,dict) or not isinstance(value.get('columns'),list) or not isinstance(value.get('warnings'),list) or any(not isinstance(w,str) for w in value['warnings']):return None
        if any(not isinstance(c,dict) or not isinstance(c.get('values'),list) or any(v is not None and (type(v) not in (str,int,float) or isinstance(v,float) and not math.isfinite(v)) for v in c['values']) for c in value['columns']):return None
        if [c['name'] for c in value['columns']]!=[d['name'] for d in definitions] or any(len(c['values'])!=row_count for c in value['columns']):return None
        return value
    except (ValueError,TypeError,KeyError,OSError,EOFError):return None

def write(store,actor,scope,key,result):
    raw=json.dumps({'columns':result['columns'],'warnings':result.get('warnings',[])},ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
    if len(raw)>MAX_RAW:return False
    compressed=gzip.compress(raw)
    if len(compressed)>MAX_ENTRY:return False
    payload=base64.b64encode(compressed).decode()
    with store.transaction() as db:
        store.require(db,actor);schema(store,db)
        store.run(db,'INSERT INTO user_column_results(username,scope,fingerprint,payload,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(username,scope) DO UPDATE SET fingerprint=excluded.fingerprint,payload=excluded.payload,updated_at=excluded.updated_at',(actor.username,scope,key,payload,time.time()))
        rows=store.run(db,'SELECT scope,length(payload) AS size FROM user_column_results WHERE username=? ORDER BY updated_at DESC,scope',(actor.username,)).fetchall()
        total=0
        for index,row in enumerate(rows):
            total+=row['size']
            if index>=32 or total>MAX_USER:store.run(db,'DELETE FROM user_column_results WHERE username=? AND scope=?',(actor.username,row['scope']))
    return True
