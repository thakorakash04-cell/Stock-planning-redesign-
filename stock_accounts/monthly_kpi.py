"""Bounded current/previous calendar-month sales comparison, without model arithmetic."""
import copy,math,re
from datetime import datetime
from .clock import IST
from .calendar_group import monthly_query,prepare,norm,MONTHS
REVISION=1
PROTOCOL='''A current-month sales value KPI with percentage growth from last month IS supported. Use a single sum metric on the exact additive invoice/sales value field and comparison={"kind":"month_over_month","date_column":"exact invoice date header","value_column":"exact invoice value header","reference_month":"current"}. The server derives both calendar-month totals and percentage change from the same authorized source; never compute these values in model text. Optional year_column is allowed only with a Month+calendar Year source. Missing months are unavailable, and zero/negative previous-month baselines have no growth percentage. Preserve filters and currency/units. Do not claim this needs an unsupported cross-sheet operation.'''
def current_month():return datetime.now(IST).strftime('%Y-%m')
def intent(question):
 return bool(re.search(r'\b(current|this)[ -]*month\b',question,re.I) and re.search(r'growth|percent|percentage|month.over.month|\bmom\b',question,re.I))
def proposal(table,question,spec=None):
 if not intent(question):return spec
 spec=copy.deepcopy(spec or {});query=spec.get('query') if isinstance(spec.get('query'),dict) else {}
 candidates=[h for h in table['headers'] if re.search(r'invoice.*(?:value|amount)|sales.*(?:value|amount)|net(?:value|amount)|revenue',norm(h))]
 named=[h for h in candidates if norm(h) in norm(question)]
 if len(named)==1:candidates=named
 if len(candidates)!=1:raise ValueError('Choose the exact additive sales/invoice value column for the month-over-month KPI.')
 value=candidates[0];base={'table':table['id'],'metrics':[{'column':value,'op':'sum'}],'filters':query.get('filters',[]),'limit':1}
 monthly=monthly_query([table],'monthly '+question,base,value);group=monthly['date_group']
 if not re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{4}',question):base['filters']=[f for f in base['filters'] if norm(f.get('column')) not in (norm(group['column']),norm(group['alias']))]
 comparison={'kind':'month_over_month','date_column':group['column'],'value_column':value,'reference_month':'current'}
 if group.get('year_column'):comparison['year_column']=group['year_column']
 return {'title':spec.get('title','Current month sales and growth'),'basis':spec.get('basis','Current calendar month versus previous calendar month; recorded invoice signs retained.'),'value':'sum('+value+')','query':base,'comparison':comparison}
def result(tables,view,spec):
 from grounded_ai import execute_query,normalize_query
 from .insight_dashboard import kpi_result
 config=copy.deepcopy(spec.get('comparison'))
 if not isinstance(config,dict) or set(config)-{'kind','date_column','value_column','reference_month','year_column'} or config.get('kind')!='month_over_month':raise ValueError('Choose a supported month-over-month comparison.')
 base=copy.deepcopy(spec.get('definition_query',spec.get('query',{})));base=normalize_query(tables,base)
 if base.get('table')!=view['table_id'] or base.get('group_by') or len(base.get('metrics',[]))!=1:raise ValueError('Choose one whole-scope additive KPI measure.')
 metric=base['metrics'][0]
 if metric['op']!='sum' or norm(metric['column'])!=norm(config.get('value_column')):raise ValueError('Month-over-month sales needs one sum of the selected invoice value.')
 config['value_column']=metric['column'];config['reference_month']=config.get('reference_month','current')
 month=current_month() if config['reference_month']=='current' else config['reference_month']
 if not isinstance(month,str) or not re.fullmatch(r'\d{4}-\d{2}',month):raise ValueError('Use current or an explicit YYYY-MM reference month.')
 try:year,number=map(int,month.split('-'));datetime(year,number,1)
 except ValueError:raise ValueError('Choose a valid reference month.') from None
 prior_year,prior_number=(year-1,12) if number==1 else (year,number-1)
 if prior_year<1:raise ValueError('Previous month is outside the supported calendar.')
 previous=f'{prior_year:04}-{prior_number:02}';labels=[f'{MONTHS[number-1]} {year:04}',f'{MONTHS[prior_number-1]} {prior_year:04}']
 table=next(t for t in tables if t['id']==base['table']);group={'column':config.get('date_column'),'grain':'month','alias':'Calendar Month' if any(norm(h)=='month' for h in table['headers']) else 'Month'}
 if config.get('year_column'):group['year_column']=config['year_column']
 expanded,_=prepare(table,group);group=expanded['_date_group'];config['date_column']=group['column']
 if len(base.get('filters',[]))>9:raise ValueError('Use at most nine base filters for this comparison.')
 evidence=[]
 for label in labels:
  query={**base,'date_group':group,'filters':base.get('filters',[])+[{'column':group['alias'],'op':'eq','value':label}],'limit':1}
  # Existing KPI validation enforces one unit/currency, additive grain and numeric values.
  card=kpi_result([expanded],view,{'title':spec.get('title','Monthly sales'),'value':'sum('+metric['column']+')','basis':spec.get('basis','Recorded sales values'),'query':query})
  evidence.append(card['evidence'])
 # Validate the combined period scope too: two different currencies must not be compared.
 combined={**base,'date_group':group,'filters':base.get('filters',[])+[{'column':group['alias'],'op':'in','value':labels}]}
 kpi_result([expanded],view,{'value':'sum('+metric['column']+')','query':combined})
 field='sum('+metric['column']+')';values=[e['records'][0].get(field) if e['records'] else None for e in evidence];current,prior=values
 growth=(current-prior)/prior*100 if current is not None and prior is not None and prior>0 else None
 if growth is not None and not math.isfinite(growth):growth=None
 note='Growth = (current − previous) / previous × 100. Recorded signs are retained.' if growth is not None else 'Growth unavailable: a month is missing or the previous-month sales baseline is zero/negative.'
 return {'title':str(spec.get('title','Current month sales and growth'))[:100],'value':current,'field':field,'basis':str(spec.get('basis','Calendar month sales; recorded signs retained.'))[:500],'definition_query':base,'comparison':config,'comparison_result':{'current_month':month,'previous_month':previous,'previous_value':prior,'growth_percent':growth,'note':note},'evidence':evidence[0],'comparison_evidence':evidence[1]}

def needs_refresh(report):
 month=current_month()
 return any(k.get('comparison',{}).get('reference_month','current')=='current' and k.get('comparison_result',{}).get('current_month')!=month for s in report.get('sections',[]) for k in s.get('kpis',[]) if k.get('comparison'))
