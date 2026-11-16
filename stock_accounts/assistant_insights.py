"""Authenticated Ask AI bridge; all context is checked against the current workbook."""
import base64,hashlib,io,secrets
import pandas as pd
import streamlit as st
from grounded_ai import ask,tables_from_frames,json_text,execute_query
from .store import AccessDenied
from workbook import forecast_summary

STOCK_TABLES_REVISION=1

def stock_tables(store,actor):
    from .workspace_insights import workspace_payload
    data,model_tables,version=workspace_payload(store,actor)
    from .planning_assistant import knowledge
    cache_key=(STOCK_TABLES_REVISION,version,str(data.get('planningRevision')),knowledge()['revision'],str(store.identity(actor)['permissions']))
    cached=st.session_state.get('_stock_ai_tables')
    if not cached or cached[0]!=cache_key:
        frames=[('worksheet',s['name'],pd.DataFrame(s['rows'],columns=s['headers'])) for s in data['sheets']]
        if len(data['sheets'])>4:
            sheet=data['sheets'][4]
            if sheet['rows'] and len(sheet['headers'])>=7:
                frames.append(('derived:forecast-product-totals',sheet['name']+' — product totals',forecast_summary(pd.DataFrame(sheet['rows'],columns=sheet['headers']))))
        frames.extend(('model',t['name'],pd.DataFrame(t['rows'],columns=t['headers'])) for t in model_tables)
        tables=[]
        for kind,name,frame in frames:
            for table in tables_from_frames([(name,frame)]):
                table.update(id='T'+str(len(tables)+1),source_kind=kind,source_key=hashlib.sha256(json_text([kind,name]).encode()).hexdigest())
                tables.append(table)
        cached=(cache_key,tables);st.session_state['_stock_ai_tables']=cached
    return cached[1],version,data['filename']

def export_evidence(store,actor,event,tables,version):
    if store.identity(actor)['role']!='admin':raise AccessDenied('Only administrators can download Ask AI tables.')
    store.require_permission(actor,'download')
    entry=st.session_state.get('_stock_ai_exports',{}).get(str(event.get('export_id','')))
    if not entry:raise ValueError('This download has expired. Ask the question again to generate a new table.')
    if entry.get('scope') is not None and entry['scope']!=report_scope(store,actor):raise AccessDenied('Your access changed. Ask the question again.')
    if entry['version']!=version or event.get('version')!=version:raise ValueError('The workbook changed. Ask the question again before downloading.')
    if 'table' in entry:
        from .matched_export import export_table
        current=store.get_dataset(actor)
        table=entry['table'];projection={**event,'headers':event.get('headers',table['headers']),'rows':event.get('rows',table['rows'])}
        return export_table(store,actor,projection,current,table,'Planning assistant results','Planning_assistant_result.xlsx')
    from .insight_dashboard import validate_entry,mark_table
    validate_entry(store,actor,entry,version)
    if entry.get('source_table'):
        selected_table,_=mark_table(entry,event)
        tables=[t for t in tables if t['id']!=selected_table['id']]+[selected_table]
    query=entry['query'];table=next((t for t in tables if t['id']==query['table']),None)
    if table is None:raise ValueError('The source table is no longer available. Ask the question again.')
    result=execute_query(tables,query,all_rows=True)
    raw_query={'table':query['table'],'filters':query.get('filters',[]),'limit':20}
    if query.get('date_group'):raw_query['date_group']=query['date_group']
    if query.get('sort_by') in table['headers']:
        raw_query.update(sort_by=query['sort_by'],descending=query.get('descending',True))
    matching=execute_query(tables,raw_query,all_rows=True)
    cells=sum(sum(len(r) for r in rows) for rows in (result['records'],matching['records']))
    if cells>2_000_000:raise ValueError('This export is too large. Narrow the question filters and download the smaller matching table.')
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    workbook=Workbook(write_only=True)
    def write_sheet(name,records,selected_headers=None):
        sheet=workbook.create_sheet(name)
        headers=selected_headers if selected_headers is not None else list(records[0]) if records else []
        def cell(value):
            if isinstance(value,str):
                if len(value)>32767:raise ValueError('A text field exceeds Excel’s cell limit. Narrow the exported columns or filters.')
                item=WriteOnlyCell(sheet,value=value);item.data_type='s';return item
            return value
        sheet.append([cell(h) for h in headers])
        for record in records:sheet.append([cell(record.get(h)) for h in headers])
    from .ai_table_view import project
    displayed=project(result['records'],event)
    write_sheet('Result table',displayed,event.get('headers'))
    if 'headers' not in event:write_sheet('Matching records',matching['records'])
    write_sheet('Query details',[{'Source table':table['name'],'Matched records':matching['matched_records'],'Result rows':result['result_rows'],'Workbook version':version,'Query':json_text(query)}])
    output=io.BytesIO();workbook.save(output)
    if output.tell()>25_000_000:raise ValueError('The Excel export exceeds 25 MB. Narrow your question filters.')
    if store.identity(actor)['role']!='admin':raise AccessDenied('Administrator access is no longer active.')
    store.require_permission(actor,'download')
    validate_entry(store,actor,entry,version)
    store.log_event(actor,'export','Ask AI matching records')
    return {'content':base64.b64encode(output.getvalue()).decode(),'filename':'Ask_AI_matching_records.xlsx','mime':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','matched_records':matching['matched_records']}

def insight_records(store,actor,event,tables,version):
    entry=st.session_state.get('_stock_insight_sources',{}).get(str(event.get('source_id','')))
    if not entry:raise ValueError('This chart has expired. Generate insights again.')
    if entry['version']!=version or event.get('version')!=version:raise ValueError('The workbook changed. Generate insights again.')
    page=event.get('page',0)
    if type(page) is not int or not 0<=page<=10000:raise ValueError('Invalid source table page.')
    from .insight_dashboard import validate_entry,mark_table
    validate_entry(store,actor,entry,version)
    if entry.get('source_table'):
        selected_table,_=mark_table(entry,event)
        tables=[t for t in tables if t['id']!=selected_table['id']]+[selected_table]
    query=entry['query']
    raw={'table':query['table'],'filters':query.get('filters',[]),'limit':20}
    if query.get('date_group'):raw['date_group']=query['date_group']
    table=next(t for t in tables if t['id']==query['table'])
    if query.get('sort_by') in table['headers']:raw.update(sort_by=query['sort_by'],descending=query.get('descending',True))
    result=execute_query(tables,raw,all_rows=True)
    records=result['records'][page*50:(page+1)*50]
    records=[{k:(v[:2000]+'…' if isinstance(v,str) and len(v)>2000 else v) for k,v in r.items()} for r in records]
    store.require_permission(actor,'use_tools')
    validate_entry(store,actor,entry,version)
    return {'records':records,'total':result['result_rows'],'page':page,'page_size':50,'table':table['name']}

def evidence_records(store,actor,event,tables,version):
    entry=st.session_state.get('_stock_ai_exports',{}).get(str(event.get('source_id','')))
    if not entry or entry.get('scope')!=report_scope(store,actor):raise AccessDenied('These results expired or your access changed. Ask again.')
    if entry['version']!=version or event.get('version')!=version:raise ValueError('The workbook changed. Ask again.')
    page=event.get('page',0)
    if type(page) is not int or page<0:raise ValueError('Invalid result page.')
    view=event.get('view','result')
    if view not in ('result','source'):raise ValueError('Choose result or matching source records.')
    if 'table' in entry:
        table=entry['table'];headers=table['headers'];rows=table['rows'];total=len(rows)
        records=[dict(zip(headers,r)) for r in rows[page*50:(page+1)*50]]
    else:
        query=entry['query']
        if view=='source':query={'table':query['table'],'filters':query.get('filters',[]),'limit':20}
        result=execute_query(tables,query,all_rows=True)
        total=result['result_rows'];records=result['records'][page*50:(page+1)*50]
    return {'records':records,'total':total,'page':page,'page_size':50}

def _handle_ai(store,actor,event):
    store.require_permission(actor,'use_tools')
    if event.get('action')=='ai_status' and event.get('lightweight') is True and not event.get('load_saved_insights'):
        # Opening the composer needs metadata, never DataFrame/source preparation.
        from grounded_ai import settings
        from .planning_assistant import knowledge
        with store.transaction() as db:
            store.require(db,actor)
            current=store.run(db,"SELECT version,filename FROM datasets WHERE id='current'").fetchone()
        key,model=settings()
        return {'configured':bool(key),'model':model,'version':current['version'] if current else 'empty',
                'filename':current['filename'] if current else 'No workbook uploaded yet',
                'workbook_ready':bool(current),'knowledge_revision':knowledge()['revision']}
    if event.get('action') in ('delete_insight_chart','save_insight_item') and event.get('compact') is True:
        from .insight_memory import fast_edit
        with store.transaction() as db:
            store.require(db,actor);current=store.run(db,"SELECT version FROM datasets WHERE id='current'").fetchone()
        return fast_edit(store,actor,event,current['version'] if current else 'empty')
    if event.get('action') in ('filter_dashboard','save_dashboard'):
        from .dashboard_builder import common_filters,save_dashboard
        with store.transaction() as db:
            store.require(db,actor);current=store.run(db,"SELECT version FROM datasets WHERE id='current'").fetchone()
        return (common_filters if event['action']=='filter_dashboard' else save_dashboard)(store,actor,event,current['version'] if current else 'empty')
    if event.get('action') in ('filter_insights','insight_filter_values'):
        with store.transaction() as db:
            store.require(db,actor);current=store.run(db,"SELECT version FROM datasets WHERE id='current'").fetchone()
        from .insight_dashboard import refresh,filter_values
        return (refresh if event['action']=='filter_insights' else filter_values)(store,actor,event,current['version'] if current else 'empty')
    tables,version,filename=stock_tables(store,actor)
    if event.get('action') in ('delete_insight_chart','save_insight_item'):
        from .insight_memory import edit
        return edit(store,actor,event,version)
    if event.get('action')=='insight_filter_values':
        from .insight_dashboard import filter_values
        return filter_values(store,actor,event,version)
    if event.get('action')=='filter_insights':
        from .insight_dashboard import refresh
        return refresh(store,actor,event,version)
    if event.get('action')=='ai_records':return evidence_records(store,actor,event,tables,version)
    if event.get('action')=='insight_records':return insight_records(store,actor,event,tables,version)
    if event.get('action')=='ai_export':return export_evidence(store,actor,event,tables,version)
    if event.get('action')=='ai_status':
        from grounded_ai import settings
        key,model=settings()
        from .planning_assistant import knowledge
        saved_report={}
        if event.get('load_saved_insights') is True:
            from .insight_memory import restore,active_analysis
            saved_report={'saved_report':restore(store,actor,version),'active_analysis':active_analysis(store,actor,version)}
        from .monthly_kpi import current_month
        return {'calendar_month':current_month(),**saved_report,'configured':bool(key),'model':model,'version':version,'tables':len(tables),'filename':filename,'knowledge_revision':knowledge()['revision'],'planning_revision':str(data_revision(store,actor)),'report_scope':report_scope(store,actor)}
    if event.get('action')=='ai_clear':
        thread=hashlib.sha256(json_text([version,event.get('context')]).encode()).hexdigest()
        st.session_state.setdefault('_stock_ai_threads',{}).pop(thread,None)
        st.session_state.setdefault('_planning_scenarios',{}).pop(thread,None)
        return {'ok':True}
    if event.get('consent') is not True:raise ValueError('Enable sharing the question and relevant loaded records with Google Gemini first.')
    if event.get('version')!=version:raise ValueError('The workbook changed. Refresh this chat and ask again using the current data.')
    if event.get('action')=='add_insight_chart':
        from . import custom_insight
        if getattr(custom_insight,'REVISION',0)!=7:
            import importlib
            custom_insight=importlib.reload(custom_insight)
        return custom_insight.handle(store,actor,event,tables,version)
    if event.get('action')=='generate_insights' and (event.get('progressive') is True or event.get('job_id') is not None):
        from .insight_jobs import handle
        return handle(store,actor,event,tables,version)
    if event.get('action')=='generate_insights':
        from .insights import build_report,report_views
        from .workspace_insights import workspace_payload
        data,_,_=workspace_payload(store,actor)
        from .insight_attention import prepare
        current=store.get_dataset(actor)
        production_revision=str(data_revision(store,actor));initial_scope=report_scope(store,actor)
        report_tables,views,planning_context=prepare(store,actor,tables,report_views(data),current,data)
        from .insight_dashboard import extend_sources,connected_views,register
        report_tables,views,planning_context=extend_sources(store,actor,report_tables,views,planning_context,current)
        report_tables,views,planning_context=connected_views(report_tables,views,planning_context,store=store,actor=actor,current=current)
        result=build_report(report_tables,views,planning_context)
        store.require_permission(actor,'use_tools')
        if stock_tables(store,actor)[1]!=version:raise ValueError('The workbook changed. Generate the report again.')
        if str(data_revision(store,actor))!=production_revision:raise ValueError('Production plans changed while analysing. Generate the report again.')
        if report_scope(store,actor)!=initial_scope:raise AccessDenied('Your access changed while analysing. Generate the dashboard again.')
        for section in result['sections']:register(store,actor,section,report_tables,version)
        store.log_event(actor,'tool_use','Insights & Graphs')
        report_id=secrets.token_urlsafe(18)
        reports=st.session_state.setdefault('_stock_custom_reports',{})
        reports[report_id]={'version':version,'planning_revision':production_revision,'scope':report_scope(store,actor),'knowledge_revision':result.get('knowledge_revision',planning_context['knowledge']['revision']),
                            'charts':{s['view']:[{'title':c['title'],'query':c['evidence']['query']} for c in s['charts']] for s in result['sections']}}
        while len(reports)>5:reports.pop(next(iter(reports)))
        import copy
        dashboards=st.session_state.setdefault('_stock_dashboard_reports',{})
        dashboards[report_id]={'version':version,'scope':report_scope(store,actor),'planning_revision':production_revision,'knowledge_revision':planning_context['knowledge']['revision'],'sections':copy.deepcopy(result['sections']),'tables':report_tables,'context':planning_context,'views':{v['view']:v for v in views}}
        while len(dashboards)>2:dashboards.pop(next(iter(dashboards)))
        response={**result,'version':version,'report_id':report_id,'planning_revision':production_revision,'report_scope':report_scope(store,actor)}
        from .insight_memory import save
        save(store,actor,response,dashboards[report_id])
        reports[report_id]['charts']={s['view']:[{'title':c['title'],'query':c['evidence']['query']} for c in s['charts']] for s in response['sections']}
        return response
    context=event.get('context')
    thread=hashlib.sha256(json_text([version,context]).encode()).hexdigest()
    threads=st.session_state.setdefault('_stock_ai_threads',{})
    history=threads.get(thread,[])
    question=event.get('question')
    from .planning_assistant import reply
    scenarios=st.session_state.setdefault('_planning_scenarios',{})
    result=reply(store,actor,tables,question,history,context,scenarios.get(thread))
    scenarios[thread]=result.pop('scenario',scenarios.get(thread,{}))
    while len(scenarios)>10:scenarios.pop(next(iter(scenarios)))
    # Recheck revocation before returning the provider result.
    store.require_permission(actor,'use_tools')
    threads[thread]=(history+[{'role':'user','text':question},{'role':'assistant','text':result['answer']}])[-40:]
    while len(threads)>10:threads.pop(next(iter(threads)))
    store.log_event(actor,'tool_use','Ask AI')
    exports=st.session_state.setdefault('_stock_ai_exports',{})
    for item in result.get('evidence',[]):
        tool_table=item.pop('_table',None)
        token=secrets.token_urlsafe(18)
        exports[token]={'version':version,'scope':report_scope(store,actor),**({'table':tool_table} if tool_table else {'query':item['query']})}
        item['source_id']=token
        if store.identity(actor)['role']=='admin':
            item['export_id']=token
    while len(exports)>100:exports.pop(next(iter(exports)))
    return {**result,'version':version}

# Increment with analysis protocol changes to invalidate hot-deployment helpers.
INSIGHTS_REVISION=21

AI_EXPORT_REVISION=1

PLANNING_ASSISTANT_REVISION=1

INSIGHT_ATTENTION_REVISION=1

def data_revision(store,actor):
    from .production import schema
    from .insight_dashboard import source_revision
    with store.transaction() as db:
        store.require(db,actor);schema(store,db)
        rows=store.run(db,'SELECT kind,id,revision,updated_at FROM production_shared ORDER BY kind,id').fetchall()
        # A conservative digest avoids decoding/scoping the workbook merely to
        # detect a revision and exposes no other segment's plan identifiers.
        production=hashlib.sha256(json_text([(r['kind'],r['id'],r['revision'],r['updated_at']) for r in rows]).encode()).hexdigest()
    return [('production',production)]+source_revision(store,actor)

def report_scope(store,actor):
    identity=store.identity(actor)
    return hashlib.sha256(json_text([actor.username,identity['permissions'],identity.get('allowedSegments')]).encode()).hexdigest()[:16]

CUSTOM_INSIGHT_REVISION=7




def handle_ai(store,actor,event):
    from . import insight_display
    if event.get('action')=='ai_status' and event.get('display_cache') is True:
        with store.transaction() as db:
            store.require(db,actor);current=store.run(db,"SELECT version,filename FROM datasets WHERE id='current'").fetchone()
        return insight_display.status(store,actor,event,current['version'] if current else 'empty',current['filename'] if current else 'No workbook uploaded yet')
    if event.get('compact') is True and event.get('action') in ('save_insight_item','delete_insight_chart'):
        from .insight_kpi_edits import edit
        with store.transaction() as db:
            store.require(db,actor);current=store.run(db,"SELECT version FROM datasets WHERE id='current'").fetchone()
        return edit(store,actor,event,current['version'] if current else 'empty')
    event=insight_display.resolve(store,actor,event)
    result=None
    action=event.get('action');registry='_stock_insight_sources' if action=='insight_records' else '_stock_ai_exports' if action=='ai_export' else None
    entry=st.session_state.get(registry,{}).get(str(event.get('source_id' if action=='insight_records' else 'export_id',''))) if registry else None
    if entry and entry.get('source_table'):
        store.require_permission(actor,'use_tools')
        with store.transaction() as db:
            store.require(db,actor);current=store.run(db,"SELECT version FROM datasets WHERE id='current'").fetchone()
        version=current['version'] if current else 'empty'
        result=(insight_records if action=='insight_records' else export_evidence)(store,actor,event,[entry['source_table']],version)
    else:result=_handle_ai(store,actor,event)
    if event.get('action') in ('generate_insights','add_insight_chart','delete_insight_chart','save_insight_item','save_dashboard'):
        return insight_display.stamp_response(store,actor,event,result)
    return result


