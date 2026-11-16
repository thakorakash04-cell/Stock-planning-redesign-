"""Bounded prepared display cache and acknowledgement on existing browser RPCs.

Call after live authorization and current workbook/override metadata checks.
Cached display data never authorizes requests or replaces source-version checks.
"""
import copy,hashlib,json,pickle,threading
from collections import OrderedDict
REVISION=10
PRODUCTION_CACHE_REVISION=2
_LOCK=threading.RLock()
MAX_BYTES=16*1024*1024

RETAINED_MAX_BYTES=128*1024*1024

def retained_get(store,key):
    # Caller has already checked the live account, source and edit metadata.
    with _LOCK:
        cache=getattr(store,'_retained_prepared_workspaces',None)
        if not isinstance(cache,OrderedDict):return None
        blob=cache.get(key)
        if blob is None:return None
        cache.move_to_end(key)
    return pickle.loads(blob)

def retained_put(store,key,value):
    blob=pickle.dumps(value,protocol=5)
    if len(blob)>RETAINED_MAX_BYTES:return False
    with _LOCK:
        cache=getattr(store,'_retained_prepared_workspaces',None)
        if not isinstance(cache,OrderedDict):cache=store._retained_prepared_workspaces=OrderedDict()
        cache[key]=blob;cache.move_to_end(key)
        while len(cache)>8 or sum(len(v) for v in cache.values())>RETAINED_MAX_BYTES:cache.popitem(last=False)
    return True

def prepared(store,current,identity,overrides,builder):
    if not current:return builder(current,identity,overrides)
    from .access import allowed
    key=json.dumps([REVISION,current['version'],current['updated_at'],current.get('_scope'),identity.get('role'),identity.get('allowedSegments'),[i for i in range(14) if allowed(identity,i)],[(r['id'],r['revision'],r['updated_at']) for r in overrides if r['kind']=='ongoing']],sort_keys=True,default=str)
    with _LOCK:
        cache=getattr(store,'_prepared_workspace_cache',None)
        if cache is None:cache=store._prepared_workspace_cache=OrderedDict()
        cached=cache.get(key)
        if cached:
            cache.move_to_end(key)
            return copy.deepcopy(cached[0][0]),current.get('data',{}).get('tables',[]),cached[0][1]
    result=builder(current,identity,overrides)
    # Embedded model tables already belong to the current scoped source. Do not
    # copy/serialize them into a second display cache during startup.
    display=(result[0],result[2])
    size=len(pickle.dumps(display,protocol=5))
    with _LOCK:
        if size<=MAX_BYTES:
            cache[key]=(copy.deepcopy(display),size)
            while len(cache)>4 or sum(v[1] for v in cache.values())>MAX_BYTES:cache.popitem(last=False)
    return result

def payload(state,event,data,tables,version,identity):
    key=[REVISION,identity['username'],identity['role'],identity['permissions'],state.get('_workspace_payload',('empty',))[0],version,data.get('accessibleTabs'),data.get('productCatalogue',{}).get('version'),data.get('portal'),(data.get('pendingSales') or {}).get('stamp')]
    bootstrap_id=hashlib.sha256(repr(key).encode()).hexdigest()
    if isinstance(event,dict):
        if event.get('action') in ('workspace_bootstrap','open_admin','open_password','open_settings','open_email','open_history','open_workbook','open_uploads'):state.pop('_workspace_bootstrap_seen',None)
        elif isinstance(event.get('knownBootstrapId'),str) and len(event['knownBootstrapId'])==64:state['_workspace_bootstrap_seen']=event['knownBootstrapId']
    present=state.get('_workspace_bootstrap_seen')!=bootstrap_id
    cache_scope=state.get('_workspace_payload',('empty',))[0]
    stable_scope=cache_scope[:1]+cache_scope[2:] if isinstance(cache_scope,tuple) and len(cache_scope)==9 else cache_scope
    content_id=hashlib.sha256(json.dumps([REVISION,access_scope(identity),stable_scope,version,data.get('accessibleTabs'),data.get('productCatalogue',{}).get('version'),data.get('portal'),(data.get('pendingSales') or {}).get('stamp')],sort_keys=True,default=str).encode()).hexdigest()
    # Fresh iframes first receive authenticated metadata, not the full display
    # rows. They either restore a matching browser snapshot or request bootstrap.
    force_data=isinstance(event,dict) and (event.get('action')=='workspace_bootstrap' or isinstance(event.get('knownBootstrapId'),str))
    return {'productionStamp':(data.get('production') or {}).get('displayStamp'),'bootstrapId':bootstrap_id,'contentId':content_id,'dataDeferred':present and not force_data,'data':data if present and force_data else None,
            'tables':[] if present and not tables else None,'tablesDeferred':bool(tables),
            'modelScope':model_scope(identity,version),'accessScope':access_scope(identity)}


def access_scope(identity):
    return hashlib.sha256(json.dumps([identity['username'],identity['role'],identity['permissions'],identity.get('allowedSegments')],sort_keys=True).encode()).hexdigest()

def model_scope(identity,version):
    return hashlib.sha256((access_scope(identity)+':'+version).encode()).hexdigest()

def model_tables(store,actor,event):
    """First source-record opening fetches the same permitted snapshot, once per version."""
    from .workspace import workspace_payload
    data,tables,version=workspace_payload(store,actor)
    identity=store.identity(actor);scope=model_scope(identity,version)
    if event.get('version')!=version or event.get('modelScope')!=scope:raise ValueError('The workbook or access changed. Reopen the source records using the current workspace.')
    with store.transaction() as db:
        store.require(db,actor)
        current=store.run(db,"SELECT version FROM datasets WHERE id='current'").fetchone()
        if (current['version'] if current else 'empty')!=version:raise ValueError('The workbook changed. Reopen the source records.')
    from .planning_assistant import require_source_table
    from .store import AccessDenied
    permitted=[]
    for index,table in enumerate(tables):
        try:require_source_table(store,actor,table,'MODEL_'+str(index))
        except AccessDenied:continue
        permitted.append(table)
    return {'tables':permitted,'version':version,'modelScope':scope}

