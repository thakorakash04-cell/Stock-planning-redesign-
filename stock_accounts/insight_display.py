"""Permission-checked display stamps and lazy evidence for persistent dashboards.

Browser values never authorize queries. Lazy references resolve only to a saved,
server-owned chart/KPI after the durable report and live access are revalidated.
"""
import copy,secrets
import streamlit as st
REVISION=3

def temporal(report):
 return any(k.get('comparison',{}).get('reference_month','current')=='current' for section in (report or {}).get('sections',[]) for k in section.get('kpis',[]) if k.get('comparison'))

def metadata(store,actor,version,sensitive=False,check_pending=True):
 from . import insight_memory as memory
 from .monthly_kpi import current_month
 scope=memory.scope_key(store,actor);key=memory.cache_key(store,actor,version)
 with store.transaction() as db:
  store.require(db,actor);memory.schema(store,db)
  size='length(snapshot)' if store.sqlite else 'octet_length(snapshot)'
  row=store.run(db,'SELECT cache_key,revision,'+size+' AS size FROM insight_memory WHERE scope=?',(scope,)).fetchone()
  pending=False
  if check_pending:
   memory.checkpoint_schema(store,db)
   pending=bool(store.run(db,'SELECT 1 FROM insight_checkpoints WHERE scope=? AND cache_key=?',(scope,key)).fetchone())
 revision=row['revision'] if row else '';period=current_month() if sensitive else ''
 return {'scope':scope,'key':key,'revision':revision,'stamp':memory.digest([key,revision,period]),'current':bool(row and row['size'] and row['cache_key']==key),'exists':bool(row and row['size']),'pending':pending,'period_sensitive':sensitive}

def reserve(store,actor,version,meta,current=None):
 from .assistant_insights import report_scope
 registry=st.session_state.setdefault('_stock_insight_lazy',{})
 old=registry.get(str(current or ''))
 if old and old['stamp']==meta['stamp'] and old['scope']==report_scope(store,actor):return current
 token='lazy_'+secrets.token_urlsafe(18)
 registry[token]={'scope':report_scope(store,actor),'version':version,'stamp':meta['stamp'],'period_sensitive':meta['period_sensitive']}
 while len(registry)>16:registry.pop(next(iter(registry)))
 return token

def adopt(alias,report):
 actual=report['report_id'];registry=st.session_state['_stock_dashboard_reports']
 if actual!=alias:
  registry[alias]=registry.pop(actual)
  custom=st.session_state.get('_stock_custom_reports',{})
  if actual in custom:custom[alias]=custom.pop(actual)
  previous=st.session_state.get('_stock_restored_insights')
  if previous and previous['report']['report_id']==actual:previous['report']['report_id']=alias
 report['report_id']=alias

def public_report(report):
 value=copy.deepcopy(report)
 for key in ('report_id','report_scope'):value.pop(key,None)
 for section in value.get('sections',[]):
  for item in section.get('charts',[])+section.get('kpis',[]):
   for field in ('evidence','comparison_evidence'):
    if field in item:
     for key in ('source_id','export_id','query'):item[field].pop(key,None)
 return value

def status(store,actor,event,version,filename):
 from grounded_ai import settings
 from .planning_assistant import knowledge
 from .assistant_insights import data_revision,report_scope
 from .monthly_kpi import current_month
 from . import insight_memory as memory
 key,model=settings();meta=metadata(store,actor,version,event.get('period_sensitive') is True)
 result={'configured':bool(key),'workbook_ready':version!='empty','model':model,'version':version,'filename':filename,'knowledge_revision':knowledge()['revision'],'planning_revision':str(data_revision(store,actor)),'report_scope':report_scope(store,actor),'calendar_month':current_month(),'active_analysis':None}
 if meta['current'] and not meta['pending'] and event.get('known_report_stamp')==meta['stamp']:
  return {**result,'report_stamp':meta['stamp'],'period_sensitive':meta['period_sensitive'],'report_not_modified':True,'report_binding':reserve(store,actor,version,meta,event.get('current_binding')),'export_allowed':store.identity(actor)['role']=='admin'}
 report=memory.restore(store,actor,version,display_only=True) if meta['exists'] else None
 active=memory.active_analysis(store,actor,version) if meta['pending'] else None
 meta=metadata(store,actor,version,temporal(report),check_pending=False)
 result.update(report_stamp=meta['stamp'],period_sensitive=meta['period_sensitive'],saved_report=report,active_analysis=active)
 if report and not active:
  binding=reserve(store,actor,version,meta,event.get('current_binding'));report['report_id']=binding;result.update(report_binding=binding,export_allowed=store.identity(actor)['role']=='admin')
  shown=public_report(report);stamps={str(s['view']):memory.digest(s) for s in shown['sections']};known=event.get('known_sections')
  result['section_stamps']=stamps
  if isinstance(known,dict) and known:
   result.update(report_patch=True,report_order=[s['view'] for s in shown['sections']])
   result['saved_report']={**report,'sections':[s for s in report['sections'] if known.get(str(s['view']))!=stamps[str(s['view'])]]}
 return result

def resolve(store,actor,event):
 """Translate opaque lazy references into this session's validated evidence."""
 from .assistant_insights import report_scope
 from . import insight_memory as memory
 from .insight_dashboard import validate_entry
 value=dict(event);descriptor=None;alias=str(value.get('report_id',''))
 for field in ('source_id','export_id'):
  raw=value.get(field)
  if isinstance(raw,str) and raw.startswith('lazy:'):
   pieces=raw.split(':')
   if len(pieces)!=6:raise ValueError('Choose a saved graph value.')
   _,alias,view,kind,item,period=pieces
   if kind not in ('charts','kpis') or period not in ('current','previous'):raise ValueError('Choose a saved graph value.')
   try:view=int(view)
   except ValueError:raise ValueError('Choose a report section.') from None
   descriptor=(field,view,kind,item,period)
 if not alias.startswith('lazy_'):return value
 binding=st.session_state.get('_stock_insight_lazy',{}).get(alias)
 if not binding or binding['scope']!=report_scope(store,actor):raise ValueError('This report display expired. Reopen Insights.')
 if value.get('version')!=binding['version']:raise ValueError('The workbook changed. Reopen Insights.')
 dashboard=st.session_state.get('_stock_dashboard_reports',{}).get(alias)
 if dashboard is None:
  meta=metadata(store,actor,binding['version'],binding['period_sensitive'])
  if not meta['current'] or meta['stamp']!=binding['stamp']:raise ValueError('Saved data or graphs changed. Reopen Insights.')
  report=memory.restore(store,actor,binding['version'])
  if report is None:raise ValueError('The saved report is unavailable. Reopen Insights.')
  adopt(alias,report);dashboard=st.session_state['_stock_dashboard_reports'][alias]
 validate_entry(store,actor,dashboard,binding['version'])
 if value.get('report_id'):value['report_id']=alias
 if descriptor:
  field,view,kind,item,period=descriptor
  section=next((s for s in dashboard['sections'] if s['view']==view),None)
  selected=next((x for x in section.get(kind,[]) if x.get('id')==item),None) if section else None
  evidence=selected.get('comparison_evidence' if period=='previous' else 'evidence') if selected else None
  token=evidence.get(field) if evidence else None
  if not token:raise ValueError('This saved value is unavailable for your access. Reopen Insights.')
  value[field]=token
 return value

def stamp_response(store,actor,event,result):
 from .insight_memory import digest as memory_digest
 if not isinstance(result,dict) or result.get('pending') is True:return result
 report=result.get('report') or (result if 'sections' in result else None)
 token=event.get('report_id');dashboard=st.session_state.get('_stock_dashboard_reports',{}).get(token)
 if report is None and dashboard:report={'sections':dashboard['sections']}
 if not report:return result
 version=report.get('version') or event.get('version')
 if not version:return result
 meta=metadata(store,actor,version,temporal(report),check_pending=False)
 result.update(report_stamp=meta['stamp'],period_sensitive=meta['period_sensitive'])
 if 'sections' in report:result['section_stamps']={str(s['view']):memory_digest(s) for s in public_report(report)['sections']}
 binding=st.session_state.get('_stock_insight_lazy',{}).get(token)
 if binding:binding.update(stamp=meta['stamp'],period_sensitive=meta['period_sensitive'])
 return result
