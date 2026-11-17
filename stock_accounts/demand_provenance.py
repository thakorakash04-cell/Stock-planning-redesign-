"""Immutable suggestion and file-upload snapshot for demand-origin production plans."""
from .sales import material_key

def capture(store,actor,current,value):
 from .pending_sales import read
 from .source_freshness import workbook_summary
 material=value.get('demandMaterial');unit=value.get('demandUnit')
 if not isinstance(material,str) or not material.strip() or len(material)>200 or not isinstance(unit,str) or len(unit)>100:
  raise ValueError('Choose a valid production requirement and unit.')
 demand=read(store,actor)
 if demand['stamp']!=value.get('demandStamp'):raise ValueError('Demand data changed. Refresh the requirement before adding a plan.')
 row=next((r for r in demand['result']['rows'] if material_key(r[0])==material_key(material) and r[3]==unit),None)
 if row is None:raise ValueError('This production requirement is no longer available in your permitted data.')
 sources=[{'label':'Master workbook (FG stock, forecast and BOM)','filename':current['filename'],'version':current['version'],'updated_at':current['updated_at'],**workbook_summary(current['data'])}]
 if any(name in row[4] for name in ('Credit Hold No Stock','Credit Release No Stock')) and demand.get('source'):
  sources.append({'label':'Open sales orders',**demand['source']})
 return {'origin':'New Production Batch Required','suggestion':row[4],'materialCode':row[0],'requiredQuantity':row[2],'unit':row[3],'demandStamp':demand['stamp'],'sources':sources}

def validate_sources(store,db,provenance):
 for source in provenance['sources']:
  if source['label'].startswith('Master workbook'):
   current=store.run(db,"SELECT version,updated_at FROM datasets WHERE id='current'").fetchone()
  else:current=store.run(db,"SELECT version,updated_at FROM stock_open_orders WHERE id='current'").fetchone()
  if not current or (current['version'],current['updated_at'])!=(source['version'],source['updated_at']):
   raise ValueError('Demand source files changed. Refresh the requirement before saving.')
