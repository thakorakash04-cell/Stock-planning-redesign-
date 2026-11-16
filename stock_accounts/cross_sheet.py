"""Bounded read-only joins and arithmetic; no generated code or database queries."""
import math,re,copy
import pandas as pd
from grounded_ai import execute_query,QueryPlanError,numeric_values
from .sales import material_key
from .pnl_import import day

REVISION=5
MAX_ROWS=100000
class PlanError(ValueError):pass
def calculate(tables,plan,trace=False):
    plan=copy.deepcopy(plan)
    sources=plan.get('sources');joins=plan.get('joins');calculations=plan.get('calculations',[])
    if not isinstance(sources,list) or not 1<=len(sources)<=4 or not isinstance(joins,list) or len(joins)!=len(sources)-1:raise PlanError('Use 1–4 loaded sources and one many-to-one join for each additional source.')
    if not isinstance(calculations,list) or len(calculations)>8:raise PlanError('Use at most 8 arithmetic calculations.')
    frames={};matched={};traces=[];output_aliases={}
    for index,spec in enumerate(sources):
        if not isinstance(spec,dict) or spec.get('alias')!='s'+str(index):raise PlanError('Sources must be ordered aliases s0, s1, s2, s3.')
        q={k:v for k,v in spec.items() if k!='alias'}
        q['limit']=20
        try:result=execute_query(tables,q,all_rows=True)
        except QueryPlanError as exc:raise PlanError(str(exc)) from None
        if result['result_rows']>MAX_ROWS:raise PlanError('Pre-aggregate or filter sources to at most 100000 rows.')
        rows=[{k:v for k,v in r.items() if k!='Source row'} for r in result['records']]
        canonical=result['query']
        output_aliases.update({spec['alias']+'.'+name:spec['alias']+'.'+value for name,value in result.get('output_aliases',{}).items()})
        empty_headers=canonical['group_by']+[m['op']+'('+m['column']+')' for m in canonical['metrics']] if canonical['metrics'] else canonical['columns'] or next(t['headers'] for t in tables if t['id']==result['table_id'])
        headers=list(rows[0]) if rows else empty_headers
        frame=pd.DataFrame(rows,columns=headers)
        frame.columns=[spec['alias']+'.'+str(c) for c in frame.columns]
        frames[spec['alias']]=frame;matched[spec['alias']]={'table':result['table'],'matched_records':result['matched_records'],'source_rows':result['result_rows']}
    # Resolve presentation labels to validated metric fields everywhere that a
    # later join/calculation can reference a source output, without editing the
    # original saved plan or guessing arithmetic.
    for join in joins:
        if isinstance(join,dict):
            for side in ('left_on','right_on'):
                if isinstance(join.get(side),list):join[side]=[output_aliases.get(v,v) if isinstance(v,str) else v for v in join[side]]
    for calculation in calculations:
        if isinstance(calculation,dict) and isinstance(calculation.get('operands'),list):calculation['operands']=[output_aliases.get(v,v) if isinstance(v,str) else v for v in calculation['operands']]
    for field in ('columns','group_by'):
        if isinstance(plan.get(field),list):plan[field]=[output_aliases.get(v,v) if isinstance(v,str) else v for v in plan[field]]
    if isinstance(plan.get('metrics'),list):
        for metric in plan['metrics']:
            if isinstance(metric,dict) and isinstance(metric.get('column'),str):metric['column']=output_aliases.get(metric['column'],metric['column'])
    def column(value,columns):
        if not isinstance(value,str):raise PlanError('Use exact prefixed column names such as s0.Material.')
        if value in columns:return value
        key=lambda v:re.sub(r'[^a-z0-9]','',str(v).casefold())
        aliases=[v for name,v in output_aliases.items() if key(name)==key(value)]
        if len(set(aliases))>1:raise PlanError('Unknown or ambiguous joined column: '+value)
        if aliases:value=aliases[0]
        matches=[c for c in columns if key(c)==key(value)]
        if len(matches)!=1:raise PlanError('Unknown or ambiguous joined column: '+value)
        return matches[0]
    frame=frames['s0'];unmatched={}
    for index,j in enumerate(joins,1):
        if not isinstance(j,dict):raise PlanError('Join specifications must be objects.')
        right=frames['s'+str(index)];left_keys=j.get('left_on');right_keys=j.get('right_on')
        if not isinstance(left_keys,list) or not isinstance(right_keys,list) or not 1<=len(left_keys)==len(right_keys)<=3:raise PlanError('Use 1–3 explicit matching keys on each side of a join.')
        left_keys=[column(c,list(frame.columns)) for c in left_keys];right_keys=[column(c,list(right.columns)) for c in right_keys]
        if j.get('how','left')!='left':raise PlanError('Only left joins are supported so missing inputs remain visible.')
        if any(c in frame.columns for c in right.columns):raise PlanError('Each source alias must be unique.')
        left=frame.copy();right=right.drop_duplicates().copy();keys=[]
        for n,(lk,rk) in enumerate(zip(left_keys,right_keys)):
            key='__key'+str(n);keys.append(key)
            clean=lambda v:material_key(v) if v is not None and not pd.isna(v) and str(v).strip() else None
            left[key]=left[lk].map(clean);right[key]=right[rk].map(clean)
        if trace:
            # Reuse the exact source filters and normalized join keys. For a
            # grouped right source, show original rows contributing to its key.
            spec=sources[index];raw=execute_query(tables,{'table':spec['table'],'filters':spec.get('filters',[]),'limit':20},all_rows=True)
            fields=[key.split('.',1)[1] for key in right_keys]
            available=next(t['headers'] for t in tables if t['id']==spec['table'])
            wanted={tuple(row) for row in left[keys].itertuples(index=False,name=None) if all(v is not None for v in row)}
            if all(field in available for field in fields):
                records=[r for r in raw['records'] if tuple(clean(r.get(field)) for field in fields) in wanted]
                headers=list(dict.fromkeys(['Source row']+available))
                traces.append({'name':'Matching records · '+spec['alias']+' · '+raw['table'],'headers':headers,'rows':[[r.get(h) for h in headers] for r in records]})
            else:
                prepared=right.loc[[tuple(r) in wanted for r in right[keys].itertuples(index=False,name=None)]].drop(columns=keys)
                traces.append({'name':'Matching prepared input · s'+str(index),'headers':list(prepared.columns),'rows':prepared.astype(object).where(pd.notna(prepared),None).values.tolist()})
        right=right.dropna(subset=keys)
        if right.duplicated(keys).any():raise PlanError('Right-side keys are not unique for source s'+str(index)+'. Project only needed fields or group/aggregate that source by its join keys before joining. Never multiply many-to-many rows.')
        frame=left.merge(right,on=keys,how='left',validate='many_to_one',indicator=True)
        unmatched['s'+str(index)]=int((frame['_merge']=='left_only').sum())
        frame=frame.drop(columns=keys+['_merge'])
    computed=[]
    for spec in calculations:
        if not isinstance(spec,dict) or set(spec)-{'name','op','operands'}:raise PlanError('Calculations accept name, op and operands only.')
        name=spec.get('name');op=spec.get('op');operands=spec.get('operands')
        if not isinstance(name,str) or not 1<=len(name)<=100 or 'calc.'+name in frame:raise PlanError('Use a unique calculation name.')
        if not isinstance(operands,list) or len(operands)!=2 or op not in ('multiply','add','subtract','divide','percent','date_diff','min','max'):raise PlanError('Each calculation needs two operands and an allowed arithmetic operation.')
        values=[]
        for operand in operands:
            if isinstance(operand,(int,float)) and not isinstance(operand,bool) and math.isfinite(operand):values.append(pd.Series(operand,index=frame.index))
            else:values.append(frame[column(operand,list(frame.columns))])
        a,b=values
        if op=='date_diff':
            a=a.map(day);b=b.map(day);out=pd.Series([(x-y).days if x is not None and y is not None else None for x,y in zip(a,b)],index=frame.index,dtype='float64')
        else:
            a=numeric_values(a);b=numeric_values(b)
            if op=='multiply':out=a*b
            elif op=='add':out=a+b
            elif op=='subtract':out=a-b
            elif op in ('divide','percent'):out=a/b.where(b!=0)*(100 if op=='percent' else 1)
            elif op=='min':out=pd.concat([a,b],axis=1).min(axis=1,skipna=False)
            else:out=pd.concat([a,b],axis=1).max(axis=1,skipna=False)
        field='calc.'+name;frame[field]=pd.to_numeric(out,errors='coerce').replace([float('inf'),float('-inf')],float('nan'));computed.append(field)
    group_by=plan.get('group_by') or [];metrics=plan.get('metrics') or []
    if not isinstance(group_by,list) or len(group_by)>3 or not isinstance(metrics,list) or len(metrics)>4:raise PlanError('Use at most 3 grouping fields and 4 summary metrics.')
    groups=[column(c,list(frame.columns)) for c in group_by]
    synthetic={'id':'JOIN','name':'Joined calculation','headers':list(frame.columns),'rows':frame.where(pd.notna(frame),None).values.tolist()}
    summary_plan={'table':'JOIN','group_by':groups,'metrics':[],'limit':20}
    for metric in metrics:
        if not isinstance(metric,dict) or set(metric)!={'column','op'}:raise PlanError('Summary metrics need column and op.')
        summary_plan['metrics'].append({'column':metric['column'] if metric['column']=='*' else column(metric['column'],list(frame.columns)),'op':metric['op']})
    if groups and not metrics:raise PlanError('Grouping requires a summary calculation.')
    checked=set(computed)|{m['column'] for m in summary_plan['metrics'] if m['column']!='*' and m['op'] not in ('count','distinct_count')}
    missing={c:int(numeric_values(frame[c]).isna().sum()) for c in checked}
    evidence=list(traces)
    if metrics:
        try:summary=execute_query([synthetic],summary_plan,all_rows=True)
        except QueryPlanError as exc:raise PlanError(str(exc)) from None
        headers=list(summary['records'][0]) if summary['records'] else groups
        evidence.append({'name':'Cross-sheet summary (known values)','headers':headers,'rows':[[r.get(h) for h in headers] for r in summary['records']]})
    output=plan.get('columns') or list(frame.columns)
    if not isinstance(output,list):raise PlanError('Output columns must be a list.')
    output=list(dict.fromkeys(column(c,list(frame.columns)) for c in output))
    if len(output)>40:raise PlanError('Choose at most 40 output fields or summarize the result.')
    evidence.append({'name':'Joined source and calculation rows','headers':output,'rows':frame[output].astype(object).where(pd.notna(frame[output]),None).values.tolist()})
    return {'tables':evidence,'sources':matched,'joined_rows':len(frame),'unmatched_rows':unmatched,'missing_calculations':missing,'complete':not any(missing.values()) and not any(unmatched.values()),'detail_truncated':False,
        'limitations':'Only the supplied permission-scoped snapshot is joined. Right-side keys must be unique after explicit source aggregation; many-to-many joins are rejected. Keys normalize case/spacing and numeric .0 suffixes while preserving leading zeros. Missing numeric inputs and division by zero remain unavailable. Summary sums are known-value subtotals if any joined/calculated input is missing. No unit/currency conversion, actual sales, manufacturing feasibility or future outcome is inferred. Preview is limited to 20 rows; all matched detail rows remain available for paged evidence/export. Aggregations use all matched rows.'}
