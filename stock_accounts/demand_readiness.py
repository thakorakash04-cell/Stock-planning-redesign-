"""Workbook-snapshot BOM readiness for cached new-production requirements."""
from collections import defaultdict
from .production_materials import availability,records,dec
from .sales import material_key

HEADERS=['Component','Description','Unit','Required Quantity','Current Stock (including QC)','Under QC Stock (included)','To be Delivered Quantity','Material Need to Be Ordered','Status']
READY='Ready'
SHORT='Material Shortage'
ORDER='Material Need to Be Ordered'
UNKNOWN='Cannot verify'

def build(data,requirements):
 """Index once; reuse physical BOM arithmetic on only each FG's relevant records."""
 boms=defaultdict(list);stocks=defaultdict(list);deliveries=defaultdict(list)
 for row in records(data,'BOM'):boms[material_key(row.get('Material'))].append(row)
 for row in records(data,'Stock Data'):stocks[material_key(row.get('Material'))].append(row)
 order_table=next((t for t in data.get('tables',[]) if t['name']=='Order List'),{})
 order_header=next((h for h in order_table.get('headers',[]) if h in ('Still to be delivered (qty)','Still To be Deliver Quantity')),None)
 if order_header and 'Material' not in order_table.get('headers',[]):order_header=None
 if order_header:
  for row in records(data,'Order List'):deliveries[material_key(row.get('Material'))].append(row)
 def table(name,rows):
  headers=list(dict.fromkeys(h for row in rows for h in row))
  return {'name':name,'headers':headers,'rows':[[row.get(h) for h in headers] for row in rows]}
 result={}
 for requirement in requirements:
  code,_,quantity,unit=requirement[:4];key=material_key(code)
  if unit in result.get(key,{}):continue
  lines=boms[key];component_codes={material_key(row.get('Component')) for row in lines}
  # Canonicalize matching codes to BOM spellings without weakening leading-zero identity.
  spellings={material_key(row.get('Component')):str(row.get('Component') or '') for row in lines}
  stock_rows=[{**r,'Material':spellings[c]} for c in component_codes for r in stocks[c]]
  mini={'tables':[table('BOM',[{**r,'Material':str(code)} for r in lines]),table('Stock Data',stock_rows)]}
  try:
   fg_units={str(r.get('Base unit of measure')).strip().upper() for r in lines if r.get('Base unit of measure')}
   if fg_units and fg_units!={str(unit).strip().upper()}:raise ValueError('Requirement unit does not match the BOM base unit.')
   physical=availability(mini,str(code),quantity)
   rows=[]
   for component,name,component_unit,required,current,_,status in physical['rows']:
    ck=material_key(component);qc_values=[dec(r.get('In Quality Insp.')) for r in stocks[ck]]
    qc=float(sum(qc_values)) if qc_values and all(v is not None for v in qc_values) else None
    on_order=None
    if order_header:
     values=[];seen={};valid=True
     for r in deliveries[ck]:
      value=dec(r.get(order_header));po=r.get('Purchasing Document');item=r.get('Item',r.get('Purchasing Document Item'))
      if value is None:valid=False;break
      if po is not None and item is not None:
       pair=(material_key(po),material_key(item))
       if pair in seen:
        if seen[pair]!=value:valid=False
        continue
       seen[pair]=value
      values.append(value)
     if valid:on_order=float(sum(values))
    else:
     values=[dec(r.get('Sum of Order List.Still to be delivered (qty)')) for r in lines if material_key(r.get('Component'))==ck]
     if values and all(v is not None for v in values):on_order=float(min(values))
    valid=status!='Cannot verify' and required is not None and current is not None
    gap=max(dec(required)-dec(current),0) if valid else None
    need=max(gap-max(dec(on_order),0),0) if gap is not None and on_order is not None else 0 if gap==0 else None
    label=READY if gap==0 else ORDER if need is not None and need>0 else SHORT if need==0 else UNKNOWN
    rows.append([component,name,component_unit,required,current,qc,on_order,float(need) if need is not None else None,label])
   labels={r[-1] for r in rows}
   status=UNKNOWN if UNKNOWN in labels or not rows else ORDER if ORDER in labels else SHORT if SHORT in labels else READY
   details={'status':status,'headers':HEADERS,'rows':rows,'warnings':physical['warnings'],'quantity':quantity,'unit':unit}
  except ValueError as exc:details={'status':UNKNOWN,'headers':HEADERS,'rows':[],'warnings':[str(exc)],'quantity':quantity,'unit':unit}
  result.setdefault(key,{})[unit]=details
 return result
