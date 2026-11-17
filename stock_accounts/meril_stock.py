"""Stock Overview estimate from the two authorized uploaded sales snapshots."""
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
import math
from .sales import material_key,read
from .pnl_import import norm

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
 return {**payload,'sheets':[sheet,*payload['sheets'][1:]]}
