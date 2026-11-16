"""Admin-only source metadata for the website's unified upload workspace."""
REVISION=2

def metadata(store,actor,include_versions=False):
 with store.transaction() as db:
  store.require(db,actor,admin=True)
  master=store.run(db,"SELECT filename,version,updated_at,uploaded_by AS updated_by FROM datasets WHERE id='current'").fetchone()
 from .pending_sales import info
 from .sales import metadata as sales_metadata
 from .pnl import metadata as pnl_metadata
 # Only source headers/timestamps leave the server, never source payloads.
 result={'master':dict(master) if master else None,'orders':info(store,actor),'sales':[{k:r[k] for k in ('kind','filename','version','updated_at','updated_by')} for r in sales_metadata(store,actor)],'pnl':[{k:r[k] for k in ('id','kind','fy','filename','version','updated_at','updated_by')} for r in pnl_metadata(store,actor)]}

 if include_versions:
  from .preload import versions
  result['sourceVersions']=versions(store,actor)
 return result
