from unittest.mock import patch
import pytest
import streamlit as st
from grounded_ai import execute_query
from stock_accounts.insight_dashboard import kpi_result,mark_table,filter_table,refresh,register,connected_views
from stock_accounts.insights import chart_result
from stock_accounts.workspace_insights import handle_request
from test_stock_assistant import accounts

TABLE={'id':'T1','name':'Stock','headers':['Material','Segment','Qty'],'rows':[['A','Alpha',3],['A','Beta',9],['B','Alpha',2]]}
VIEW={'view':0,'table':'Stock','table_id':'T1','title':'Stock overview'}

def test_ai_kpis_aggregate_full_scope_not_chart_top_ten():
 table={**TABLE,'rows':[['A'+str(i),'Alpha',i] for i in range(1,101)]}
 result=kpi_result([table],VIEW,{'title':'Total units','value':'sum(Qty)','basis':'Same-unit source quantity','query':{'table':'T1','metrics':[{'column':'Qty','op':'sum'}],'limit':1}})
 assert result['value']==5050 and result['evidence']['matched_records']==100
 with pytest.raises(ValueError,match='whole-scope'):
  kpi_result([table],VIEW,{'query':{'table':'T1','group_by':['Segment'],'metrics':[{'column':'Qty','op':'sum'}]}})

def test_duplicate_raw_labels_drill_to_exact_source_row():
 q={'table':'T1','columns':['Material','Qty'],'sort_by':'Qty','limit':10}
 evidence=execute_query([TABLE],q)
 table,query=mark_table({'source_table':TABLE,'query':evidence['query'],'marks':evidence['records']},{'mark':0})
 assert table['rows']==[['A','Beta',9]]
 with pytest.raises(ValueError,match='current graph'):
  mark_table({'source_table':TABLE,'query':q,'marks':evidence['records']},{'mark':99})

def test_group_mark_opens_all_contributing_rows_not_aggregate_or_other_segments():
 q={'table':'T1','group_by':['Segment'],'metrics':[{'column':'Qty','op':'sum'}],'limit':10}
 evidence=execute_query([TABLE],q)
 table,_=mark_table({'source_table':TABLE,'query':evidence['query'],'marks':evidence['records']},{'mark':0})
 assert table['rows']==[['A','Alpha',3],['B','Alpha',2]]
 assert sum(r[2] for r in table['rows'])==evidence['records'][0]['sum(Qty)']

def test_filter_on_full_data_then_calculate_chart_and_kpi(accounts):
 from stock_accounts.assistant_insights import data_revision,report_scope
 from stock_accounts.planning_assistant import knowledge
 store,admin,_=accounts;version=store.get_dataset(admin)['version']
 q={'table':'T1','columns':['Material','Qty'],'sort_by':'Qty','limit':2}
 c=chart_result([TABLE],VIEW,{'title':'Rank','label':'Material','value':'Qty','query':q})
 k=kpi_result([TABLE],VIEW,{'title':'Units','value':'sum(Qty)','query':{'table':'T1','metrics':[{'column':'Qty','op':'sum'}],'limit':1}})
 section={'view':0,'title':'Stock','charts':[c],'kpis':[k],'facets':[],'records':3}
 st.session_state['_stock_dashboard_reports']={'report':{'version':version,'scope':report_scope(store,admin),'planning_revision':str(data_revision(store,admin)),'knowledge_revision':knowledge()['revision'],'sections':[section],'tables':[TABLE],'views':{0:VIEW}}}
 r=refresh(store,admin,{'report_id':'report','version':version,'view':0,'filters':[{'column':'Segment','op':'eq','value':'Alpha'}]},version)['section']
 assert r['records']==2 and r['kpis'][0]['value']==5
 assert [x['Qty'] for x in r['charts'][0]['evidence']['records']]==[3,2]
 assert r['review_mode']=='calculated'
 e=r['charts'][0]['evidence']
 out=handle_request(store,admin,{'action':'insight_records','version':version,'source_id':e['source_id'],'mark':0})
 assert out['total']==1 and out['records'][0]['Segment']=='Alpha'
 reset=refresh(store,admin,{'report_id':'report','version':version,'view':0,'filters':[]},version)['section']
 assert reset['kpis'][0]['value']==14 and reset['records']==3


def test_report_and_source_permissions_rechecked(accounts):
 store,admin,viewer=accounts;version=store.get_dataset(viewer)['version']
 c=chart_result([TABLE],VIEW,{'title':'Rank','label':'Material','value':'Qty','query':{'table':'T1','columns':['Material','Qty'],'limit':10}})
 register(store,viewer,{'charts':[c]},[TABLE],version)
 store.update_permissions(admin,'viewer_user',{'menu_0':False})
 viewer=store.login('viewer_user','Test-viewer-password!123')
 with pytest.raises(PermissionError,match='access changed'):
  handle_request(store,viewer,{'action':'insight_records','version':version,'source_id':c['evidence']['source_id']})


def test_connected_ai_plan_cannot_use_hidden_tables():
 hidden={'id':'HIDDEN','name':'Private','headers':['Material','Rate'],'rows':[['A',50]]}
 plan={'comparisons':[{'title':'Invalid join','plan':{'sources':[{'alias':'s0','table':'T1'},{'alias':'s1','table':'HIDDEN'}],'joins':[{'left_on':['s0.Material'],'right_on':['s1.Material']}],'columns':['s0.Material','s1.Rate']}}]}
 with patch('stock_accounts.insight_dashboard.settings',return_value=('key','model')),patch('stock_accounts.insight_dashboard.generate',return_value=plan):
  tables,views,ctx=connected_views([TABLE,hidden],[VIEW],{})
 assert len(views)==1 and 'could not be verified' in ctx['limitations'][0]


def test_invalid_filter_rejected_and_empty_scope_retained():
 with pytest.raises(ValueError):filter_table(TABLE,[{'column':'Qty','op':'execute','value':1}])
 assert filter_table(TABLE,[{'column':'Segment','op':'eq','value':'Missing'}])['rows']==[]


def test_kpi_rejects_mixed_units_and_summed_percentages():
 table={'id':'T1','name':'Stock','headers':['Material','Qty','UoM','Margin %'],'rows':[['A',3,'EA',10],['B',9,'KG',20]]}
 for col in ('Qty','Margin %'):
  with pytest.raises(ValueError):
   kpi_result([table],VIEW,{'title':col,'value':'sum('+col+')','query':{'table':'T1','metrics':[{'column':col,'op':'sum'}],'limit':1}})


def test_connected_comparison_uses_shared_many_to_one_calculator():
 prices={'id':'T2','name':'Prices','headers':['Material','Price'],'rows':[['A',2],['B',4]]}
 plan={'comparisons':[{'title':'Quantity and price','basis':'Explicit material keys; same price convention.', 'plan':{'sources':[{'alias':'s0','table':'T1'},{'alias':'s1','table':'T2'}],'joins':[{'left_on':['s0.Material'],'right_on':['s1.Material']}],'calculations':[{'name':'Value','op':'multiply','operands':['s0.Qty','s1.Price']}],'columns':['s0.Material','s0.Segment','s0.Qty','s1.Price','calc.Value']}}]}
 with patch('stock_accounts.insight_dashboard.settings',return_value=('key','model')),patch('stock_accounts.insight_dashboard.generate',return_value=plan):
  tables,views,ctx=connected_views([TABLE,prices],[VIEW,{'view':1,'table':'Prices'}],{})
 assert views[-1]['view']==30 and [r[-1] for r in tables[-1]['rows']]==[6,18,8]
 assert 'missing calculations' in views[-1]['basis']


def test_group_drill_preserves_case_sensitive_category_identity():
 table={**TABLE,'rows':[['A','Alpha',3],['B','alpha',9]]}
 query={'table':'T1','group_by':['Segment'],'metrics':[{'column':'Qty','op':'sum'}],'limit':10}
 evidence=execute_query([table],query)
 selected,_=mark_table({'source_table':table,'query':evidence['query'],'marks':evidence['records']},{'mark':0})
 assert selected['rows']==[['A','Alpha',3]]


def test_registered_insight_operation_is_read_only_and_uses_shared_calculator(accounts):
 from stock_accounts.planning_assistant import run_tool
 store,admin,_=accounts;before=store.get_dataset(admin)
 prices={'id':'T2','name':'Prices','headers':['Material','Price'],'rows':[['A',2],['B',4]]}
 plan={'operation':'insight_comparison','sources':[{'alias':'s0','table':'T1'},{'alias':'s1','table':'T2'}],'joins':[{'left_on':['s0.Material'],'right_on':['s1.Material']}],'calculations':[{'name':'Value','op':'multiply','operands':['s0.Qty','s1.Price']}],'columns':['s0.Material','calc.Value']}
 evidence,scenario=run_tool(store,admin,plan,before,[TABLE,prices])
 assert [r[-1] for r in evidence[-1]['_table']['rows']]==[6,18,8]
 assert scenario['operation']=='insight_comparison' and store.get_dataset(admin)==before


def test_selected_mark_excel_contains_same_underlying_rows(accounts):
 import base64,io
 from openpyxl import load_workbook
 store,admin,_=accounts;version=store.get_dataset(admin)['version']
 chart=chart_result([TABLE],VIEW,{'title':'Segment units','label':'Segment','value':'sum(Qty)','query':{'table':'T1','group_by':['Segment'],'metrics':[{'column':'Qty','op':'sum'}],'limit':10}})
 register(store,admin,{'charts':[chart]},[TABLE],version)
 file=handle_request(store,admin,{'action':'ai_export','version':version,'export_id':chart['evidence']['export_id'],'mark':1})
 workbook=load_workbook(io.BytesIO(base64.b64decode(file['content'])))
 rows=list(workbook['Matching records'].values)
 assert len(rows)==2 and rows[1][rows[0].index('Segment')]=='Beta'
 assert file['matched_records']==1
