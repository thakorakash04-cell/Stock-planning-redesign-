"""Saved reports are permission-scoped, durable, editable and query-backed after restore."""
import copy
from unittest.mock import patch
import pytest
import streamlit as st
from test_stock_assistant import accounts
from stock_accounts.workspace_insights import handle_request
from stock_accounts.insights import chart_result
from stock_accounts.insight_memory import scope_key


def generate(store,actor):
    version=store.get_dataset(actor)['version']
    def build(tables,views,context):
        table=next(t for t in tables if t['name']=='Stock')
        view={'view':0,'table_id':table['id'],'table':'Stock','title':'Stock overview'}
        chart=chart_result(tables,view,{'title':'Quantity','label':'Material','value':'Qty','query':{'table':table['id'],'columns':['Material','Qty'],'limit':10}})
        return {'sections':[{'view':0,'title':'Stock overview','records':len(table['rows']),'charts':[chart],'kpis':[]}],'answer':'Review quantities','generated_at':'2026-10-27','knowledge_revision':context['knowledge']['revision']}
    with patch('stock_accounts.insights.build_report',side_effect=build),patch('stock_accounts.insight_dashboard.connected_views',side_effect=lambda t,v,c,**kw:(t,v,c)):
        return handle_request(store,actor,{'action':'generate_insights','version':version,'consent':True})

def status(store,actor):return handle_request(store,actor,{'action':'ai_status','load_saved_insights':True})['saved_report']

def test_new_session_and_matching_user_restore_without_ai_and_keep_drillthrough(accounts):
    store,admin,viewer=accounts
    original=generate(store,viewer);old_source=original['sections'][0]['charts'][0]['evidence']['source_id']
    store.create_viewer(admin,'another_user','Another-viewer-password!123');other=store.login('another_user','Another-viewer-password!123')
    assert scope_key(store,viewer)==scope_key(store,other)
    st.session_state.clear()
    with patch('stock_accounts.insights.generate') as provider:
        restored=status(store,other)
        provider.assert_not_called()
    assert restored['cached'] and restored['generated_at']==original['generated_at']
    assert restored['report_id']!=original['report_id']
    evidence=restored['sections'][0]['charts'][0]['evidence']
    assert evidence['source_id']!=old_source and 'export_id' not in evidence
    records=handle_request(store,other,{'action':'insight_records','version':restored['version'],'source_id':evidence['source_id'],'mark':1})
    assert records['records'][0]['Material']=='B' and records['total']==1
    assert status(store,other)['report_id']==restored['report_id'],'Repeated reads reuse registered evidence in the same session'
    assert status(store,admin) is None,'Admin and viewer dashboards cannot cross access scopes'
    # A changed right invalidates old credentials and selects a different cache scope.
    store.update_permissions(admin,'another_user',{'menu_0':False});other=store.login('another_user','Another-viewer-password!123')
    assert status(store,other) is None


def test_delete_and_custom_definition_survive_regeneration_and_new_workbook(accounts):
    store,admin,_=accounts;before=store.get_dataset(admin);report=generate(store,admin)
    chart=report['sections'][0]['charts'][0]
    result=handle_request(store,admin,{'action':'delete_insight_chart','report_id':report['report_id'],'version':report['version'],'view':0,'chart_id':chart['id']})
    assert not result['report']['sections'][0]['charts']
    regenerated=generate(store,admin)
    assert not regenerated['sections'][0]['charts'],'The removed query must not return during regeneration'
    token=regenerated['report_id'];dashboard=st.session_state['_stock_dashboard_reports'][token];table=next(t for t in dashboard['tables'] if t['name']=='Stock')
    specification={'title':'Quantity totals','type':'column','label':'Material','value':'sum(Qty)','query':{'table':table['id'],'group_by':['Material'],'metrics':[{'column':'Qty','op':'sum'}],'limit':10}}
    custom=chart_result(dashboard['tables'],{**dashboard['views'][0],'table_id':table['id']},specification);custom['custom']=True
    with patch('stock_accounts.custom_insight.create',return_value={'chart':custom,'source_table':table}):
        added=handle_request(store,admin,{'action':'add_insight_chart','report_id':token,'version':report['version'],'view':0,'question':'Save my totals','consent':True})
    assert added['report']['sections'][0]['charts'][0]['custom']
    st.session_state.clear()
    restored=status(store,admin)
    assert restored['sections'][0]['charts'][0]['value']=='sum(Qty)'
    assert store.get_dataset(admin)==before
    store.save_dataset(admin,'updated.xlsx',{'sheets':[{'name':'Stock','headers':['Material','Qty'],'rows':[['A',30],['B',90]]}],'tables':[]})
    assert status(store,admin) is None,'A new workbook must not display cached old quantities'
    with patch('stock_accounts.custom_insight.generate') as provider:
        refreshed=generate(store,admin)
        provider.assert_not_called()
    graphs=refreshed['sections'][0]['charts']
    assert len(graphs)==1 and graphs[0]['custom']
    assert [r['sum(Qty)'] for r in graphs[0]['evidence']['records']]==[30,90]
    # Deleting the custom graph removes its reusable definition too.
    handle_request(store,admin,{'action':'delete_insight_chart','report_id':refreshed['report_id'],'version':refreshed['version'],'view':0,'chart_id':graphs[0]['id']})
    assert not generate(store,admin)['sections'][0]['charts']


def test_stale_report_cannot_overwrite_newer_run_or_other_users_layout(accounts):
    store,admin,viewer=accounts;old=generate(store,admin);new=generate(store,admin)
    event={'action':'delete_insight_chart','report_id':old['report_id'],'version':old['version'],'view':0,'chart_id':old['sections'][0]['charts'][0]['id']}
    with pytest.raises(ValueError,match='regenerated'):handle_request(store,admin,event)
    with pytest.raises(PermissionError):handle_request(store,viewer,event)
    assert status(store,admin)['cache_generation']==new['cache_generation']
    store.update_permissions(admin,'viewer_user',{'menu_8':False});viewer=store.login('viewer_user','Test-viewer-password!123')
    with pytest.raises(PermissionError):status(store,viewer)


def test_business_source_change_invalidates_saved_report_and_failed_run_keeps_old_cache(accounts):
    store,admin,_=accounts;report=generate(store,admin)
    with patch('stock_accounts.insights.build_report',side_effect=ValueError('Provider unavailable')),patch('stock_accounts.insight_dashboard.connected_views',side_effect=lambda t,v,c,**kw:(t,v,c)):
        with pytest.raises(ValueError,match='Provider'):handle_request(store,admin,{'action':'generate_insights','version':report['version'],'consent':True})
    assert status(store,admin)['cache_generation']==report['cache_generation']
    with patch('stock_accounts.assistant_insights.data_revision',return_value=[('updated-sales',2)]):
        assert status(store,admin) is None


def test_restored_admin_report_still_supports_filters_and_authorized_evidence_download(accounts):
    import base64,io
    from openpyxl import load_workbook
    store,admin,_=accounts;generate(store,admin);st.session_state.clear()
    report=status(store,admin)
    result=handle_request(store,admin,{'action':'filter_insights','report_id':report['report_id'],'version':report['version'],'view':0,'filters':[{'column':'Material','op':'in','value':['B']}]})
    chart=result['section']['charts'][0];assert chart['id']==report['sections'][0]['charts'][0]['id']
    evidence=chart['evidence'];assert evidence['matched_records']==1
    file=handle_request(store,admin,{'action':'ai_export','version':report['version'],'export_id':evidence['export_id'],'mark':0})
    workbook=load_workbook(io.BytesIO(base64.b64decode(file['content'])))
    assert workbook['Matching records'].max_row==2
    sheet=workbook['Matching records'];headers=[c.value for c in sheet[1]]
    assert sheet.cell(2,headers.index('Material')+1).value=='B'
