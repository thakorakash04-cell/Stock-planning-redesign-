"""Durable dashboards and graph definitions, shared only within identical access scopes.

No authentication state or browser-provided query is persisted here. Evidence tokens
are minted again for each authenticated Streamlit session when a snapshot is restored.
"""
import base64,copy,gzip,hashlib,json,secrets,time
import streamlit as st

REVISION=9
COMPACT_KPI_REVISION=2

def authorize(store,actor):
    from .access import require_menu
    require_menu(store,actor,8);store.require_permission(actor,'use_tools')
    return store.identity(actor)

def scope_key(store,actor):
    identity=authorize(store,actor)
    return digest([identity['role'],identity['permissions'],identity.get('allowedSegments')])

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def cache_key(store,actor,version):
    from .assistant_insights import data_revision
    from .planning_assistant import knowledge
    return digest([REVISION,version,workbook_stamp(store,actor),str(data_revision(store,actor)),knowledge()['revision']])

def schema(store,db):
    store.run(db,'''CREATE TABLE IF NOT EXISTS insight_memory (
        scope TEXT PRIMARY KEY,cache_key TEXT NOT NULL DEFAULT '',snapshot TEXT NOT NULL DEFAULT '',
        layout TEXT NOT NULL DEFAULT '{}',revision TEXT NOT NULL,updated_at DOUBLE PRECISION NOT NULL)''')

def pack(value):
    return base64.b64encode(gzip.compress(json.dumps(value,allow_nan=False,separators=(',',':')).encode(),mtime=0)).decode()

def unpack(value):return json.loads(gzip.decompress(base64.b64decode(value)))

def row(store,db,scope,lock=False):
    schema(store,db)
    # Ensure first-time competing writers lock the same row in PostgreSQL too.
    store.run(db,"INSERT INTO insight_memory(scope,revision,updated_at) VALUES(?,?,?) ON CONFLICT(scope) DO NOTHING",(scope,secrets.token_hex(12),time.time()))
    return store.run(db,'SELECT cache_key,snapshot,layout,revision FROM insight_memory WHERE scope=?'+(' FOR UPDATE' if lock and not store.sqlite else ''),(scope,)).fetchone()

def chart_id(view,chart,tables):
    query=copy.deepcopy(chart['evidence']['query'])
    table=next((t for t in tables if t['id']==query.pop('table',None)),None)
    query.pop('limit',None)
    identity=[view,table['name'] if table else chart['evidence']['table'],query,chart['label'],chart['value'],chart.get('x')]
    if chart.get('top_n') is not None:identity.append(chart['top_n'])
    return digest(identity)[:24]

def kpi_id(view,kpi,tables):
    query=copy.deepcopy(kpi.get('definition_query',kpi['evidence']['query']));table=next((t for t in tables if t['id']==query.pop('table',None)),None);query.pop('limit',None)
    identity=['kpi',view,table['name'] if table else kpi['evidence']['table'],query,kpi['field']]
    if kpi.get('comparison'):identity.append(kpi['comparison'])
    return digest(identity)[:24]

def kpi_spec(item):
    spec={'title':item['title'],'value':item['field'],'basis':item['basis'],'query':copy.deepcopy(item.get('definition_query',item['evidence']['query']))}
    if item.get('comparison'):spec['comparison']=copy.deepcopy(item['comparison'])
    return spec

def identify(section,tables):
    for chart in section.get('charts',[]):chart['id']=chart_id(section['view'],chart,tables)
    for card in section.get('kpis',[]):card['id']=kpi_id(section['view'],card,tables)

def restore_saved_sources(store,actor,report,dashboard,layout):
    """Keep explicitly saved connected views even when AI selects different comparisons."""
    from .insight_dashboard import facets
    for definition in layout.get('custom',[])+layout.get('custom_kpis',[]):
        recipe=definition.get('source_recipe')
        if not recipe:continue
        name=recipe.get('saved_name') or definition['table']+' · Saved';definition['table']=name
        table=next((t for t in dashboard['tables'] if t['name']==name),None)
        if table is None:
            try:
                plan=copy.deepcopy(recipe['plan'])
                for source in plan['sources']:
                    binding=next(b for b in recipe['sources'] if b['id']==source['table'])
                    matches=[t for t in dashboard['tables'] if t['name']==binding['name']]
                    if len(matches)!=1:raise ValueError('A saved comparison source is unavailable or ambiguous.')
                    source['table']=matches[0]['id']
                from .planning_assistant import run_tool
                evidence,_=run_tool(store,actor,{**plan,'operation':'insight_comparison'},store.get_dataset(actor),dashboard['tables'])
                detail=evidence[-1]['_table'];table={'id':'CONNECTED_SAVED_'+digest(name)[:12],'name':name,'headers':detail['headers'],'rows':detail['rows'],'saved_name':name,'refresh_plan':plan,'refresh_sources':[{'id':s['table'],'name':next(t['name'] for t in dashboard['tables'] if t['id']==s['table'])} for s in plan['sources']]}
                dashboard['tables'].append(table)
            except (ValueError,KeyError,StopIteration) as exc:
                report.setdefault('warnings',[]).append('Saved comparison unavailable: '+name+'. '+str(exc));continue
        matching=next((v for v in dashboard['views'].values() if v['table']==name),None)
        if matching is None:
            index=1000+int(digest(name)[:8],16)
            while index in dashboard['views'] and dashboard['views'][index]['table']!=name:index+=1
            matching={'view':index,'title':name,'table':name,'table_id':table['id']};dashboard['views'][index]=matching
        definition['view']=matching['view']
        if not any(s['view']==matching['view'] for s in report['sections']):report['sections'].append({'view':matching['view'],'title':name,'records':len(table['rows']),'limitation':'Saved comparison recalculated using its validated join definition.','facets':facets(table),'charts':[],'kpis':[]})

def apply_layout(store,actor,report,tables,views,layout=None):
    """Use only saved server-validated specifications, recalculating against current data."""
    from .insights import chart_result
    if layout is None:
        scope=scope_key(store,actor)
        with store.transaction() as db:
            store.require(db,actor);saved=row(store,db,scope);layout=json.loads(saved['layout'])
    from .insight_dashboard import kpi_result
    deleted=set(layout.get('deleted',[]));custom=layout.get('custom',[]);deleted_kpis=set(layout.get('deleted_kpis',[]))
    for section in report['sections']:
        identify(section,tables);section['charts']=[c for c in section['charts'] if c['id'] not in deleted]
        section['kpis']=[k for k in section.get('kpis',[]) if k['id'] not in deleted_kpis]
        view=next((v for v in views if v['view']==section['view']),None)
        table=next((t for t in tables if view and t['name']==view['table']),None)
        if not table:continue
        saved_cards=[d for d in layout.get('custom_kpis',[]) if d['view']==section['view'] and (not d.get('table') or d['table']==table['name'])]
        saved_charts=[d for d in custom if d['view']==section['view'] and (not d.get('table') or d['table']==table['name'])]
        section['kpis']=section['kpis'][:max(0,20-len(saved_cards))];section['charts']=section['charts'][:max(0,30-len(saved_charts))]
        for definition in layout.get('custom_kpis',[]):
            if definition['view']!=section['view']:continue
            if definition.get('table') and definition['table']!=table['name']:
                report.setdefault('warnings',[]).append('Saved KPI source changed: '+str(definition['spec'].get('title','KPI'))+'. Its definition is retained; choose its original source view.');continue
            spec=copy.deepcopy(definition['spec']);spec['query']['table']=table['id']
            try:
                card=kpi_result(tables,{**view,'table_id':table['id']},spec);card.update(custom=True,saved=True,request=definition.get('request',''));card['id']=kpi_id(section['view'],card,tables)
                if card['id'] in deleted_kpis:continue
                definition['id']=card['id']
                section['kpis']=[k for k in section['kpis'] if k['id']!=card['id']]
                if len(section['kpis'])<20:section['kpis'].append(card)
            except (ValueError,KeyError,StopIteration):
                report.setdefault('warnings',[]).append('Saved KPI unavailable in '+section['title']+': '+str(spec.get('title','KPI'))+'. Its definition is retained; check source columns.')
        for definition in custom:
            if definition['view']!=section['view']:continue
            if definition.get('table') and definition['table']!=table['name']:
                report.setdefault('warnings',[]).append('Saved graph source changed: '+str(definition['spec'].get('title','Graph'))+'. Its definition is retained; choose its original source view.');continue
            specification=copy.deepcopy(definition['spec']);specification['query']['table']=table['id']
            if 'top_n' not in specification:
                import re
                requested=re.search(r'\b(?:top|bottom|first|last|highest|lowest)\s+(\d{1,6})\b',definition.get('request',''),re.I)
                if requested:specification['top_n']=int(requested.group(1))
            try:
                chart=chart_result(tables,{**view,'table_id':table['id']},specification)
                chart.update(custom=True,saved=True,request=definition.get('request',''),finding=f"Saved graph recalculated from {chart['evidence']['matched_records']:,} matching records.",action='Review the current supporting records before changing a plan.')
                chart['id']=chart_id(section['view'],chart,tables)
                if chart['id'] in deleted:continue
                definition['id']=chart['id']
                # A generated equivalent becomes the saved custom definition.
                section['charts']=[c for c in section['charts'] if c['id']!=chart['id']]
                if len(section['charts'])<30:section['charts'].append(chart)
            except (ValueError,KeyError,StopIteration):
                warning='Saved graph unavailable in '+section['title']+': '+str(specification.get('title','Graph'))+'. Its definition is retained; check the current source columns.'
                if warning not in report.setdefault('warnings',[]):report['warnings'].append(warning)

def workbook_stamp(store,actor):
    with store.transaction() as db:
        store.require(db,actor);current=store.run(db,"SELECT version,filename,updated_at FROM datasets WHERE id='current'").fetchone()
    return [current['version'],current['filename'],current['updated_at']] if current else [None,None,None]

def snapshot(report,dashboard):
    result=copy.deepcopy({'report':report,'tables':dashboard['tables'],'views':list(dashboard['views'].values()),'context':dashboard.get('context',{})})
    # Tokens never transfer from one user's session to another user's session.
    for section in result['report']['sections']:
        for item in section.get('charts',[])+section.get('kpis',[]):
            item['evidence'].pop('source_id',None);item['evidence'].pop('export_id',None)
            if item.get('comparison_evidence'):item['comparison_evidence'].pop('source_id',None);item['comparison_evidence'].pop('export_id',None)
    return result

def save(store,actor,report,dashboard):
    from .insight_dashboard import validate_entry
    version=report['version'];validate_entry(store,actor,dashboard,version)
    if store.get_dataset(actor)['version']!=version:raise ValueError('The workbook changed. Start a new analysis.')
    scope=scope_key(store,actor);key=cache_key(store,actor,version)
    report.setdefault('cache_generation',report['report_id']);stamp=workbook_stamp(store,actor)
    with store.transaction() as db:
        store.require(db,actor);before=row(store,db,scope);layout=json.loads(before['layout'])
    restore_saved_sources(store,actor,report,dashboard,layout)
    if cache_key(store,actor,version)!=key:raise ValueError('Business data changed while restoring saved comparisons. Retry analysis.')
    # Source replay can change view numbers; use it only if the saved layout has not changed.
    with store.transaction() as db:
        store.require(db,actor);saved=row(store,db,scope,True)
        if saved['revision']!=before['revision']:raise ValueError('The saved layout changed while preparing the report. Retry saving analysis.')
        apply_layout(store,actor,report,dashboard['tables'],list(dashboard['views'].values()),layout)
        value=snapshot(report,dashboard);value['workbook_stamp']=stamp;layout['_generation']=report['cache_generation']
        store.run(db,'UPDATE insight_memory SET cache_key=?,snapshot=?,layout=?,revision=?,updated_at=? WHERE scope=?',(key,pack(value),json.dumps(layout,allow_nan=False),secrets.token_hex(12),time.time(),scope))
        from .insight_kpi_edits import publish
        publish(store,db,scope,key,value['report'],value['tables'])
    from .insight_dashboard import register
    for section in report['sections']:
        register(store,actor,{kind:[item for item in section.get(kind,[]) if not item['evidence'].get('source_id')] for kind in ('charts','kpis')},dashboard['tables'],version)
    dashboard['sections']=copy.deepcopy(report['sections']);dashboard['cache_generation']=report['cache_generation']
    return report

def restore(store,actor,version,display_only=False):
    scope=scope_key(store,actor);key=cache_key(store,actor,version)
    from .transfer_cache import read_rows
    with store.transaction() as db:
        store.require(db,actor);schema(store,db)
        rows=read_rows(store,db,'SELECT snapshot,layout,revision,cache_key FROM insight_memory WHERE scope=? AND snapshot<>?',(scope,''))
    if not rows:return None
    from .monthly_kpi import needs_refresh
    previous_cached=st.session_state.get('_stock_restored_insights')
    reference=previous_cached['report'] if previous_cached and previous_cached['marker']==(scope,key,rows[0]['revision']) else unpack(rows[0]['snapshot'])['report']
    if rows[0]['cache_key']!=key or needs_refresh(reference):
        value=unpack(rows[0]['snapshot']);overlay_layout(value['report'],json.loads(rows[0]['layout']))
        from .planning_assistant import knowledge
        from .insight_refresh import recalculate
        value=recalculate(store,actor,value,force=value['report'].get('knowledge_revision')!=knowledge()['revision'])
        value['report']['version']=version
        if cache_key(store,actor,version)!=key:raise ValueError('Business data changed during automatic update. Retry opening Insights.')
        value['workbook_stamp']=workbook_stamp(store,actor)
        from .assistant_insights import data_revision
        value['report']['planning_revision']=str(data_revision(store,actor));value['report']['knowledge_revision']=knowledge()['revision']
        new_revision=secrets.token_hex(12)
        if scope_key(store,actor)!=scope:raise ValueError('Your access changed during automatic update.')
        with store.transaction() as db:
            store.require(db,actor);latest=row(store,db,scope,True)
            if latest['revision']!=rows[0]['revision']:raise ValueError('The saved dashboard changed during automatic update. Retry opening Insights.')
            store.run(db,'UPDATE insight_memory SET cache_key=?,snapshot=?,revision=?,updated_at=? WHERE scope=?',(key,pack(value),new_revision,time.time(),scope))
            from .insight_kpi_edits import publish
            publish(store,db,scope,key,value['report'],value['tables'])
        rows=[{'snapshot':pack(value),'layout':rows[0]['layout'],'revision':new_revision,'cache_key':key}]
    marker=(scope,key,rows[0]['revision']);previous=st.session_state.get('_stock_restored_insights')
    if previous and previous['marker']==marker and previous['report']['report_id'] in st.session_state.get('_stock_dashboard_reports',{}):
        return copy.deepcopy(previous['report'])
    saved=unpack(rows[0]['snapshot']);report=overlay_layout(saved['report'],json.loads(rows[0]['layout']));tables=saved['tables']
    from .assistant_insights import report_scope,data_revision
    from .planning_assistant import knowledge
    from .insight_dashboard import register
    token=secrets.token_urlsafe(18)
    report.update(report_id=token,report_scope=report_scope(store,actor),planning_revision=str(data_revision(store,actor)),knowledge_revision=knowledge()['revision'],cached=True)
    if display_only:
        if cache_key(store,actor,version)!=key:raise ValueError('Business data changed. Reload Insights.')
        authorize(store,actor)
        return report
    for section in report['sections']:register(store,actor,section,tables,version)
    dashboard={'version':version,'scope':report['report_scope'],'planning_revision':report['planning_revision'],'knowledge_revision':report['knowledge_revision'],
               'tables':tables,'views':{v['view']:v for v in saved['views']},'context':saved['context'],'sections':copy.deepcopy(report['sections']),
               'cache_generation':report['cache_generation']}
    st.session_state.setdefault('_stock_dashboard_reports',{})[token]=dashboard
    st.session_state.setdefault('_stock_custom_reports',{})[token]={**{k:dashboard[k] for k in ('version','scope','planning_revision','knowledge_revision')},
          'charts':{s['view']:[{'title':c['title'],'query':c['evidence']['query'],'top_n':c.get('top_n')} for c in s['charts']] for s in report['sections']}}
    # Retain a bounded number of active reports, just like generation.
    for name,limit in (('_stock_dashboard_reports',2),('_stock_custom_reports',5)):
        registry=st.session_state[name]
        while len(registry)>limit:registry.pop(next(iter(registry)))
    if cache_key(store,actor,version)!=key:raise ValueError('Business data changed. Reload Insights.')
    authorize(store,actor)
    st.session_state['_stock_restored_insights']={'marker':marker,'report':copy.deepcopy(report)}
    return report

def overlay_layout(report,layout):
    """Apply committed layout-only changes without re-running any calculation."""
    deleted=set(layout.get('deleted',[]));deleted_kpis=set(layout.get('deleted_kpis',[]))
    for section in report['sections']:
        section['charts']=[c for c in section.get('charts',[]) if c.get('id') not in deleted]
        section['kpis']=[k for k in section.get('kpis',[]) if k.get('id') not in deleted_kpis]
        for kind,collection in (('charts','custom'),('kpis','custom_kpis')):
            definitions={d['id']:d for d in layout.get(collection,[]) if d['view']==section['view']}
            for item in section.get(kind,[]):
                definition=definitions.get(item.get('id'))
                if definition:
                    item['saved']=True
                    if kind=='charts':item['type']=definition['spec'].get('type',item.get('type','bar'))
    return report

def graph_style(selected,style):
    """Validate display style using rows, or trusted server catalogue capabilities."""
    if '_edit_styles' in selected:
        if not isinstance(style,str) or style not in selected['_edit_styles']:raise ValueError('Choose a supported graph style.')
        return selected['_edit_styles'][style]
    if style not in ('bar','column','lollipop','donut','line','area','scatter'):raise ValueError('Choose a supported graph style.')
    records=selected['evidence']['records'];value=selected['value']
    if style=='scatter' and (not selected.get('x') or not any(r.get(selected['x']) is not None and r.get(value) is not None for r in records)):raise ValueError('Scatter plot requires two numeric fields.')
    if style=='donut' and (len(records)>30 or not value.startswith(('count(','distinct_count(')) or any(r.get(value) is None or r[value]<0 for r in records)):style='bar'
    if style in ('line','area'):
        import re
        from datetime import datetime
        try:
            if not records:raise ValueError('No dated values')
            for record in records:
                label=str(record.get(selected['label'],''))
                if selected['evidence']['query'].get('date_group'):
                    from .calendar_group import month_key
                    if month_key(label)>=10**9:raise ValueError('Unknown month')
                    continue
                if not re.match(r'^\d{4}-\d{2}(?:-\d{2})?(?:T.*)?$',label):raise ValueError('Not an ISO date')
                datetime.fromisoformat(label+'-01' if len(label)==7 else label)
        except ValueError:style='column'
    return style

def fast_edit(store,actor,event,version):
    """Commit a small layout change; keep the report token, values and evidence intact."""
    from .insight_dashboard import validate_entry
    token=str(event.get('report_id',''));index=event.get('view')
    dashboard=st.session_state.get('_stock_dashboard_reports',{}).get(token)
    if not dashboard:raise ValueError('This report expired. Reload Insights.')
    validate_entry(store,actor,dashboard,version)
    if event.get('version')!=version:raise ValueError('The workbook changed. Reload Insights.')
    scope=scope_key(store,actor);key=cache_key(store,actor,version)
    section=next((s for s in dashboard['sections'] if s['view']==index),None)
    if section is None:raise ValueError('Choose a current report section.')
    kind='kpis' if event.get('item_kind')=='kpi' else 'charts';item_id=event.get('kpi_id') if kind=='kpis' else event.get('chart_id')
    selected=next((item for item in section.get(kind,[]) if item.get('id')==item_id),None)
    saving=event.get('action')=='save_insight_item';style=None
    if selected is None and saving:raise ValueError('This item changed or was deleted. Reload Insights.')
    if saving and selected.get('refresh_error'):raise ValueError('Resolve the unavailable source before saving this item.')
    if saving and kind=='charts':
        style=graph_style(selected,event.get('chart_type',selected.get('type','bar')))
    new_revision=secrets.token_hex(12)
    with store.transaction() as db:
        store.require(db,actor,permission='use_tools')
        schema(store,db)
        saved=store.run(db,'SELECT cache_key,layout,revision FROM insight_memory WHERE scope=?'+(' FOR UPDATE' if not store.sqlite else ''),(scope,)).fetchone()
        if not saved or saved['cache_key']!=key:raise ValueError('The saved report changed. Reload Insights.')
        layout=json.loads(saved['layout']);generation=layout.get('_generation')
        if generation is None:
            legacy=store.run(db,'SELECT snapshot FROM insight_memory WHERE scope=?',(scope,)).fetchone()
            generation=unpack(legacy['snapshot'])['report']['cache_generation'];layout['_generation']=generation
        if generation!=dashboard.get('cache_generation',token):raise ValueError('Another user regenerated this report. Reload Insights before editing graphs.')
        collection='custom_kpis' if kind=='kpis' else 'custom';deleted_key='deleted_kpis' if kind=='kpis' else 'deleted'
        deleted=set(layout.get(deleted_key,[]))
        if saving:
            if item_id in deleted:raise ValueError('This item was deleted in another session. Reload Insights.')
            definitions=[d for d in layout.get(collection,[]) if d['id']!=item_id]
            if len(definitions)>=100 or sum(d['view']==index for d in definitions)>=(20 if kind=='kpis' else 30):raise ValueError('This view has reached its saved item limit.')
            if kind=='charts':
                spec={field:copy.deepcopy(selected[field]) for field in ('title','type','label','value','x','top_n') if field in selected};spec['type']=style
            else:spec=kpi_spec(selected)
            if kind=='charts':spec['query']=copy.deepcopy(selected['evidence']['query'])
            definition={'id':item_id,'view':index,'table':selected['evidence']['table'],'request':selected.get('request',''),'saved':True,'spec':spec}
            source=next(t for t in dashboard['tables'] if t['id']==spec['query']['table'])
            if source.get('refresh_plan') and source.get('refresh_sources'):definition['source_recipe']={'plan':copy.deepcopy(source['refresh_plan']),'sources':copy.deepcopy(source['refresh_sources']),'saved_name':source.get('saved_name') or source['name']+' · Saved'}
            layout[collection]=definitions+[definition]
        else:
            if selected is None and item_id not in deleted:raise ValueError('Choose a current graph or KPI.')
            deleted.add(item_id)
            if len(deleted)>1000:raise ValueError('The saved dashboard has reached its removed item limit.')
            layout[deleted_key]=sorted(deleted);layout[collection]=[d for d in layout.get(collection,[]) if d['id']!=item_id]
        store.run(db,'UPDATE insight_memory SET layout=?,revision=?,updated_at=? WHERE scope=?',(json.dumps(layout,allow_nan=False),new_revision,time.time(),scope))
        store._log(db,actor.username,'tool_use',('Save' if saving else 'Delete')+' Insight '+('KPI' if kind=='kpis' else 'graph'),session_id=actor.session_id)
    # Only acknowledge after the durable transaction commits. No report rehydration.
    for active_token,active in st.session_state.get('_stock_dashboard_reports',{}).items():
        if active.get('cache_generation')==generation and active.get('scope')==dashboard.get('scope'):
            overlay_layout({'sections':active['sections']},layout)
            custom=st.session_state.get('_stock_custom_reports',{}).get(active_token)
            if custom is not None:custom['charts']={s['view']:[{'title':c['title'],'query':c['evidence']['query'],'top_n':c.get('top_n')} for c in s['charts']] for s in active['sections']}
    cached=st.session_state.get('_stock_restored_insights')
    if cached and cached['marker'][0]==scope and cached['report'].get('cache_generation')==generation:
        overlay_layout(cached['report'],layout);cached['marker']=(scope,key,new_revision)
    return {'report_id':token,'view':index,'item_id':item_id,'item_kind':'kpi' if kind=='kpis' else 'chart','saved':saving,'deleted':not saving,'chart_type':style,'layout_revision':new_revision}

def edit(store,actor,event,version,chart=None,kpi=None):
    """Atomically update a saved layout and its current snapshot. Never accept client queries."""
    from .insight_dashboard import validate_entry
    token=str(event.get('report_id',''));index=event.get('view')
    dashboard=st.session_state.get('_stock_dashboard_reports',{}).get(token)
    if not dashboard:raise ValueError('This report expired. Reload Insights.')
    validate_entry(store,actor,dashboard,version)
    if event.get('version')!=version:raise ValueError('The workbook changed. Reload Insights.')
    scope=scope_key(store,actor);key=cache_key(store,actor,version)
    with store.transaction() as db:
        store.require(db,actor);saved=row(store,db,scope,True)
        if saved['cache_key']!=key or not saved['snapshot']:raise ValueError('The saved report changed. Reload Insights.')
        value=unpack(saved['snapshot']);layout=json.loads(saved['layout']);report=overlay_layout(value['report'],layout)
        if dashboard.get('cache_generation',token)!=report['cache_generation']:raise ValueError('Another user regenerated this report. Reload Insights before editing graphs.')
        section=next((s for s in report['sections'] if s['view']==index),None)
        if section is None:raise ValueError('Choose a current report section.')
        if event.get('action')=='save_insight_item':
            kind='kpis' if event.get('item_kind')=='kpi' else 'charts'
            item_id=event.get('kpi_id') if kind=='kpis' else event.get('chart_id')
            selected=next((item for item in section.get(kind,[]) if item.get('id')==item_id),None)
            if selected is None:raise ValueError('This item changed or was deleted. Reload Insights.')
            if selected.get('refresh_error'):raise ValueError('Resolve the unavailable source before saving this item.')
            selected['saved']=True
            if kind=='charts':
                style=event.get('chart_type',selected.get('type','bar'))
                if style not in ('bar','column','lollipop','donut','line','area','scatter'):raise ValueError('Choose a supported graph style.')
                from .insights import chart_result
                selected.update(chart_result(dashboard['tables'],{**dashboard['views'][index],'table_id':selected['evidence']['query']['table']},{**selected,'type':style,'query':selected['evidence']['query']}))
                definition={'id':item_id,'view':index,'table':selected['evidence']['table'],'request':selected.get('request',''),'spec':{key:copy.deepcopy(selected[key]) for key in ('title','type','label','value','x','top_n') if key in selected}}
                definition['spec']['query']=copy.deepcopy(selected['evidence']['query']);collection='custom'
            else:
                definition={'id':item_id,'view':index,'table':selected['evidence']['table'],'request':selected.get('request',''),'spec':kpi_spec(selected)};collection='custom_kpis'
            definitions=[d for d in layout.get(collection,[]) if d['id']!=item_id]
            if len(definitions)>=100:raise ValueError('The saved dashboard has reached its saved item limit.')
            if sum(d.get('view')==index for d in definitions)>=(20 if kind=='kpis' else 30):raise ValueError('This view has reached its saved item limit.')
            source=next(t for t in dashboard['tables'] if t['id']==selected['evidence']['query']['table'])
            if source.get('refresh_plan') and source.get('refresh_sources'):definition['source_recipe']={'plan':copy.deepcopy(source['refresh_plan']),'sources':copy.deepcopy(source['refresh_sources']),'saved_name':source.get('saved_name') or source['name']+' · Saved'}
            definition['saved']=True;layout[collection]=definitions+[definition]
        elif kpi is not None:
            kpi=copy.deepcopy(kpi);kpi['id']=kpi_id(index,kpi,dashboard['tables']);kpi['custom']=True;kpi['saved']=True
            if any(k.get('id')==kpi['id'] for k in section.get('kpis',[])):raise ValueError('This KPI is already in the view. Choose another measure or filter.')
            if len(section.get('kpis',[]))>=20:raise ValueError('This view has reached its 20 KPI card limit.')
            customs=layout.get('custom_kpis',[])
            if len(customs)>=100:raise ValueError('This report has reached its 100 saved custom KPI limit.')
            definition={'id':kpi['id'],'table':kpi['evidence']['table'],'view':index,'request':event.get('question',''),'spec':kpi_spec(kpi)}
            layout['custom_kpis']=customs+[definition];layout['deleted_kpis']=[key for key in layout.get('deleted_kpis',[]) if key!=kpi['id']]
            section.setdefault('kpis',[]).append(kpi)
        elif chart is not None:
            chart=copy.deepcopy(chart);chart['saved']=True;chart['id']=chart_id(index,chart,dashboard['tables'])
            if not any(c.get('id')==chart['id'] for c in section['charts']) and (len(section['charts'])>=30 or sum(len(s['charts']) for s in report['sections'])>=100):raise ValueError('This report has reached its graph limit.')
            definition={'view':index,'table':chart['evidence']['table'],'request':event.get('question',''),'spec':{k:chart[k] for k in ('title','type','label','value','x','top_n') if k in chart}}
            definition['spec']['query']=copy.deepcopy(chart['evidence']['query'])
            definition['id']=chart['id']
            customs=[d for d in layout.get('custom',[]) if d['id']!=chart['id']]
            if len(customs)>=100:raise ValueError('The saved dashboard has reached its 100 custom graph limit.')
            layout['custom']=customs+[definition]
            layout['deleted']=[d for d in layout.get('deleted',[]) if d!=chart['id']]
            section['charts']=[c for c in section['charts'] if c.get('id')!=chart['id']]+[chart]
        elif event.get('item_kind')=='kpi':
            selected=next((k for k in section.get('kpis',[]) if k.get('id')==event.get('kpi_id')),None)
            if selected is None:raise ValueError('This KPI changed or was already deleted. Reload Insights.')
            removed=selected['id'];deleted=set(layout.get('deleted_kpis',[]));deleted.add(removed)
            if len(deleted)>1000:raise ValueError('The saved dashboard has reached its removed KPI limit.')
            layout['deleted_kpis']=sorted(deleted);layout['custom_kpis']=[k for k in layout.get('custom_kpis',[]) if k['id']!=removed]
            section['kpis']=[k for k in section.get('kpis',[]) if k.get('id')!=removed]
        else:
            selected=next((c for c in section['charts'] if c.get('id')==event.get('chart_id')),None)
            if selected is None:raise ValueError('This graph changed or was already deleted. Reload Insights.')
            graph=selected['id'];deleted=set(layout.get('deleted',[]));deleted.add(graph)
            if len(deleted)>1000:raise ValueError('The saved dashboard has reached its removed graph limit.')
            layout['deleted']=sorted(deleted);layout['custom']=[d for d in layout.get('custom',[]) if d['id']!=graph]
            section['charts']=[c for c in section['charts'] if c.get('id')!=graph]
        source=next((t for t in dashboard['tables'] if t['name']==dashboard['views'][index]['table']),None)
        if source and source.get('refresh_plan') and source.get('refresh_sources'):
            for definition in layout.get('custom',[])+layout.get('custom_kpis',[]):
                if definition['view']==index and definition.get('table')==source['name']:definition['source_recipe']={'plan':copy.deepcopy(source['refresh_plan']),'sources':copy.deepcopy(source['refresh_sources']),'saved_name':source.get('saved_name') or source['name']+' · Saved'}
        store.require(db,actor,permission='use_tools')
        store.run(db,'UPDATE insight_memory SET snapshot=?,layout=?,revision=?,updated_at=? WHERE scope=?',(pack(value),json.dumps(layout,allow_nan=False),secrets.token_hex(12),time.time(),scope))
        from .insight_kpi_edits import publish
        publish(store,db,scope,key,value['report'],value['tables'])
    # Rehydrate fresh evidence tokens and canonical templates, including all edits.
    st.session_state.pop('_stock_restored_insights',None)
    restored=restore(store,actor,version)
    store.log_event(actor,'tool_use',('Save Insight item' if event.get('action')=='save_insight_item' else ('Save Insight KPI' if kpi is not None else 'Save Insight graph') if chart is not None or kpi is not None else ('Delete Insight KPI' if event.get('item_kind')=='kpi' else 'Delete Insight graph')))
    return {'report':restored,'deleted':event.get('action')!='save_insight_item' and chart is None and kpi is None}


def checkpoint_schema(store,db):
    store.run(db,'''CREATE TABLE IF NOT EXISTS insight_checkpoints (
        scope TEXT PRIMARY KEY,cache_key TEXT NOT NULL,run_id TEXT NOT NULL,
        payload TEXT NOT NULL,updated_at DOUBLE PRECISION NOT NULL)''')


def checkpoint(store,actor,job,next_step):
    """Save every delivered section and continuation before acknowledging a step."""
    if not job['report']['sections']:return
    from .insight_jobs import validate
    validate(store,actor,job,job['version'])
    scope=scope_key(store,actor);key=cache_key(store,actor,job['version'])
    saved=copy.deepcopy({k:job[k] for k in ('id','request_id','version','planning_revision','knowledge_revision','tables','views','context','report','phase','batch','briefs')})
    saved['step']=next_step
    for section in saved['report']['sections']:
        for item in section.get('charts',[])+section.get('kpis',[]):
            item['evidence'].pop('source_id',None);item['evidence'].pop('export_id',None)
            if item.get('comparison_evidence'):item['comparison_evidence'].pop('source_id',None);item['comparison_evidence'].pop('export_id',None)
    with store.transaction() as db:
        store.require(db,actor);checkpoint_schema(store,db)
        store.run(db,'''INSERT INTO insight_checkpoints(scope,cache_key,run_id,payload,updated_at) VALUES(?,?,?,?,?)
            ON CONFLICT(scope) DO UPDATE SET cache_key=excluded.cache_key,run_id=excluded.run_id,payload=excluded.payload,updated_at=excluded.updated_at''',
            (scope,key,job['id'],pack(saved),time.time()))


def clear_checkpoint(store,actor,job):
    scope=scope_key(store,actor)
    with store.transaction() as db:
        store.require(db,actor);checkpoint_schema(store,db)
        store.run(db,'DELETE FROM insight_checkpoints WHERE scope=? AND run_id=?',(scope,job['id']))


def active_analysis(store,actor,version):
    """Recover interrupted work with fresh actor-bound evidence, without calling AI."""
    from .assistant_insights import report_scope
    from .insight_jobs import validate,response,publish,BATCH_SIZE
    from .insight_dashboard import register
    from .transfer_cache import read_rows
    from .store import AccessDenied
    scope=scope_key(store,actor);key=cache_key(store,actor,version)
    jobs=st.session_state.setdefault('_stock_insight_jobs',{})
    for job in reversed(list(jobs.values())):
        if job['scope']!=report_scope(store,actor) or not job['report']['sections'] or job.get('persisted'):continue
        try:validate(store,actor,job,version)
        except (ValueError,AccessDenied):continue
        publish(job)
        result={**response(job),'request_id':job['request_id']}
        if job['phase']=='done':result.update(pending=True,progress={**result['progress'],'label':'Saving completed analysis'})
        return result
    with store.transaction() as db:
        store.require(db,actor);checkpoint_schema(store,db)
        rows=read_rows(store,db,'SELECT payload FROM insight_checkpoints WHERE scope=? AND cache_key=?',(scope,key))
    if not rows:return None
    job=unpack(rows[0]['payload']);job['scope']=report_scope(store,actor)
    job['report'].update(report_id=secrets.token_urlsafe(18),report_scope=job['scope'])
    validate(store,actor,job,version)
    for section in job['report']['sections']:register(store,actor,section,job['tables'],version)
    if job['phase']=='review':
        ids={v['view'] for v in job['views'][job['batch']*BATCH_SIZE:(job['batch']+1)*BATCH_SIZE]}
        job['current_sections']=[s for s in job['report']['sections'] if s['view'] in ids]
    jobs[job['id']]=job
    while len(jobs)>2:jobs.pop(next(iter(jobs)))
    publish(job)
    return {**response(job),'request_id':job['request_id']}

