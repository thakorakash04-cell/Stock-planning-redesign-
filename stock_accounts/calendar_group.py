"""Validated calendar-month dimensions shared by Ask AI, Insights and Sales."""
import copy,re
from datetime import date,datetime
MONTHS=('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec')
FULL_MONTHS=('January','February','March','April','May','June','July','August','September','October','November','December')
REVISION=1
PROTOCOL='''For month-wise/monthly sales or Month against Invoice value, aggregate invoices into calendar months, not individual invoice dates. Set date_group={"column":"exact invoice/billing date header","grain":"month","alias":"Month"}, group_by=["Month"], metrics=[{"column":"exact Invoice value header","op":"sum"}], sort_by="Month", descending=false. The derived Month output uses Jun 2026 labels, keeps years distinct and sorts chronologically. Use the explicitly requested date field; if several date bases are equally plausible ask which one. Only if there is no full date field may date_group include year_column="exact Year header" and column="exact Month header". Never guess a year or merge different years into June. The alias must not overwrite a real source column; use Calendar Month if Month exists. Raw dates are for explicit daily/date-wise requests. Missing/invalid dates remain in Unknown month with a note. Preserve requested filters, measures, signs and units; no date_group is needed for ordinary nonmonthly queries.'''
def norm(value):return re.sub(r'[^a-z0-9]','',str(value).casefold())
def schema(table,config):
 if not isinstance(config,dict) or set(config)-{'column','grain','alias','year_column'} or config.get('grain')!='month':raise ValueError('Use date_group with column, grain=month, alias and optional year_column only.')
 headers=table['headers']
 def column(value):
  matches=[h for h in headers if norm(h)==norm(value)] if isinstance(value,str) else []
  if len(matches)!=1:raise ValueError('Choose an exact, unambiguous date/month column.')
  return matches[0]
 out={'column':column(config.get('column')),'grain':'month','alias':config.get('alias','Calendar Month' if any(norm(h)=='month' for h in headers) else 'Month')}
 if 'year_column' in config:
  out['year_column']=column(config['year_column'])
  if re.match(r'^(fy|fiscal|financial)',norm(out['year_column'])):raise ValueError('Use calendar Year or invoice dates; a financial year alone does not identify a calendar month.')
 if norm(out['column']) in ('month','invoicemonth','calendarmonth') and not out.get('year_column'):raise ValueError('A month-only field requires an explicit Year column; do not guess the year.')
 alias=out['alias']
 if not isinstance(alias,str) or not 1<=len(alias)<=100 or any(ord(c)<32 for c in alias):raise ValueError('Choose a valid calendar-month output name.')
 if any(norm(h)==norm(alias) for h in headers) and table.get('_date_group')!=out:raise ValueError('The calendar-month alias cannot overwrite a source column.')
 return out

def month_date(value,year=None):
 if isinstance(value,bool):return None
 if year is not None:
  try:
   if isinstance(year,bool) or float(year)!=int(float(year)):return None
   y=int(float(year));token=str(value).strip();m=int(float(token)) if re.fullmatch(r'\d+(?:\.0+)?',token) else next((i for i,name in enumerate(MONTHS,1) if token.casefold() in (name.casefold(),FULL_MONTHS[i-1].casefold(),('sept' if i==9 else name.casefold()))),0)
   return date(y,m,1)
  except (ValueError,TypeError,OverflowError):return None
 if isinstance(value,str) and re.fullmatch(r'\d{4}-\d{2}',value.strip()):value=value.strip()+'-01'
 from .pnl_import import day
 try:return day(value)
 except (TypeError,ValueError,OverflowError):return None

def month_key(value):
 match=re.fullmatch(r'([A-Za-z]{3}) (\d{4})',str(value))
 if not match or match[1] not in MONTHS:return 10**9
 return int(match[2])*12+MONTHS.index(match[1])

def prepare(table,config):
 config=schema(table,config)
 if table.get('_date_group')==config:return table,0
 ci=table['headers'].index(config['column']);yi=table['headers'].index(config['year_column']) if config.get('year_column') else None
 rows=[];unknown=0;cache={}
 for row in table['rows']:
  value=row[ci];year=row[yi] if yi is not None else None;key=(type(value).__name__,str(value),str(year),yi is not None)
  if key not in cache:
   parsed=None if yi is not None and year is None else month_date(value,year)
   cache[key]=f'{MONTHS[parsed.month-1]} {parsed.year:04}' if isinstance(parsed,date) and isinstance(parsed.year,int) else 'Unknown month'
  label=cache[key];unknown+=label=='Unknown month';rows.append(list(row)+[label])
 return {**table,'headers':table['headers']+[config['alias']],'rows':rows,'_date_group':config},unknown

def wants_month(question):
 text=str(question).casefold()
 if re.search(r'\b(daily|date[ -]?wise|day[ -]?wise|by date|by day)\b',text):return False
 if not re.search(r'\b(month|months|monthly|monthwise)\b',text):return False
 if re.search(r'\b(this|last|next|current|previous) month\b',text) and not re.search(r'\b(monthly|monthwise|per month|by month|each month)\b',text):return False
 return True

def monthly_query(tables,question,query,value=None):
 """Repair only an explicit monthly request; never infer periods from table text."""
 if not wants_month(question):return copy.deepcopy(query)
 if not isinstance(query,dict):raise ValueError('Use a query object for the monthly comparison.')
 result=copy.deepcopy(query);matches=[t for t in tables if t['id']==result.get('table')] or [t for t in tables if norm(t['name'])==norm(result.get('table'))]
 if len(matches)>1:raise ValueError('Choose a uniquely named sales table for the monthly comparison.')
 if not matches:return result
 table=matches[0]
 headers=table['headers'];groups=result.get('group_by') or [];groups=[groups] if isinstance(groups,str) else groups
 if not isinstance(groups,list) or any(not isinstance(group,str) for group in groups):raise ValueError('Use exact grouping field names and a date_group month definition.')
 groups=[next((h for h in headers if norm(h)==norm(group)),group) for group in groups]
 if result.get('date_group'):
  config=schema(table,result['date_group']);source=config['column'];alias=config['alias']
 else:
  explicit=[h for h in groups if h in headers and 'date' in norm(h)]
  invoice=[h for h in headers if norm(h) in ('invoicedate','billingdate','invoicedocumentdate')]
  dates=[h for h in headers if norm(h).endswith('date') or norm(h) in ('date','invoicedon','billedon')]
  mentioned=[h for h in dates if norm(h) in norm(question)]
  candidates=mentioned if len(mentioned)==1 else invoice or dates
  years=[h for h in headers if norm(h) in ('year','calendaryear','invoiceyear')];months=[h for h in headers if norm(h) in ('month','invoicemonth')]
  if len(candidates)==1:source=candidates[0];config={'column':source,'grain':'month'}
  elif not candidates and len(years)==len(months)==1:source=months[0];config={'column':source,'year_column':years[0],'grain':'month'}
  else:raise ValueError('Choose the invoice/billing date field for calendar-month grouping; a month name without a year is ambiguous.')
  alias='Month' if not any(norm(h)=='month' for h in headers) else 'Calendar Month'
  config['alias']=alias;config=schema(table,config)
 metrics=result.get('metrics') or []
 if not isinstance(metrics,list) or any(not isinstance(metric,dict) for metric in metrics):raise ValueError('Use metric objects with column and op for monthly totals.')
 if not metrics:
  field=value if value in headers else None
  if field is None:
   candidates=[h for h in headers if norm(h) in norm(question) and re.search(r'invoice.*(?:value|amount)|sales.*(?:value|amount)|net(?:value|amount)|revenue|totalamount',norm(h))]
   if len(candidates)==1:field=candidates[0]
  if not field or not re.search(r'invoice.*(?:value|amount)|sales.*(?:value|amount)|net(?:value|amount)|revenue|totalamount',norm(field)):raise ValueError('Choose an additive invoice/sales value measure for the monthly total.')
  metrics=[{'column':field,'op':'sum'}]
 result.update(table=table['id'],date_group=config,metrics=metrics,group_by=list(dict.fromkeys([alias if h==source or h in (config.get('year_column'),alias) or norm(h) in ('month','invoicemonth','calendarmonth') else h for h in groups]+([alias] if alias not in groups and source not in groups else []))),columns=[])
 if norm(result.get('sort_by','')) in (norm(source),norm(alias),'month','calendarmonth'):result['sort_by']=alias
 for metric in metrics:
  if result.get('sort_by')==metric.get('column'):result['sort_by']=str(metric.get('op','sum'))+'('+metric['column']+')'
 if not re.search(r'\b(top|bottom|highest|lowest|largest|smallest|descending|newest first|latest first)\b',question,re.I):result.update(sort_by=alias,descending=False)
 return result


def monthly_chart(tables,question,chart):
 result=copy.deepcopy(chart);result['query']=monthly_query(tables,question,result.get('query',{}),result.get('value'))
 if result['query'].get('date_group'):
  from grounded_ai import normalize_query
  result['query'],aliases=normalize_query(tables,result['query'],with_aliases=True);result['label']=result['query']['date_group']['alias']
  if result['query']['metrics']:
   requested=aliases.get(result.get('value'),result.get('value'))
   matches=[m for m in result['query']['metrics'] if norm(m['column'])==norm(requested) or norm(m['op']+'('+m['column']+')')==norm(requested)]
   if len(matches)!=1:raise ValueError('Choose the exact numeric measure for the monthly graph.')
   metric=matches[0];result['value']=metric['op']+'('+metric['column']+')'
  outputs=[m['op']+'('+m['column']+')' for m in result['query']['metrics']]
  if result.get('type')=='scatter' and result.get('x') not in outputs:result['type']='column';result.pop('x',None)
 return result
