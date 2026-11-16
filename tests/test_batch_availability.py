from unittest.mock import patch
import pytest
from stock_accounts.batch_availability import calculate,check
from stock_accounts.production import read,save
from stock_accounts.store import Store
from test_stock_assistant import accounts
from test_production_materials import data

def item(id,qty,start='2026-11-01',code='A'):
 return {'id':id,'revision':1,'materialCode':code,'row':[code,'Product',id,qty,start,'2026-11-30']}

def test_shared_material_is_not_counted_available_for_each_plan_separately():
 result=calculate(data(),[item('later',20,'2026-11-02'),item('first',20)])
 assert result['planStatuses']=={'first':'Ready','later':'Material shortage'}
 rm=next(r for r in result['rows'] if r[0]=='RM')
 assert rm[3:6]==[12,10,2]
 assert result['planRows'][1][-1]=='RM: 2.0 EA'

def test_blocked_plan_does_not_consume_partial_stock():
 d=data();stocks=next(t for t in d['tables'] if t['name']=='Stock Data');stocks['rows'][1][2]=0
 bom=next(t for t in d['tables'] if t['name']=='BOM')
 bom['rows'].append(['B','Second','RM','Raw','ZRAW',1,1,'EA',2,1,10,10,0])
 result=calculate(d,[item('blocked',10),item('ready',9,'2026-11-02','B')])
 assert result['planStatuses']=={'blocked':'Material shortage','ready':'Ready'}

def test_unverifiable_units_and_missing_bom_are_not_ready():
 d=data();bom=next(t for t in d['tables'] if t['name']=='BOM')
 bom['rows'].append(['B','Second','RM','Raw','ZRAW',1,1,'KG',2,1,10,10,0])
 result=calculate(d,[item('a',1),item('b',1,code='B'),item('missing',1,code='NO-BOM')])
 assert set(result['planStatuses'].values())=={'Cannot verify'}

def setup(s,a):
 s.save_dataset(a,'master.xlsx',data());version=read(s,a)['version']
 for batch,start in [('ONE','2026-11-01'),('TWO','2026-11-02')]:
  save(s,a,{'kind':'upcoming','version':version,'revision':0,'value':{'materialCode':'A','product':'A','description':'Size A','batch':batch,'quantity':20,'startDate':start,'endDate':'2026-11-10'}})
 return {'version':version}

def test_combined_cache_relogin_restart_and_date_changes(accounts):
 s,a,v=accounts;event=setup(s,a);first=check(s,a,event)
 assert set(first['planStatuses'].values())=={'Ready','Material shortage'}
 with patch('stock_accounts.batch_availability.calculate',side_effect=AssertionError('recalculated')):
  summary=read(s,v)['batchAvailability']
  assert summary['checkedAt']==first['checkedAt'] and 'rows' not in summary
  assert check(s,v,event)==first
  restarted=Store(s.url);actor=restarted.login('viewer_user','Test-viewer-password!123')
  assert check(restarted,actor,event)==first
 report=read(s,a);plan=report['upcoming'][0]
 save(s,a,{'kind':'upcoming','version':event['version'],'plan_id':plan['id'],'revision':plan['revision'],'value':{'materialCode':'A','product':'A','description':'Size A','batch':plan['row'][2],'quantity':20,'startDate':'2026-11-03','endDate':'2026-11-10'}})
 assert read(s,v)['batchAvailability'] is None
 assert check(s,v,event)['signature']!=first['signature']
 s.save_dataset(a,'identical.xlsx',data())
 assert read(s,v)['batchAvailability'] is None
 assert check(s,v,event)['sourceStamp']!=first['sourceStamp']
 s.update_permissions(a,'viewer_user',{'menu_3':False});actor=s.login('viewer_user','Test-viewer-password!123')
 with pytest.raises(PermissionError):check(s,actor,event)

def test_aggregate_results_do_not_cross_segment_scope(accounts):
 s,a,v=accounts;event=setup(s,a);check(s,a,event)
 s.update_segments(a,'viewer_user',[]);v=s.login('viewer_user','Test-viewer-password!123')
 result=check(s,v,event)
 assert result['planRows']==[] and result['rows']==[] and not result['available']

def test_assistant_uses_same_calculation_without_modifying_plans(accounts):
 from stock_accounts.planning_assistant import run_tool
 s,a,_=accounts;event=setup(s,a)
 before=read(s,a)['upcoming']
 result=run_tool(s,a,{'operation':'upcoming_availability'},s.get_dataset(a))
 evidence,scenario=result
 assert scenario['operation']=='upcoming_availability'
 assert len(evidence)==3 and evidence[0]['matched_records']==2
 assert read(s,a)['upcoming']==before

def test_concurrent_plan_change_rejects_stale_allocation(accounts):
 import stock_accounts.batch_availability as module
 s,a,_=accounts;event=setup(s,a);original=module.calculate
 def change(data,items):
  result=original(data,items);p=items[0]
  save(s,a,{'kind':'upcoming','version':event['version'],'plan_id':p['id'],'revision':p['revision'],'value':{'materialCode':'A','product':'A','description':'Size A','batch':p['row'][2],'quantity':21,'startDate':p['row'][4],'endDate':p['row'][5]}})
  return result
 with patch.object(module,'calculate',side_effect=change):
  with pytest.raises(ValueError,match='plans changed'):check(s,a,event)
 assert read(s,a)['batchAvailability'] is None
