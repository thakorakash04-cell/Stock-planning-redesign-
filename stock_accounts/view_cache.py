"""Conditional display responses; existing handlers own all calculations."""
import hashlib,json
REVISION=2
OPERATIONS={'production_status':3,'planning_status':6,'pnl_report':10}

def production_stamp(identity,master,plans,availability):
    """Fingerprint the same authorized source inputs used by startup delivery."""
    from .production import REVISION as calculation_revision
    access={k:identity.get(k) for k in ('username','role','permissions','allowedSegments')}
    return hashlib.sha256(json.dumps([REVISION,'production_status',calculation_revision,access,master,plans,availability],sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()

def metadata(store,actor,event):
    from .access import require_menu
    operation=event['action'];require_menu(store,actor,OPERATIONS[operation])
    with store.transaction() as db:
        identity=store.require(db,actor)
        row=store.run(db,"SELECT version,updated_at FROM datasets WHERE id='current'").fetchone()
        master=[row['version'],row['updated_at']] if row else None
        plans=[];availability=[]
    if operation=='production_status':
        from .production import shared
        from .availability_cache import revision
        rows=shared(store,actor)
        plans=str([(r['kind'],r['id'],r['revision'],r['updated_at']) for r in rows])
        return production_stamp(identity,master,plans,revision(store,actor,tuple(master) if master else None,identity))
    if operation=='planning_status':
        from .order_snapshot import REVISION as calculation_revision
    else:
        from .pnl import REVISION as calculation_revision
    finance=None
    if operation=='pnl_report':
        from .preload import versions
        finance=versions(store,actor).get('pnl')
    parameters={k:v for k,v in event.items() if k in ('fy','basis','segments','products','materialType')}
    access={k:identity.get(k) for k in ('username','role','permissions','allowedSegments')}
    return hashlib.sha256(json.dumps([REVISION,operation,calculation_revision,access,master,plans,availability,finance,parameters],sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()

def read(store,actor,event,loader):
    before=metadata(store,actor,event)
    if event.get('known_stamp')==before:return {'stamp':before,'not_modified':True}
    for attempt in range(2):
        data=loader()
        after=metadata(store,actor,event)
        if after==before:return {'stamp':after,'not_modified':False,'data':data}
        before=after
    raise ValueError('Data or access changed while loading the saved view. Refresh and retry.')
