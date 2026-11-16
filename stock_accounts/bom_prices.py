"""Enrich the saved BOM cost view from the same authorised workbook snapshot."""
import math
import re
from .sales import material_key
REVISION=2

def norm(value):
    return re.sub(r'[^a-z0-9]', '', str(value).casefold())

def price_index(dataset):
    """Shared SKU price sets; duplicate equal prices do not multiply a join."""
    key_names={'material','materialcode','materialnumber','fgcode','fgmaterial','skucode','sku'}
    prices={}
    tables=dataset.get('tables',[])
    preferred=[t for t in tables if norm(t['name']) in {'dpmrp','dpmrpdata'}]
    for table in preferred or tables:
        names=[norm(h) for h in table['headers']]
        key=next((i for i,h in enumerate(names) if h in key_names),None)
        if key is None:continue
        columns=[next((i for i,h in enumerate(names) if h in aliases),None) for aliases in ({'stddp','standarddp','stddpvalue','stddpprice','stddpinr','dpmrpstddp'},{'mrp','mrpvalue','mrpprice','mrpinr','dpmrpmrp'})]
        for row in table['rows']:
            code=material_key(row[key])
            if not code:continue
            values=prices.setdefault(code,[set(),set()])
            for slot,col in enumerate(columns):
                if col is None or col>=len(row):continue
                raw=row[col]
                try:value=float(str(raw).replace(',','').strip())
                except (ValueError,TypeError):continue
                if math.isfinite(value):values[slot].add(value)
    return prices

def pack_index(dataset):
    """Pack quantity from DP/MRP, distinct from the product's Size/dimensions."""
    result={}
    for table in dataset.get('tables',[]):
        if norm(table['name']) not in ('dpmrp','dpmrpdata'):continue
        names=[norm(h) for h in table['headers']]
        key=next((i for i,h in enumerate(names) if h in ('material','materialcode','materialnumber','fgcode','fgmaterial','fgmaterialcode','sku','skucode')),None)
        pack=next((names.index(h) for h in ('packsize','unitsperpack','packquantity','noofunits','numberofunits') if h in names),None)
        if key is None or pack is None:continue
        for row in table['rows']:
            if max(key,pack)>=len(row):continue
            code=material_key(row[key]);raw=row[pack]
            if not code or raw is None or isinstance(raw,bool) or not str(raw).strip():continue
            try:
                value=float(str(raw).replace(',','').strip())
                if not math.isfinite(value):continue
                value=int(value) if value.is_integer() else value
            except (ValueError,TypeError):value=str(raw).strip()
            result.setdefault(code,set()).add(value)
    return result

def with_prices(sheet, dataset):
    headers=list(sheet['headers'])
    if norm(sheet['name'])!='bomcost':return sheet
    key_names={'material','materialcode','materialnumber','fgcode','fgmaterial','skucode','sku'}
    material=next((i for i,h in enumerate(headers) if norm(h) in key_names),0 if headers else None)
    total=next((i for i,h in enumerate(headers) if norm(h)=='grandtotal'),len(headers)-1)
    prices=price_index(dataset);packs=pack_index(dataset)
    rows=[]
    for row in sheet['rows']:
        values=prices.get(material_key(row[material]),[set(),set()]) if material is not None else [set(),set()]
        # Conflicting source prices stay blank rather than selecting an arbitrary rate.
        extra=[next(iter(v)) if len(v)==1 else None for v in values]
        pack=packs.get(material_key(row[material]),set()) if material is not None else set()
        rows.append([*row[:total+1],next(iter(pack)) if len(pack)==1 else None,*extra,*row[total+1:]])
    return {**sheet,'headers':[*headers[:total+1],'Pack Size','Std DP','MRP',*headers[total+1:]],'rows':rows}
