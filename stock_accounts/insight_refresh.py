"""Refresh saved numeric dashboards from current authorized sources, without AI."""
import copy
from datetime import datetime,timezone

REVISION=4

def prepare_sources(store,actor):
    from .assistant_insights import stock_tables
    from .workspace_insights import workspace_payload
    from .insights import report_views
    from .insight_attention import prepare
    from .insight_dashboard import extend_sources
    tables,_,_=stock_tables(store,actor);data,_,_=workspace_payload(store,actor)
    current=store.get_dataset(actor)
    tables,views,context=prepare(store,actor,tables,report_views(data),current,data)
    tables,views,context=extend_sources(store,actor,tables,views,context,current)
    return tables,views,context,current

def recalculate(store,actor,saved,force=False):
    from .insight_memory import digest
    from .insight_dashboard import kpi_result,facets,filter_table
    from .insights import chart_result
    tables,views,context,current=prepare_sources(store,actor)
    result=copy.deepcopy(saved);report=result['report'];old_tables=result['tables']
    def match(old):
        exact=[t for t in tables if t['id']==old['id'] and t['name']==old['name']]
        candidates=exact or [t for t in tables if t['name']==old['name'] and t.get('source_kind')==old.get('source_kind')]
        return candidates[0] if len(candidates)==1 else None
    # Preserve snapshot IDs, because all validated saved queries refer to them.
    refreshed=[];changed=set();missing=set()
    for old in old_tables:
        if old['id'].startswith('CONNECTED'):continue
        fresh=match(old)
        if fresh is None:
            fresh={**old,'rows':[]};missing.add(old['id'])
        else:fresh={**fresh,'id':old['id']}
        if force or digest([old['headers'],old['rows']])!=digest([fresh['headers'],fresh['rows']]):changed.add(old['id'])
        refreshed.append(fresh)
    for old in old_tables:
        if not old['id'].startswith('CONNECTED'):continue
        dependencies=old.get('refresh_sources');plan=old.get('refresh_plan')
        needs=any(t['id'] in changed or t['id'] in missing for t in dependencies) if dependencies else bool(changed or missing)
        if not needs:refreshed.append(old);continue
        changed.add(old['id'])
        try:
            if not plan or not dependencies:raise ValueError('This older comparison has no saved join definition; regenerate it once.')
            if any(t['id'] in missing for t in dependencies):raise ValueError('A comparison source is no longer available.')
            # The original bounded server tool revalidates keys, grain and permissions.
            from .planning_assistant import run_tool
            evidence,_=run_tool(store,actor,{**copy.deepcopy(plan),'operation':'insight_comparison'},current,refreshed)
            detail=evidence[-1]['_table'];fresh={**old,'headers':detail['headers'],'rows':detail['rows']}
        except (ValueError,KeyError,StopIteration) as exc:
            missing.add(old['id']);fresh={**old,'rows':[]}
            warning=old['name']+': '+str(exc)
            if warning not in report.setdefault('warnings',[]):report['warnings'].append(warning)
        refreshed.append(fresh)
    by_id={t['id']:t for t in refreshed};affected=[]
    for section in report['sections']:
        view=next(v for v in result['views'] if v['view']==section['view'])
        table=next((t for t in refreshed if t['name']==view['table']),None)
        from .monthly_kpi import needs_refresh
        if table is None or table['id'] not in changed|missing and not needs_refresh({'sections':[section]}):continue
        affected.append(section['view']);section['facets']=facets(table)
        filter_error=None
        try:filtered=filter_table(table,section.get('filters',[]));section['records']=len(filtered['rows'])
        except ValueError as exc:filtered={**table,'rows':[]};section['records']=0;filter_error=str(exc)
        section['review_mode']='calculated';section.pop('review',None)
        for kind in ('charts','kpis'):
            rebuilt=[]
            for item in section.get(kind,[]):
                try:
                    source=by_id[item['evidence']['query']['table']]
                    if filter_error:raise ValueError('Saved filter unavailable: '+filter_error)
                    if section.get('filters'):source=filter_table(source,section['filters'])
                    scoped=[source if t['id']==source['id'] else t for t in refreshed]
                    if source['id'] in missing:raise ValueError('Source unavailable; the saved definition is retained.')
                    spec={**item,'query':copy.deepcopy(item['evidence']['query'])}
                    if kind=='charts':
                        updated=chart_result(scoped,{**view,'table_id':source['id']},spec)
                        updated.update(finding='Automatically recalculated from current saved data.',action='Select a graph value to inspect its current matching records.')
                    else:
                        updated=kpi_result(scoped,{**view,'table_id':source['id']},{**spec,'value':item['field']})
                    updated.update({key:item[key] for key in ('id','custom','saved','request') if key in item})
                    rebuilt.append(updated)
                except (ValueError,KeyError,StopIteration) as exc:
                    # Retain the specification for a later valid edit, but never expose stale evidence.
                    unavailable=copy.deepcopy(item);unavailable['evidence'].update(records=[],shown_rows=0,result_rows=0,matched_records=0)
                    unavailable['evidence'].pop('source_id',None);unavailable['evidence'].pop('export_id',None)
                    unavailable['refresh_error']=str(exc)
                    if kind=='kpis':
                        unavailable['value']=None;unavailable.pop('comparison_result',None);unavailable.pop('comparison_evidence',None)
                    else:
                        unavailable.update(finding='Current values are unavailable; previous graph values are hidden.',action='Check the source or regenerate this comparison.');unavailable.pop('data_quality',None)
                    rebuilt.append(unavailable)
            section[kind]=rebuilt
        section['review']={'findings':[f'{section["records"]:,} current saved records. KPI cards and graphs updated automatically.'],'actions':['Select values to verify their current source records.'],'data_quality':['The previous AI narrative is hidden for this changed section. No new AI request was made.']}
    if affected:
        report['overview']='Saved dashboard updated from current business data. Review the recalculated sections and current source records; the previous AI business brief has been hidden.'
        report['answer']='';report['attention']=context.get('attention',[]);report['referenceDate']=context.get('referenceDate')
        report['data_updated_at']=datetime.now(timezone.utc).isoformat();report['updated_views']=affected
    result.update(tables=refreshed,context=context)
    return result

