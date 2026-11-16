"""Resumable Insights generation: one bounded provider phase per authenticated RPC."""
import copy,math,secrets
from datetime import datetime,timezone
import streamlit as st
from .store import AccessDenied

REVISION=5
BATCH_SIZE=2

def compact_context(context,views):
    """Send current rules and evidence, without repeatedly serializing source implementations."""
    from .planning_assistant import CROSS_SHEET_PROTOCOL
    ids={v['view'] for v in views};knowledge=context.get('knowledge',{})
    return {**context,'knowledge':{'revision':knowledge.get('revision'),'rules':knowledge.get('rules',''),'release_notes':knowledge.get('release_notes','')[-6000:],'cross_sheet_protocol':CROSS_SHEET_PROTOCOL,'calculation_definitions':[{'module':item.get('module'),'description':item.get('description'),'functions':[{'name':f.get('name'),'description':f.get('description')} for f in item.get('functions',[]) if f.get('name') in ('calculate','availability','build','run_tool','purchasing','report')]} for item in knowledge.get('deployed_features',[]) if any(f.get('name') in ('calculate','availability','build','run_tool','purchasing','report') for f in item.get('functions',[]))]},
            'attention':[a for a in context.get('attention',[]) if a['view'] in ids],
            'priority_charts':{k:v for k,v in context.get('priority_charts',{}).items() if k in ids}}

def validate(store,actor,job,version):
    from .assistant_insights import data_revision,report_scope
    from .planning_assistant import knowledge
    from .access import require_menu
    require_menu(store,actor,8);store.require_permission(actor,'use_tools')
    if job['scope']!=report_scope(store,actor):raise AccessDenied('Your access changed. Start a new analysis.')
    if job['version']!=version or job['planning_revision']!=str(data_revision(store,actor)):raise ValueError('Business data changed. Start a new analysis.')
    if job['knowledge_revision']!=knowledge()['revision']:raise ValueError('Planning rules changed. Start a new analysis.')

def response(job):
    batches=max(1,math.ceil(len(job['views'])/BATCH_SIZE));total=1+batches*2
    completed=1+job['batch']*2+(1 if job['phase']=='review' else 0) if job['phase']!='connected' else 0
    if job['phase']=='done':completed=total
    labels={'connected':'Connecting business sources','charts':'Calculating KPI cards and graphs','review':'Writing business findings','done':'Analysis complete'}
    return {'pending':job['phase']!='done','job_id':job['id'],'step':job['step'],
            'progress':{'label':labels[job['phase']],'completed':completed,'total':total,'percent':round(completed/total*100)},
            'report':job['report'] if job['report']['sections'] else None}

def publish(job):
    """Keep custom graphs, filters and evidence available as sections arrive."""
    report=job['report'];token=report['report_id']
    reports=st.session_state.setdefault('_stock_custom_reports',{})
    reports[token]={'version':job['version'],'planning_revision':job['planning_revision'],'scope':job['scope'],'knowledge_revision':job['knowledge_revision'],
                    'charts':{s['view']:[{'title':c['title'],'query':c['evidence']['query']} for c in s['charts']] for s in report['sections']}}
    while len(reports)>5:reports.pop(next(iter(reports)))
    dashboards=st.session_state.setdefault('_stock_dashboard_reports',{})
    dashboards[token]={k:job[k] for k in ('version','scope','planning_revision','knowledge_revision','tables')}
    dashboards[token].update(context=job['context'],sections=copy.deepcopy(report['sections']),views={v['view']:v for v in job['views']})
    while len(dashboards)>2:dashboards.pop(next(iter(dashboards)))

def persist_completed(store,actor,job):
    if job.get('persisted'):return
    from .insight_memory import save
    publish(job)
    dashboard=st.session_state['_stock_dashboard_reports'][job['report']['report_id']]
    save(store,actor,job['report'],dashboard)
    publish(job)
    st.session_state['_stock_dashboard_reports'][job['report']['report_id']]['cache_generation']=job['report']['cache_generation']
    from .insight_memory import clear_checkpoint
    clear_checkpoint(store,actor,job)
    job['persisted']=True

def finish_step(store,actor,job,step):
    # A database failure can retry publication without another provider phase.
    job['pending_step']=step
    publish(job)
    if job['phase']=='done':persist_completed(store,actor,job)
    else:
        from .insight_memory import checkpoint
        checkpoint(store,actor,job,job['step']+1)
    job['step']+=1;job['last_step']=step
    job.pop('pending_step',None)
    job['last_response']=copy.deepcopy(response(job))
    return job['last_response']

def handle(store,actor,event,tables,version):
    from .assistant_insights import data_revision,report_scope
    from .planning_assistant import knowledge
    jobs=st.session_state.setdefault('_stock_insight_jobs',{})
    token=event.get('job_id')
    if token is None:
        request=event.get('request_id')
        if not isinstance(request,str) or not 1<=len(request)<=100:raise ValueError('Start analysis again to create a request.')
        # A lost initial response can be retried without repeating source preparation.
        existing=next((j for j in jobs.values() if j['request_id']==request and j['scope']==report_scope(store,actor)),None)
        if existing:validate(store,actor,existing,version);return response(existing)
        from .workspace_insights import workspace_payload
        from .insights import report_views
        from .insight_attention import prepare
        from .insight_dashboard import extend_sources
        scope=report_scope(store,actor);revision=str(data_revision(store,actor));know=knowledge()['revision']
        data,_,_=workspace_payload(store,actor);current=store.get_dataset(actor)
        if not current:raise ValueError('Upload a workbook before running analysis.')
        prepared,views,context=prepare(store,actor,tables,report_views(data),current,data)
        prepared,views,context=extend_sources(store,actor,prepared,views,context,current)
        from .dashboard_builder import configuration,select_views
        dashboard_config=configuration(event.get('dashboard'))
        views=select_views(views,dashboard_config)
        if not views:raise ValueError('No permitted source views are available for this dashboard template.')
        context={**context,'dashboard_request':dashboard_config['question'],'dashboard_template':dashboard_config['template']}
        token=secrets.token_urlsafe(18);report_id=secrets.token_urlsafe(18)
        report={'dashboard':dashboard_config,'report_id':report_id,'version':version,'report_scope':scope,'planning_revision':revision,'knowledge_revision':know,
                'referenceDate':context.get('referenceDate'),'attention':context.get('attention',[]),'scope_notes':context.get('limitations',[]),
                'generated_at':datetime.now(timezone.utc).isoformat(),'overview':'Analysis is in progress. Completed dashboards appear below.','answer':'','warnings':[],'sections':[]}
        job={'id':token,'request_id':request,'version':version,'scope':scope,'planning_revision':revision,'knowledge_revision':know,'tables':prepared,'views':views,'context':context,'report':report,'phase':'connected','batch':0,'step':0,'briefs':[]}
        validate(store,actor,job,version);jobs[token]=job
        while len(jobs)>2:jobs.pop(next(iter(jobs)))
        return response(job)
    if not isinstance(token,str) or token not in jobs:raise ValueError('This analysis expired. Start a new analysis.')
    job=jobs[token];validate(store,actor,job,version)
    step=event.get('step')
    if type(step) is not int:raise ValueError('Invalid analysis step.')
    if step==job.get('last_step'):return job['last_response']
    if step!=job['step']:raise ValueError('The analysis step changed. Resume the latest analysis.')
    if job.get('pending_step')==step or job['phase']=='done':return finish_step(store,actor,job,step)
    from .insight_dashboard import connected_views,register
    from .insights import build_report,review_sections
    context=compact_context(job['context'],job['views'])
    if job['phase']=='connected':
        current=store.get_dataset(actor)
        prepared,views,connected_context=connected_views(job['tables'],job['views'],context,store=store,actor=actor,current=current)
        validate(store,actor,job,version)
        job.update(tables=prepared,views=views,context=connected_context,phase='charts')
        job['report']['scope_notes']=connected_context.get('limitations',[])
    elif job['phase']=='charts':
        batch=job['views'][job['batch']*BATCH_SIZE:(job['batch']+1)*BATCH_SIZE]
        result=build_report(job['tables'],batch,compact_context(job['context'],batch),include_review=False)
        validate(store,actor,job,version)
        from .insight_memory import apply_layout
        apply_layout(store,actor,result,job['tables'],job['views'])
        for section in result['sections']:register(store,actor,section,job['tables'],version)
        job['report']['sections'].extend(result['sections']);job['report']['warnings'].extend(result.get('warnings',[]))
        job['current_sections']=result['sections'];job['phase']='review'
    elif job['phase']=='review':
        batch=job['views'][job['batch']*BATCH_SIZE:(job['batch']+1)*BATCH_SIZE]
        sections=copy.deepcopy(job['current_sections']);warnings=[]
        narrative=review_sections(sections,compact_context(job['context'],batch),warnings)
        validate(store,actor,job,version)
        ids={s['view'] for s in sections};job['report']['sections']=[s for s in job['report']['sections'] if s['view'] not in ids]+sections
        job['report']['warnings'].extend(warnings)
        if isinstance(narrative,dict) and isinstance(narrative.get('overview'),str) and narrative['overview'].strip():
            job['briefs'].append(narrative['overview'].strip());job['report']['overview']='\n\n'.join(job['briefs'])
        job['batch']+=1;job['phase']='charts' if job['batch']*BATCH_SIZE<len(job['views']) else 'done'
        if job['phase']=='done':
            if not job['briefs']:job['report']['overview']='Review the calculated KPI cards, findings and supporting records for each business section.'
            store.log_event(actor,'tool_use','Insights & Graphs')
    return finish_step(store,actor,job,step)

