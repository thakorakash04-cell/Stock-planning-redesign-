import copy
from unittest.mock import patch
import pytest
from stock_accounts.production_value import calculate
from stock_accounts.planning_assistant import run_tool
from test_stock_assistant import accounts

def data():
 return {'sheets':[],'tables':[
 {'name':'Prices','headers':['Material','Std DP','UoM'],'rows':[['a',10,'EA'],['B',20,'EA'],['A',10,'EA']]},
 {'name':'Production Order Details','headers':['Order','Material Number','Unit of measure (=GMEIN)'],'rows':[[1,'A','EA'],[2,'B','EA']]},
 {'name':'Unique Material','headers':['Material','Source.Name'],'rows':[['A','Care.xlsx'],['B','Care.xlsx']]}]}
def report():
 return {'referenceDate':'2026-10-24','segments':['Care'],'materials':[],
 'ongoing':[{'id':'one','segments':['Care'],'row':[1,'ZFGS','A','A product','A-BATCH',5,'2026-10-01','2026-11-01',4,'Estimate',None,None]}],
 'qc':{'segments':[['Care']],'rows':[['B','B product','B-BATCH',3,3,'2026-10-10',2,'ZFGS']]}}
def test_separate_status_totals_and_combined_match_exact_sku_dp():
 r=calculate(data(),report())
 assert r['summary']['rows'][-1]==['Combined',2,2,0,100,100]
 assert sorted(row[9] for row in r['details']['rows'])==[40,60]
 assert calculate(data(),report(),{'price_convention':'strict'})['complete']
 assert calculate(data(),report(),{'ongoing_quantity':'order'})['summary']['rows'][-1][-1]==110
 assert calculate(data(),report(),{'production_statuses':['ongoing']})['summary']['rows'][-1][-1]==40
def test_missing_quantity_conflicting_price_and_units_are_unvalued():
 d=data();r=report();r['ongoing'][0]['row'][8]=None
 out=calculate(d,r);assert not out['complete']
 assert out['summary']['rows'][-1][-2:]==[60,None]
 d['tables'][0]['rows'].append(['B',30,'EA'])
 assert calculate(d,r)['summary']['rows'][-1][-2:]==[0,None]
 d=data();d['tables'][0]['rows'][1][2]='BOX'
 assert not calculate(d,report(),{'price_convention':'strict'})['complete']
 assert calculate(d,report())['complete']
def test_overlapping_batch_and_duplicate_qc_orders_are_not_counted_twice():
 r=report();r['qc']['rows'].append(copy.deepcopy(r['qc']['rows'][0]));r['qc']['segments'].append(['Care'])
 r['qc']['rows'].append(['A','A product','A-BATCH',2,2,'2026-10-10',1,'ZFGS']);r['qc']['segments'].append(['Care'])
 out=calculate(data(),r)
 assert out['summary']['rows'][-1][-1]==80
 assert all(row[0]=='Under QC' for row in out['details']['rows'])
def test_tool_is_read_only_and_requires_production_and_price_access(accounts):
 s,a,v=accounts;d=data();s.save_dataset(a,'master.xlsx',d);current=s.get_dataset(v);before=copy.deepcopy(current)
 with patch('stock_accounts.production.read',return_value=report()) as read:
  evidence,scenario=run_tool(s,v,{'operation':'production_value'},current)
  assert scenario['complete'] and evidence[0]['records'][-1]['Complete Potential Value']==100
  assert read.call_args.kwargs['archive'] is False
 assert current==before
 s.update_permissions(a,'viewer_user',{'menu_1':False});v=s.login('viewer_user','Test-viewer-password!123')
 with pytest.raises(PermissionError):run_tool(s,v,{'operation':'production_value'},s.get_dataset(v))
