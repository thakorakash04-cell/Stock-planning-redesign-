"""Server-side segment boundaries for workbook rows and shared plans."""
import hashlib,json,re
REVISION=2

CODE_HEADERS=('Material','Material Code','Material Number','SKU Code','FG Code','FG Material','FG Material Code','FG Material Number','Component')
def name(value):
    from workbook import source_segment
    return source_segment(value)
def available(data):
    from workbook import segment_map,row_source,source_index,source_segment
    tables=data.get('tables',[])
    return sorted({s for values in segment_map(tables).values() for s in values}|{source_segment(r[i]) for t in tables if (i:=source_index(t['headers'],False)) is not None for r in t['rows'] if source_segment(r[i])})
def validate(value,choices):
    if value is None:return None
    if not isinstance(value,list) or len(value)>200 or any(not isinstance(v,str) or v not in choices for v in value):raise ValueError('Choose valid master-workbook segments.')
    return sorted(set(value))
def scope_data(data,segments):
    if segments is None:return data
    from workbook import segment_map,material_code,source_index
    wanted={name(v).casefold() for v in segments};mapping=segment_map(data.get('tables',[]))
    codes={material_code(k).casefold() for k,v in mapping.items() if wanted.intersection(name(s).casefold() for s in v)}
    def table(t,is_sheet=False):
        headers=t['headers'];norm=lambda v:re.sub(r'[^a-z0-9]','',str(v).casefold())
        source_pos=source_index(headers,fallback=norm(t['name']) not in ('dpmrp','dpmrpdata'))
        source=headers[source_pos] if source_pos is not None else None
        keys={norm(h) for h in CODE_HEADERS}
        code=next((h for h in headers if norm(h) in keys),None)
        if t.get('name')=='Calendar':return {**t,'rows':[]}
        rows=[]
        for row in t['rows']:
            if source and name(row[headers.index(source)]):
                if name(row[headers.index(source)]).casefold() not in wanted:continue
            elif not code or material_code(row[headers.index(code)]).casefold() not in codes:continue
            if is_sheet and (not source or not name(row[headers.index(source)])) and code and not {name(v).casefold() for v in mapping.get(str(row[headers.index(code)]),set())}.issubset(wanted):continue
            rows.append(row)
        return {**t,'rows':rows}
    return {**data,'sheets':[table(t,True) for t in data.get('sheets',[])],'tables':[table(t) for t in data.get('tables',[])]}
def scope_key(segments):
    return hashlib.sha256(json.dumps([REVISION,sorted(segments)]).encode()).hexdigest() if segments is not None else 'all'
def current_scope(current,segments):
    if segments is None:return current
    scope=scope_key(segments)
    return {**current,'data':scope_data(current['data'],segments),'_scope':scope,'_segments':segments}
def plan_visible(current,payload,plan_id=None):
    if '_segments' not in current:return True
    from workbook import segment_map
    from .production import ident,order_key
    from .production_materials import records,resolve
    segments={name(v) for v in current['_segments']};chosen=payload.get('segment')
    if chosen:return chosen in segments
    mapping=segment_map(current['data'].get('tables',[]))
    material=resolve(current['data'],payload)
    code=ident(payload.get('materialCode') or (material or {}).get('code') or payload.get('product'))
    if code and segments.intersection(mapping.get(code,set())):return True
    return bool(plan_id and plan_id in {order_key(r) for r in records(current['data'],'Production Order Details')})
def plans(current,rows):
    return [r for r in rows if plan_visible(current,json.loads(r['payload']),r['id'])]

