"""Audited production-to-Std-DP join over the current permission-scoped snapshot."""
from collections import defaultdict
from decimal import Decimal
from .access import require_menu
from .sales import material_key
from .bom_prices import price_index,norm
from .production_materials import dec
from workbook import segment_map,source_segment

REVISION=1
def records(data,name):
    table=next((t for t in data.get('tables',[]) if norm(t['name'])==norm(name)),None)
    return [dict(zip(table['headers'],r)) for r in table['rows']] if table else []
def unit(value):return str(value or '').strip().upper()

def calculate(data,report,selection=None):
    selection=selection or {}
    convention=selection.get('price_convention','sku')
    if convention not in ('sku','strict'):raise ValueError('Choose sku or strict price convention.')
    quantity_basis=selection.get('ongoing_quantity','expected')
    if quantity_basis not in ('expected','order'):raise ValueError('Choose expected or order quantity for ongoing batches.')
    statuses=selection.get('production_statuses') or ['ongoing','qc']
    if not isinstance(statuses,list) or not statuses or any(s not in ('ongoing','qc') for s in statuses):raise ValueError('Choose ongoing and/or qc production status.')
    segments=selection.get('segments') or []
    if not isinstance(segments,list) or any(not isinstance(s,str) for s in segments):raise ValueError('Choose valid segment names.')
    wanted={source_segment(s).casefold() for s in segments}
    material=selection.get('material') or ''
    if not isinstance(material,str):raise ValueError('Choose an exact material code.')
    prices=price_index(data);mapping=segment_map(data.get('tables',[]))
    order_units=defaultdict(set);price_units=defaultdict(set);fallback_units=defaultdict(set)
    for r in records(data,'Production Order Details'):
        if r.get('Unit of measure (=GMEIN)'):order_units[(material_key(r.get('Material Number')),str(r.get('Order')).strip())].add(unit(r['Unit of measure (=GMEIN)']))
    for r in report.get('materials',[]):
        if r.get('unit'):fallback_units[material_key(r['code'])].add(unit(r['unit']))
    tables=data.get('tables',[])
    preferred=[t for t in tables if norm(t['name']) in ('dpmrp','dpmrpdata')]
    for table in preferred or tables:
        hs=[norm(h) for h in table['headers']]
        if not any(h in ('stddp','standarddp','stddpvalue','stddpprice','stddpinr','dpmrpstddp') for h in hs):continue
        ki=next((i for i,h in enumerate(hs) if h in ('material','materialcode','materialnumber','sku','skucode')),None)
        ui=next((i for i,h in enumerate(hs) if h in ('uom','unit','baseunitofmeasure')),None)
        if ki is not None and ui is not None:
            for r in table['rows']:
                if r[ui]:price_units[material_key(r[ki])].add(unit(r[ui]))
    groups={};qc_pairs=set()
    # QC wins over ongoing when both windows contain the same material/batch.
    for index,r in enumerate(report['qc']['rows']):
        pair=(material_key(r[0]),str(r[2]).strip().casefold());qc_pairs.add(pair)
        if 'qc' not in statuses:continue
        tags=report['qc'].get('segments',[]);tags=tags[index] if index<len(tags) else sorted(mapping.get(r[0],set()))
        key=('Under QC',*pair)
        g=groups.setdefault(key,{'code':r[0],'batch':r[2],'description':r[1],'tags':set(),'quantities':[],'units':set(),'seen':set(),'type':str(r[7] or '').upper(),'basis':'Confirmed quantity; QC release pending'})
        g['tags'].update(tags);identity=str(r[6]).strip() if r[6] is not None else repr(r)
        if identity in g['seen']:continue
        g['seen'].add(identity);g['quantities'].append(dec(r[4]));g['units'].update(order_units.get((pair[0],identity),set()))
    for item in report['ongoing']:
        r=item['row'];pair=(material_key(r[2]),str(r[4]).strip().casefold())
        if 'ongoing' not in statuses or pair in qc_pairs:continue
        key=('Ongoing',*pair)
        g=groups.setdefault(key,{'code':r[2],'batch':r[4],'description':r[3],'tags':set(),'quantities':[],'units':set(),'seen':set(),'type':str(r[1] or '').upper(),'basis':'Expected FG quantity; production estimate / saved override'})
        g['tags'].update(item.get('segments') or mapping.get(r[2],set()))
        if item['id'] in g['seen']:continue
        g['seen'].add(item['id']);g['quantities'].append(dec(r[8] if quantity_basis=='expected' else r[5]))
        if quantity_basis=='order':g['basis']='Order quantity; theoretical value before yield losses'
        g['units'].update(order_units.get((pair[0],str(r[0]).strip()),set()))
    details=[];sums=defaultdict(lambda:{'value':Decimal(0),'batches':0,'missing':0});excluded=0
    for (status,sku,_),g in groups.items():
        if material and sku!=material_key(material):continue
        if wanted and not wanted.intersection(source_segment(s).casefold() for s in g['tags']):continue
        if not g['units']:g['units'].update(fallback_units.get(sku,set()))
        qty=sum(g['quantities'],Decimal(0)) if g['quantities'] and all(v is not None and v>=0 for v in g['quantities']) else None
        options=prices.get(sku,[set(),set()])[0]
        price=dec(next(iter(options))) if len(options)==1 else None
        q_units=g['units'];p_units=price_units[sku];reason=[]
        if qty is None:reason.append('Missing expected / confirmed quantity')
        if price is None or price<0:reason.append('Missing / conflicting Std DP')
        unit_difference=len(q_units)!=1 or len(p_units)!=1 or q_units!=p_units
        if convention=='strict' and unit_difference:reason.append('Missing / conflicting units or conversion required')
        unit_note='; workbook SKU price convention; unit labels differ, no pack conversion' if convention=='sku' and unit_difference else ''
        is_sfg=g['type'] in ('ZSFG','SFG') and not material
        if is_sfg:reason.append('SFG excluded from finished-goods sales total')
        value=qty*price if not reason else None
        if is_sfg:excluded+=1
        else:sums[status]['batches']+=1;sums[status]['missing']+=int(value is None)
        if value is not None:sums[status]['value']+=value
        details.append([status,', '.join(sorted(g['tags'])),g['code'],g['description'],g['batch'],float(qty) if qty is not None else None,', '.join(sorted(q_units)),float(price) if price is not None else None,', '.join(sorted(p_units)),float(value) if value is not None else None,g['basis']+unit_note, '; '.join(reason) or 'Valued'])
    rows=[]
    for status,g in sorted(sums.items()):rows.append([status,g['batches'],g['batches']-g['missing'],g['missing'],float(g['value']),float(g['value']) if not g['missing'] else None])
    missing=sum(g['missing'] for g in sums.values());subtotal=sum((g['value'] for g in sums.values()),Decimal(0))
    rows.append(['Combined',sum(g['batches'] for g in sums.values()),sum(g['batches']-g['missing'] for g in sums.values()),missing,float(subtotal),float(subtotal) if not missing else None])
    return {'summary':{'headers':['Production Status','Batches','Valued Batches','Unvalued Batches','Known Potential Value','Complete Potential Value'],'rows':rows},
        'details':{'headers':['Production Status','Segment','Material','Description','Batch','Quantity','Quantity Unit','Std DP','Price Unit','Potential Value','Quantity Basis','Status / Missing Inputs'],'rows':details},
        'complete':not missing,'excluded_sfg_batches':excluded,'price_convention':convention,'limitations':'Potential snapshot value = expected FG quantity (ongoing) or confirmed quantity (Under QC) × SKU Std DP from the same source used by BOM Cost. The default retains the workbook per-SKU Std DP convention even when quantity/price unit labels differ; it does not perform a pack conversion. Strict unit matching can be requested. No historical price, discount, tax or guaranteed sale is inferred. QC release and actual yield may change quantities. Missing values remain unvalued; known subtotals are not complete totals. Duplicate orders are deduplicated and a batch present in QC is not counted again as ongoing. SFG batches are excluded from combined finished-goods sales unless an individual SFG material is explicitly requested.'}

def run(store,actor,current,selection):
    require_menu(store,actor,3);require_menu(store,actor,1)
    from .production import read
    report=read(store,actor,current=current,archive=False)
    result=calculate(current['data'],report,selection)
    return {**result,'referenceDate':report.get('referenceDate'),'source':{'filename':current['filename'],'version':current['version']}}
