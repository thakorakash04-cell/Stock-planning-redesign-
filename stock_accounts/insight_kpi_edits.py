"""Small server-owned KPI/graph definitions for editing a browser-cached report."""
import copy,json
import streamlit as st
REVISION=2

def schema(store,db):
 store.run(db,'''CREATE TABLE IF NOT EXISTS insight_kpi_catalog (
 scope TEXT PRIMARY KEY,cache_key TEXT NOT NULL,generation TEXT NOT NULL,catalog TEXT NOT NULL)''')

def publish(store,db,scope,key,report,tables):
 from .insight_memory import kpi_spec,graph_style
 from .insight_display import temporal
 sources={t['id']:t for t in tables};items=[]
 for section in report['sections']:
  for kind in ('kpi','chart'):
   for item in section.get('kpis' if kind=='kpi' else 'charts',[]):
    if not item.get('id'):continue
    query=kpi_spec(item)['query'] if kind=='kpi' else item['evidence']['query'];source=sources.get(query['table'],{})
    small={k:copy.deepcopy(item[k]) for k in ('id','title','field','basis','definition_query','comparison','comparison_result','refresh_error','request','type','label','value','x','top_n') if k in item}
    if kind=='kpi':small.pop('value',None)
    small['evidence']={'table':item['evidence']['table'],'query':copy.deepcopy(item['evidence']['query']),'records':[]}
    if kind=='chart':
     small['_edit_styles']={}
     for style in ('bar','column','lollipop','donut','line','area','scatter'):
      try:small['_edit_styles'][style]=graph_style(item,style)
      except ValueError:pass
    source={k:copy.deepcopy(source[k]) for k in ('id','name','saved_name','refresh_plan','refresh_sources') if k in source}
    items.append({'kind':kind,'view':section['view'],'item':small,'source':source})
 catalog={'revision':REVISION,'items':items,'period_sensitive':temporal(report)}
 schema(store,db)
 store.run(db,'''INSERT INTO insight_kpi_catalog(scope,cache_key,generation,catalog) VALUES(?,?,?,?)
 ON CONFLICT(scope) DO UPDATE SET cache_key=excluded.cache_key,generation=excluded.generation,catalog=excluded.catalog''',
 (scope,key,report['cache_generation'],json.dumps(catalog,allow_nan=False,separators=(',',':'))))

def edit(store,actor,event,version):
 from . import insight_memory as memory
 from .insight_display import metadata,temporal
 from .assistant_insights import report_scope,data_revision
 from .planning_assistant import knowledge
 from .monthly_kpi import current_month
 kind='kpi' if event.get('item_kind')=='kpi' else 'chart';field='kpi_id' if kind=='kpi' else 'chart_id';collection='custom_kpis' if kind=='kpi' else 'custom';removed='deleted_kpis' if kind=='kpi' else 'deleted'
 if type(event.get('view')) is not int or not isinstance(event.get(field),str) or not 1<=len(event[field])<=100:raise ValueError('Choose a current graph or KPI.')
 token=str(event.get('report_id',''));scope=memory.scope_key(store,actor);key=memory.cache_key(store,actor,version)
 if event.get('version')!=version:raise ValueError('The workbook changed. Reopen Insights.')
 active=st.session_state.get('_stock_dashboard_reports',{}).get(token);temporary=False
 if active is None:
  binding=st.session_state.get('_stock_insight_lazy',{}).get(token)
  if not binding or binding['scope']!=report_scope(store,actor) or binding['version']!=version:raise ValueError('This report display expired. Reopen Insights.')
  meta=metadata(store,actor,version,binding['period_sensitive'],check_pending=False)
  if not meta['current']:raise ValueError('Saved data or graphs changed. Reopen Insights.')
  changed=meta['stamp']!=binding['stamp']
  with store.transaction() as db:
   store.require(db,actor,permission='use_tools');schema(store,db)
   found=store.run(db,'SELECT cache_key,generation,catalog FROM insight_kpi_catalog WHERE scope=?',(scope,)).fetchone()
   if not found or found['cache_key']!=key or json.loads(found['catalog']).get('revision')!=REVISION:
    # One-time migration of older saved reports. Never rebuild sources/evidence.
    saved=memory.row(store,db,scope,True)
    if saved['cache_key']!=key or not saved['snapshot']:raise ValueError('The saved report changed. Reopen Insights.')
    value=memory.unpack(saved['snapshot']);publish(store,db,scope,key,value['report'],value['tables'])
    found=store.run(db,'SELECT cache_key,generation,catalog FROM insight_kpi_catalog WHERE scope=?',(scope,)).fetchone()
  catalog=json.loads(found['catalog']);selected=next((d for d in catalog['items'] if d.get('kind','kpi')==kind and d['view']==event.get('view') and d['item']['id']==event.get(field)),None)
  if selected is None:raise ValueError('Choose a current graph or KPI.')
  if event.get('cache_generation') and event['cache_generation']!=found['generation']:raise ValueError('Another user regenerated the report. Reopen Insights.')
  if changed:
   # A commit can succeed while its acknowledgement is lost. Confirm only the
   # same generation and already-durable state; never replay an unrelated edit.
   with store.transaction() as db:
    store.require(db,actor,permission='use_tools')
    latest=store.run(db,'SELECT cache_key,layout,revision FROM insight_memory WHERE scope=?',(scope,)).fetchone()
   layout=json.loads(latest['layout']);saving=event.get('action')=='save_insight_item';item_id=event.get(field)
   committed=any(d['id']==item_id for d in layout.get(collection,[])) if saving else item_id in layout.get(removed,[])
   style=None
   if committed and saving and kind=='chart':
    style=memory.graph_style(selected['item'],event.get('chart_type',selected['item'].get('type','bar')))
    committed=any(d['id']==item_id and d.get('spec',{}).get('type')==style for d in layout.get(collection,[]))
   if latest['cache_key']!=key or layout.get('_generation')!=found['generation'] or event.get('cache_generation')!=found['generation'] or not committed:raise ValueError('Saved data or graphs changed. Reopen Insights.')
   result={'report_id':token,'view':event['view'],'item_id':item_id,'item_kind':kind,'saved':saving,'deleted':not saving,'chart_type':style,'layout_revision':latest['revision']}
   return acknowledge(event,result,key,catalog['period_sensitive'])
  item=selected['item']
  if item.get('comparison',{}).get('reference_month')=='current' and item.get('comparison_result',{}).get('current_month')!=current_month():raise ValueError('The calendar month changed. Reopen Insights.')
  active={'version':version,'scope':report_scope(store,actor),'planning_revision':str(data_revision(store,actor)),'knowledge_revision':knowledge()['revision'],'cache_generation':found['generation'],'tables':[selected['source']],'sections':[{'view':event['view'],'kpis':[item] if kind=='kpi' else [],'charts':[item] if kind=='chart' else []}]}
  st.session_state.setdefault('_stock_dashboard_reports',{})[token]=active;temporary=True
  sensitive=catalog['period_sensitive']
 else:sensitive=temporal({'sections':active['sections']})
 try:result=memory.fast_edit(store,actor,event,version)
 finally:
  if temporary:st.session_state['_stock_dashboard_reports'].pop(token,None)
 return acknowledge(event,result,key,sensitive)

def acknowledge(event,result,key,sensitive):
 from .insight_memory import digest
 from .monthly_kpi import current_month
 # No full report copy, evidence registration or per-section row hashing.
 period=current_month() if sensitive else ''
 result.update(report_stamp=digest([key,result['layout_revision'],period]),period_sensitive=sensitive,invalidated_views=[event['view']])
 binding=st.session_state.get('_stock_insight_lazy',{}).get(str(event.get('report_id','')))
 if binding:binding.update(stamp=result['report_stamp'],period_sensitive=sensitive)
 return result
