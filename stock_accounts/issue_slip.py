"""Metadata-only validation of the existing upcoming-plan issue table."""
import hashlib,json
REVISION=3

def metadata(store,actor):
    from .production import schema,REVISION as production_revision
    from .batch_availability import REVISION as availability_revision
    with store.transaction() as db:
        identity=store.require(db,actor);schema(store,db)
        current=store.run(db,"SELECT version,updated_at FROM datasets WHERE id='current'").fetchone()
        if not current:raise ValueError('Upload a workbook first.')
        plans=store.run(db,"SELECT id,revision,updated_at FROM production_shared WHERE kind='upcoming' ORDER BY id").fetchall()
    access={k:identity.get(k) for k in ('username','role','permissions','allowedSegments')}
    return hashlib.sha256(json.dumps([REVISION,production_revision,availability_revision,access,[current['version'],current['updated_at']],[[row['id'],row['revision'],row['updated_at']] for row in plans]],sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()

def read(store,actor,event):
    from .access import require_menu
    from .production import read as production
    from .batch_availability import check
    require_menu(store,actor,12)
    key=metadata(store,actor)
    if event.get('known_stamp')==key:return {'stamp':key,'not_modified':True}
    report=production(store,actor)
    if report.get('error'):raise ValueError(report['error'])
    # Production read may archive plans that now have an SAP production order.
    key=metadata(store,actor)
    value=None
    if report['upcoming']:
        saved=report.get('batchAvailability')
        value=saved if saved and saved.get('version')==report['version'] and saved.get('sourceStamp')==report.get('sourceStamp') and isinstance(saved.get('issueHeaders'),list) else check(store,actor,{'version':report['version']})
    if metadata(store,actor)!=key:raise ValueError('Upcoming plans or access changed while loading issue slips. Retry.')
    result={k:value.get(k) for k in ('issueHeaders','issueRows','checkedAt','version','sourceStamp','signature')} if value else None
    return {'stamp':key,'result':result,'not_modified':False}
