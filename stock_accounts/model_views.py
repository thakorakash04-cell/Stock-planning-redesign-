"""Full-source views independent of Excel's saved pivot slicers.

Only rebuild when the required source schema exists. Call on the already
permission-scoped dataset, inside the versioned prepared workspace cache.
"""
import math,re
from collections import defaultdict
from workbook import material_code,row_source,segment_map

REVISION=1
def norm(value):return re.sub(r'[^a-z0-9]','',str(value).casefold())
def num(value):
    try:value=float(value)
    except (TypeError,ValueError):return None
    return value if math.isfinite(value) else None
def records(data,name):
    table=next((t for t in data.get('tables',[]) if norm(t['name'])==norm(name)),None)
    return (table,[dict(zip(table['headers'],r)) for r in table['rows']]) if table else (None,[])

def bom_rows(data):
    """Component extended costs, using the workbook's explicit line-cost measure."""
    table,rows=records(data,'BOM Cost')
    if table is None:return None
    h={norm(v) for v in table['headers']}
    if not {'material','component'}.issubset(h) or not ({'totalbomcost','pricelistprice'}&h):return None
    groups={}
    for raw in rows:
        r={norm(k):v for k,v in raw.items()}
        code=material_code(r.get('material'))
        if not code:continue
        source=row_source(list(raw),list(raw.values()))
        key=(code.casefold(),source.casefold())
        g=groups.setdefault(key,{'code':code,'description':r.get('materialtext'),'unit':r.get('baseunitofmeasure'),'source':source,'types':defaultdict(float),'missing':set()})
        typ=str(r.get('materialtype') or 'Other')
        value=num(r.get('totalbomcost'))
        if value is None:
            price=num(r.get('pricelistprice'));quantity=num(r.get('componentquantity'))
            if price is not None and quantity is not None:value=price*quantity
        if value is None:g['missing'].add(typ)
        else:g['types'][typ]+=value
    return list(groups.values())

def bom_sheet(data,saved):
    groups=bom_rows(data)
    if groups is None:return saved
    headers=['Material','Material(text)','Base unit of measure','ZCON','ZPKG','ZRAW','ZSFG','Grand Total','Source.Name']
    rows=[]
    for g in groups:
        categories=[None if t in g['missing'] or t not in g['types'] else g['types'][t] for t in headers[3:7]]
        total=None if g['missing'] else sum(g['types'].values())
        rows.append([g['code'],g['description'],g['unit'],*categories,total,g['source'] or None])
    return {**saved,'headers':headers,'rows':sorted(rows,key=lambda r:str(r[0])),'basis':'Embedded BOM Cost component records; independent of saved pivot slicers'}

def completed_sheet(data,saved):
    table,moves=records(data,'Material Document List')
    if table is None:return saved
    h={norm(v) for v in table['headers']}
    if not {'material','batch','movementtype','postingdate'}.issubset(h) or not ({'quantity','qtyinunofentry'}&h):return saved
    from .production import day,ident
    mapping=segment_map(data.get('tables',[]))
    _,order_rows=records(data,'Production Order Details')
    orders=defaultdict(dict)
    for r in order_rows:
        k=(material_code(r.get('Material Number')).casefold(),ident(r.get('Batch')).casefold())
        orders[k][ident(r.get('Order')) or str(r)]=r
    unique,fg_rows=records(data,'Unique Material')
    finished={material_code(r.get('Material')).casefold() for r in fg_rows}
    groups={}
    for raw in moves:
        r={norm(k):v for k,v in raw.items()}
        code=material_code(r.get('material'));batch=ident(r.get('batch'));date=day(r.get('postingdate'))
        if not code or not batch or batch[:1].isdigit() or date is None:continue
        typ=str(r.get('materialtype') or '').upper()
        if finished and code.casefold() not in finished:continue
        if typ and typ not in ('ZFGS','ZFG','FG','ZFERT','FERT'):continue
        source=row_source(list(raw),list(raw.values()))
        if not source:
            tags=mapping.get(code,set())
            source=next(iter(tags)) if len(tags)==1 else ''
        key=(date.year,code.casefold(),batch.casefold(),source.casefold())
        g=groups.setdefault(key,{'code':code,'batch':batch,'year':date.year,'description':r.get('materialdescription'),'unit':r.get('baseunitofmeasure') or r.get('unitofentry'),'source':source,'moves':defaultdict(float),'release':False})
        kind=ident(r.get('movementtype'));q=num(r.get('quantity'))
        if q is None:q=num(r.get('qtyinunofentry'))
        if q is None:continue
        # 321 has paired positive/negative stock legs: retain receiving side once.
        if kind=='321':
            if q>0:g['release']=True;g['moves'][kind]+=q
        elif kind in ('101','102','331','332','551','552'):g['moves'][kind]+=q
    headers=['Year','Batch','Material(text)','Material','UoM','Order Quantity','Rejection Quantity','QC Quantity','FG Quantity','Source.Name']
    rows=[]
    for g in groups.values():
        if not g['release']:continue
        m=g['moves'];matched=list(orders.get((g['code'].casefold(),g['batch'].casefold()),{}).values())
        quantities=[num(r.get('Order quantity (GMEIN)')) for r in matched];confirmed=[num(r.get('Confirmed quantity (GMEIN)')) for r in matched]
        quantity=sum(quantities) if quantities and all(v is not None for v in quantities) else None
        rejection=(sum(confirmed)-quantity if sum(confirmed)>0 else 0) if quantity is not None and all(v is not None for v in confirmed) else None
        qc=m.get('331') if '331' in m else None
        if '332' in m:qc=(qc or 0)+m['332']
        rows.append([g['year'],g['batch'],g['description'],g['code'],g['unit'],quantity,rejection,qc,m['321'],g['source'] or None])
    return {**saved,'headers':headers,'rows':sorted(rows,key=lambda r:(str(r[0]),str(r[1]),str(r[3]))),'basis':'Embedded movement records; positive 321 receiving side, order quantity and confirmed-minus-order rejection (unconfirmed orders retain zero); signed 331/332 QC adjustments'}

def summary_sheet(data,saved):
    table,bom=records(data,'BOM');stock_table,stocks=records(data,'Stock Data')
    required={'Material','Max Quantity to be produced from current stock','MAX QUANTITY CAN BE PRODUCED AFTER RECEIVING STOCK'}
    if table is None or stock_table is None or not required.issubset(table['headers']) or 'Current Stock' not in stock_table['headers']:return saved
    stock=defaultdict(float)
    for r in stocks:
        value=num(r.get('Current Stock'))
        if value is not None:stock[material_code(r.get('Material')).casefold()]+=value
    groups=defaultdict(list)
    for r in bom:
        source=row_source(list(r),list(r.values()))
        groups[(material_code(r.get('Material')),source)].append(r)
    rows=[]
    for (code,source),items in groups.items():
        if not code:continue
        def capacity(header):
            values=[num(r.get(header)) for r in items]
            return min(values) if values and all(v is not None for v in values) else None
        rows.append([code,items[0].get('Material(text)'),stock[code.casefold()],capacity('Max Quantity to be produced from current stock'),capacity('MAX QUANTITY CAN BE PRODUCED AFTER RECEIVING STOCK'),source or None])
    return {**saved,'headers':['Material','Material(text)','Current FG Stock','Max Quantity to be produced from current stock','MAX QUANTITY CAN BE PRODUCED AFTER RECEIVING STOCK','Source.Name'],'rows':sorted(rows,key=lambda r:str(r[0])),'basis':'Embedded stock and BOM records; minimum component capacity per FG'}

def apply(data):
    return {**data,'sheets':[summary_sheet(data,s) if norm(s['name'])=='summary' else bom_sheet(data,s) if norm(s['name'])=='bomcost' else completed_sheet(data,s) if norm(s['name'])=='productiondata' else s for s in data.get('sheets',[])]}
