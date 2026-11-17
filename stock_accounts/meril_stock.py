"""Stock Overview estimate from the two authorized uploaded sales snapshots."""
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
import math
from .sales import material_key,read
from .pnl_import import norm

REVISION=3
HEADERS=['Expected Meril India Stock','Last uploaded Secondary sales data']

def quantities(report):
 if not report.get('available'):return None
 hs=[norm(h) for h in report['headers']]
 ci=next((i for i,h in enumerate(hs) if h in {'material','materialcode','materialnumber','sku','skucode','fgcode','materialno'}),None)
 qi=next((i for i,h in enumerate(hs) if h in {'billedqty','billedquantity'}),None)
 if ci is None or qi is None:return None
 totals=defaultdict(float);invalid=set();si=report['segmentIndex']
 for row in report['rows']:
  if norm(row[si]) in {'energydevice','energydevices'}:continue
  code=material_key(row[ci]);value=row[qi]
  if not code:continue
  if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):invalid.add(code)
  else:totals[code]+=value
 for code in invalid:totals[code]=None
 return totals

def apply(table,primary,secondary,segment_map):
 p=quantities(primary);s=quantities(secondary)
 stamp=secondary.get('source',{}).get('updated_at')
 uploaded=datetime.fromtimestamp(stamp,ZoneInfo('Asia/Kolkata')).date().isoformat() if stamp is not None else None
 mapping={material_key(k):v for k,v in segment_map.items()}
 out=[]
 for row in table['rows']:
  code=material_key(row[0]);excluded=any(norm(tag) in {'energydevice','energydevices'} for tag in mapping.get(code,[]))
  a=p.get(code,0) if p is not None else None;b=s.get(code,0) if s is not None else None
  value=a-b if not excluded and a is not None and b is not None else None
  out.append(list(row)+[value,uploaded if not excluded else None])
 return {**table,'headers':table['headers']+HEADERS,'rows':out}

def enrich(store,actor,payload,identity):
 from .access import allowed
 if not payload.get('sheets') or not allowed(identity,0):return payload
 reports=({}, {})
 if allowed(identity,11):reports=tuple(read(store,actor,{'kind':kind}) for kind in ('primary','secondary'))
 sheet=apply(payload['sheets'][0],*reports,payload.get('segmentMap',{}))
 return {**payload,'salesSourceFiles':[{**report['source'],'label':label} for label,report in zip(('Primary Sales','Secondary Sales'),reports) if report.get('source')],'sheets':[sheet,*payload['sheets'][1:]]}


def matching(report,material):
 """Select exact FG rows with the same Energy Device exclusion as the estimate."""
 if not report.get('available'):return []
 hs=[norm(h) for h in report['headers']]
 ci=next((i for i,h in enumerate(hs) if h in {'material','materialcode','materialnumber','sku','skucode','fgcode','materialno'}),None)
 if ci is None:return []
 return [row for row in report['rows'] if material_key(row[ci])==material_key(material) and norm(row[report['segmentIndex']]) not in {'energydevice','energydevices'}]


def records(store,actor,event):
 from .access import require_menu
 from .sales import bom_source_index
 require_menu(store,actor,0)
 material=event.get('material')
 if not isinstance(material,str) or not material.strip() or len(material)>200:raise ValueError('Choose a valid FG Code.')
 reports={kind:read(store,actor,{'kind':kind}) for kind in ('primary','secondary')}
 _,mapping,_=bom_source_index(store,actor)
 if any(norm(s) in {'energydevice','energydevices'} for s in mapping.get(material_key(material),[])):
  raise ValueError('Expected Meril India Stock excludes Energy Device.')
 pages=event.get('pages',{})
 if not isinstance(pages,dict):raise ValueError('Invalid record page.')
 tables={}
 for kind,report in reports.items():
  page=pages.get(kind,0)
  if type(page) is not int or not 0<=page<=500:raise ValueError('Invalid record page.')
  rows=matching(report,material);totals=quantities(report)
  tables[kind]={'headers':report.get('headers',[]),'rows':rows[page*200:(page+1)*200],'total':len(rows),'page':page,'billedQuantity':totals.get(material_key(material),0) if totals is not None else None,'source':report.get('source'),'available':report.get('available',False)}
 a=tables['primary']['billedQuantity'];b=tables['secondary']['billedQuantity']
 require_menu(store,actor,0)
 return {'material':material,'primary':tables['primary'],'secondary':tables['secondary'],'expectedStock':a-b if a is not None and b is not None else None}
