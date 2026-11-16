"""Template selection and common filters over existing authorized report views."""
import copy,json,secrets,time
REVISION=1
PROFILES={'current':None,'executive':None,'stock':{0,1,4,5,6,9},'production':{3,10,11,12,23},'sales':{2,20,21,22},'custom':None}

def configuration(value):
 value=value or {}
 if not isinstance(value,dict) or not isinstance(value.get('template','current'),str) or value.get('template','current') not in PROFILES:raise ValueError('Choose a dashboard template.')
 question=value.get('question','');views=value.get('views',[])
 if not isinstance(question,str) or len(question)>2000:raise ValueError('Describe the dashboard in at most 2000 characters.')
 if not isinstance(views,list) or len(views)>50 or any(type(v)!=int for v in views):raise ValueError('Choose valid dashboard source views.')
 return {'template':value.get('template','current'),'question':question.strip(),'views':list(dict.fromkeys(views))}

def select_views(views,config):
 config=configuration(config);ids=PROFILES[config['template']]
 if config['template']=='custom' and config['views']:ids=set(config['views'])
 return [v for v in views if ids is None or v['view'] in ids]

def _dashboard(store,actor,event,version):
 import streamlit as st
 from .insight_dashboard import validate_entry
 from .access import require_menu
 require_menu(store,actor,8);store.require_permission(actor,'use_tools')
 saved=st.session_state.get('_stock_dashboard_reports',{}).get(str(event.get('report_id','')))
 if not saved:raise ValueError('Reload the saved report before editing this dashboard.')
 validate_entry(store,actor,saved,version)
 if event.get('version')!=version:raise ValueError('The workbook changed. Reload the report.')
 return saved

def common_filters(store,actor,event,version):
 from .insight_dashboard import refresh,filter_table,validate_entry
 saved=_dashboard(store,actor,event,version);ids=event.get('views',[]);filters=event.get('filters',[]);previous=event.get('previous_filters',[])
 if not isinstance(ids,list) or not ids or len(ids)>50 or any(type(i)!=int for i in ids) or len(set(ids))!=len(ids):raise ValueError('Choose dashboard views.')
 if not isinstance(filters,list) or len(filters)>16 or not isinstance(previous,list) or len(previous)>16:raise ValueError('Choose valid common filters.')
 sections={s['view']:s for s in saved['sections']}
 if any(i not in sections for i in ids):raise ValueError('A selected report view is unavailable.')
 canon=lambda f:json.dumps(f,sort_keys=True,default=str)
 old={canon(f) for f in previous};requests=[];skipped=[]
 for index in ids:
  section=sections[index];view=saved['views'][index];table=next(t for t in saved['tables'] if t['name']==view['table'])
  local=[f for f in section.get('filters',[]) if canon(f) not in old]
  compatible=all(isinstance(f,dict) and f.get('column') in table['headers'] for f in filters)
  if not compatible:skipped.append({'view':index,'title':section['title']})
  chosen=local+filters if compatible else local
  filter_table(table,chosen) # Validate every section before changing any active view.
  requests.append((index,chosen))
 before_tables=saved.get('active_tables');before_filters=saved.get('active_filters');before_sections=saved['sections']
 saved['active_tables']=dict(before_tables or {});saved['active_filters']=dict(before_filters or {})
 try:
  changed=[refresh(store,actor,{**event,'view':index,'filters':chosen},version)['section'] for index,chosen in requests]
  validate_entry(store,actor,saved,version)
 except Exception:
  saved['active_tables']=before_tables or {};saved['active_filters']=before_filters or {};saved['sections']=before_sections;raise
 replacements={s['view']:s for s in changed};saved['sections']=[replacements.get(s['view'],s) for s in saved['sections']]
 return {'report_id':event['report_id'],'sections':changed,'skipped':skipped}

def save_dashboard(store,actor,event,version):
 from . import insight_memory as memory
 from .insight_dashboard import validate_entry
 saved=_dashboard(store,actor,event,version);config=configuration(event.get('dashboard'))
 scope=memory.scope_key(store,actor);key=memory.cache_key(store,actor,version)
 with store.transaction() as db:
  store.require(db,actor);current=memory.row(store,db,scope,True)
  if current['cache_key']!=key or not current['snapshot']:raise ValueError('Saved sources changed. Reload Insights.')
  value=memory.unpack(current['snapshot']);report=value['report']
  if saved.get('cache_generation')!=report.get('cache_generation'):raise ValueError('The report changed in another session. Reload Insights.')
  report['sections']=copy.deepcopy(saved['sections']);report['dashboard']=config
  if any(s.get('filters') for s in report['sections']):report.update(overview='Saved filtered dashboard. KPI cards and graphs use the displayed source conditions; the original full-snapshot AI brief is hidden.',answer='',attention=[])
  value=memory.snapshot(report,{**saved,'views':saved['views']});value['workbook_stamp']=memory.workbook_stamp(store,actor)
  validate_entry(store,actor,saved,version)
  store.run(db,'UPDATE insight_memory SET snapshot=?,revision=?,updated_at=? WHERE scope=?',(memory.pack(value),secrets.token_hex(12),time.time(),scope))
  from .insight_kpi_edits import publish
  publish(store,db,scope,key,value['report'],value['tables'])
 return {'report_id':event['report_id'],'saved':True,'report_meta':{k:report[k] for k in ('overview','answer','attention','dashboard') if k in report}} 
