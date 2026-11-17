"""Authenticated first-render preload, acknowledged once; metadata-only change signals."""
import hashlib,json,uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from .access import allowed
REVISION=9

def versions(store,actor):
    identity=store.identity(actor);out={}
    if not allowed(identity,10) and not allowed(identity,11):return out
    with store.transaction() as db:
        store.require(db,actor)
        plan=store.run(db,"SELECT version FROM datasets WHERE id='current'").fetchone()
        planning=plan['version'] if plan else None
    if allowed(identity,10):
        from .pnl import schema,REVISION as PNL_REVISION
        from .product_catalog import metadata as product_version
        schema(store)
        with store.transaction() as db:
            store.require(db,actor)
            rows=store.run(db,'SELECT id,version,updated_at FROM stock_pnl_documents ORDER BY id').fetchall()
        from .sales import schema as sales_schema
        sales_schema(store)
        with store.transaction() as db:
            store.require(db,actor)
            sales_rows=store.run(db,'SELECT kind,version,updated_at FROM stock_sales_documents ORDER BY kind').fetchall()
        out['pnl']=hashlib.sha256(json.dumps([PNL_REVISION,planning,product_version(store,actor),[(r['id'],r['version'],r['updated_at']) for r in rows],[(r['kind'],r['version'],r['updated_at']) for r in sales_rows]]).encode()).hexdigest()
    if allowed(identity,11):
        from .sales import schema
        schema(store)
        with store.transaction() as db:
            store.require(db,actor)
            rows=store.run(db,'SELECT kind,version,updated_at FROM stock_sales_documents ORDER BY kind').fetchall()
        found={r['kind']:(r['version'],r['updated_at']) for r in rows}
        from .sales import REVISION as sales_revision
        out['primary']=str(sales_revision)+':'+str(found.get('primary'))+':'+str(planning)
        out['secondary']=str(sales_revision)+':'+str(found.get('secondary'))+':'+str(planning)
    return out

def bundle(store,actor,preferences,state,parts=None):
    identity=store.identity(actor)
    selected=['primary','secondary','pnl'] if parts is None else parts
    if not isinstance(selected,list) or not selected or len(selected)>3 or any(p not in ('primary','secondary','pnl') for p in selected) or len(set(selected))!=len(selected):raise ValueError('Choose valid saved-data sections.')
    if parts is not None and any(not allowed(identity,10 if p=='pnl' else 11) for p in selected):
        from .store import AccessDenied
        raise AccessDenied('Saved-data section access denied.')
    key=json.dumps([REVISION,actor.username,actor.session_id,identity['role'],identity['permissions'],identity.get('allowedSegments'),selected,preferences.get('pnl:filters') if 'pnl' in selected else None],sort_keys=True)
    previous=state.get('_workspace_preload')
    if previous and previous['key']==key:
        return None if state.get('_workspace_preload_ack')==previous['body']['id'] else previous['body']
    result={'id':uuid.uuid4().hex,'sales':{},'pnl':None,'errors':[]}
    if allowed(identity,11):
        from .sales import read
        for kind in (p for p in ('primary','secondary') if p in selected):
            try:result['sales'][kind]=read(store,actor,{'kind':kind})
            except Exception:result['errors'].append(kind.title()+' Sales could not be loaded.')
    if allowed(identity,10) and 'pnl' in selected:
        from .pnl import catalogue,report
        now=datetime.now(ZoneInfo('Asia/Kolkata'));fy=now.year if now.month>=4 else now.year-1
        saved=preferences.get('pnl:filters',{})
        params={'fy':saved.get('fy',fy),'basis':saved.get('basis','revenue'),'segments':saved.get('segments',[]),'products':saved.get('products',[]),'materialType':saved.get('materialType','all')}
        try:
            cat=catalogue(store,actor)
            result['pnl']={'params':params,'catalogue':cat,'report':report(store,actor,params) if any(d['kind']=='master' and d['fy']==params['fy'] for d in cat['documents']) else None}
        except Exception:result['errors'].append('PnL could not be loaded.')
    result['versions']=versions(store,actor)
    state['_workspace_preload']={'key':key,'body':result}
    return result

def acknowledge(store,actor,event,state):
    store.identity(actor)
    cached=state.get('_workspace_preload')
    if cached and cached['body']['id']==event.get('preloadId'):
        state['_workspace_preload_ack']=event['preloadId']
        # Release large per-session copies after browser acknowledgement.
        state['_workspace_preload']={'key':cached['key'],'body':{'id':event['preloadId']}}
    return {'ok':True}


def load_after_paint(store,actor,state,event=None):
    """Warm finance after the workbook is visible; a fresh iframe can recover its copy."""
    from .preferences import read
    from .workspace_delivery import access_scope
    store.identity(actor)
    previous=state.get('_workspace_preload')
    if previous and (set(previous['body'])=={'id'} or previous['body'].get('errors')):
        state.pop('_workspace_preload',None);state.pop('_workspace_preload_ack',None)
    before=versions(store,actor)
    value=bundle(store,actor,read(store,actor),state,(event or {}).get('parts'))
    if before!=versions(store,actor):
        state.pop('_workspace_preload',None);state.pop('_workspace_preload_ack',None)
        raise ValueError('Business sources changed while preparing the saved views. Open Sales or PnL to load the current data.')
    with store.transaction() as db:
        store.require(db,actor)
        current=store.run(db,"SELECT version FROM datasets WHERE id='current'").fetchone()
    return {'preload':value,'accessScope':access_scope(store.identity(actor)),'version':current['version'] if current else 'empty'}
