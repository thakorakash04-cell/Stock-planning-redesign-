import copy
import pytest
from test_stock_assistant import accounts
from stock_accounts.cross_sheet import calculate,PlanError

TABLES=[{'id':'T1','name':'Production','headers':['Material','Quantity','Date'],'rows':[[' A ',2,'2026-04-10'],['A',3,'2026-04-20'],['B',4,'2026-04-15']]},
 {'id':'T2','name':'Prices','headers':['SKU Code','Std DP','Cost','PO Date'],'rows':[['a',10,6,'2026-04-01'],['a',10,6,'2026-04-01'],['B',20,15,'2026-04-05']]}]
def plan():
 return {'sources':[{'alias':'s0','table':'T1'},{'alias':'s1','table':'T2'}],'joins':[{'left_on':['s0.Material'],'right_on':['s1.SKU Code']}],
 'calculations':[{'name':'Revenue','op':'multiply','operands':['s0.Quantity','s1.Std DP']}],'metrics':[{'column':'calc.Revenue','op':'sum'}],'columns':['s0.Material','calc.Revenue']}
def test_join_value_and_identical_price_rows_do_not_multiply_sales():
 p=plan();before=copy.deepcopy(p);r=calculate(TABLES,p)
 assert r['tables'][0]['rows']==[[130]]
 assert r['joined_rows']==3 and r['complete']
 assert p==before
def test_conflicting_duplicate_keys_require_explicit_aggregation():
 t=copy.deepcopy(TABLES);t[1]['rows'].append(['A',99,6,'2026-04-01'])
 with pytest.raises(PlanError,match='not unique'):calculate(t,plan())
def test_missing_price_retains_missing_line_and_known_subtotal():
 t=copy.deepcopy(TABLES);t[1]['rows']=t[1]['rows'][:1]
 r=calculate(t,plan());assert not r['complete']
 assert r['tables'][0]['rows']==[[50]]
 assert r['tables'][1]['rows'][-1][-1] is None
 assert r['missing_calculations']['calc.Revenue']==1
def test_source_preaggregation_margin_percentage_and_dates():
 p=plan();p['sources'][0]={'alias':'s0','table':'T1','group_by':['Material'],'metrics':[{'column':'Quantity','op':'sum'}]}
 p['calculations']=[{'name':'Sales','op':'multiply','operands':['s0.sum(Quantity)','s1.Std DP']},{'name':'Cost','op':'multiply','operands':['s0.sum(Quantity)','s1.Cost']},{'name':'Profit','op':'subtract','operands':['calc.Sales','calc.Cost']},{'name':'Margin','op':'percent','operands':['calc.Profit','calc.Sales']}]
 p['metrics']=[{'column':'calc.Profit','op':'sum'}];p['columns']=['s0.Material','calc.Margin']
 r=calculate(TABLES,p);assert r['tables'][0]['rows']==[[40]]
 dates=plan();dates['calculations']=[{'name':'Days','op':'date_diff','operands':['s0.Date','s1.PO Date']}];dates['metrics']=[];dates['columns']=['calc.Days']
 assert calculate(TABLES,dates)['tables'][0]['rows']==[[9],[19],[10]]
def test_zero_divisor_and_missing_keys_are_not_zero_or_blank_matches():
 t=[{'id':'T1','name':'Left','headers':['Key','Value'],'rows':[[None,5],['A',5]]},{'id':'T2','name':'Right','headers':['Key','Divisor'],'rows':[[None,100],['A',0]]}]
 p={'sources':[{'alias':'s0','table':'T1'},{'alias':'s1','table':'T2'}],'joins':[{'left_on':['s0.Key'],'right_on':['s1.Key']}],'calculations':[{'name':'Ratio','op':'divide','operands':['s0.Value','s1.Divisor']}],'columns':['calc.Ratio']}
 r=calculate(t,p);assert r['tables'][0]['rows']==[[None],[None]] and not r['complete']
def test_generated_code_is_not_an_operation():
 p=plan();p['calculations'][0]['op']='eval'
 with pytest.raises(PlanError):calculate(TABLES,p)

def test_join_tool_obeys_price_menu_permissions(accounts):
 from stock_accounts.planning_assistant import run_tool
 s,a,v=accounts
 current=s.get_dataset(v)
 p=plan();p['operation']='cross_sheet'
 out,scenario=run_tool(s,v,p,current,TABLES)
 assert scenario['complete'] and len(out)==2
 s.update_permissions(a,'viewer_user',{'menu_1':False});v=s.login('viewer_user','Test-viewer-password!123')
 with pytest.raises(PermissionError):run_tool(s,v,p,s.get_dataset(v),TABLES)

def test_primary_sales_is_lazy_scoped_source_with_independent_rights(accounts):
 from unittest.mock import patch
 from stock_accounts.planning_assistant import run_tool
 s,a,v=accounts
 s.update_permissions(a,'viewer_user',{'menu_11':True,'menu_1':False});v=s.login('viewer_user','Test-viewer-password!123')
 p=plan();p['operation']='cross_sheet';p['sources'][1]['table']='SALES_PRIMARY'
 p['calculations'][0]['operands'][1]='s1.Price'
 loaded={'available':True,'headers':['SKU Code','Price'],'rows':[['A',10],['B',20]],'source':{'version':'sales-v1'}}
 with patch('stock_accounts.sales.read',return_value=loaded) as load:
  evidence,scenario=run_tool(s,v,p,s.get_dataset(v),[TABLES[0]])
  assert evidence[0]['records']==[{'sum(calc.Revenue)':130.0}]
  assert scenario['sales_versions']=={'primary':'sales-v1'}
  assert load.call_count==1

def test_router_can_repair_explicit_source_aggregation_once(accounts):
 from unittest.mock import patch
 from stock_accounts.planning_assistant import reply
 s,a,v=accounts;t=copy.deepcopy(TABLES);t[1]['rows'].append(['a',99,6,'2026-04-01'])
 bad=plan();bad['operation']='cross_sheet'
 good=copy.deepcopy(bad);good['sources'][1]={'alias':'s1','table':'T2','group_by':['SKU Code'],'metrics':[{'column':'Std DP','op':'max'}]}
 good['calculations'][0]['operands'][1]='s1.max(Std DP)'
 with patch('stock_accounts.planning_assistant.settings',return_value=('key','model')),patch('stock_accounts.planning_assistant.generate',side_effect=[bad,good,'Computed from maximum SKU prices.']) as provider:
  result=reply(s,v,t,'Calculate quantity times maximum price per SKU',[],None)
  assert result['evidence'][0]['records']==[{'sum(calc.Revenue)':575.0}]
  assert provider.call_count==3
  assert provider.call_args_list[0].args[3]['tables'][0]['id']=='T1'
  assert 'validation_error' in provider.call_args_list[1].args[3]

def test_repeated_invalid_join_returns_clarification_not_query_error(accounts):
 from unittest.mock import patch
 from stock_accounts.planning_assistant import reply
 s,a,v=accounts;bad={'operation':'cross_sheet','sources':None}
 with patch('stock_accounts.planning_assistant.settings',return_value=('key','model')),patch('stock_accounts.planning_assistant.generate',side_effect=[bad,bad]) as provider:
  result=reply(s,v,TABLES,'Compare these sources',[],None)
  assert result['evidence']==[] and 'ambiguous' in result['answer']
  assert provider.call_count==2
