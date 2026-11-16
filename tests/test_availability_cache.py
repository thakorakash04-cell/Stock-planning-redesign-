from unittest.mock import patch
import pytest
from stock_accounts.production import read,save,check_availability
from stock_accounts.store import Store
from test_stock_assistant import accounts
from test_production_materials import data

def setup(s,a):
 s.save_dataset(a,'master.xlsx',data());r=read(s,a)
 plan=save(s,a,{'kind':'upcoming','version':r['version'],'revision':0,'value':{'materialCode':'A','product':'A','description':'Size A','batch':'CACHE','quantity':100,'startDate':'2026-11-01','endDate':'2026-11-02'}})['upcoming'][0]
 return {'version':r['version'],'plan_id':plan['id'],'revision':plan['revision']}

def test_status_survives_other_users_logins_and_restart_without_recalculation(accounts):
 s,a,v=accounts;event=setup(s,a);first=check_availability(s,a,event)
 with patch('stock_accounts.production_materials.availability',side_effect=AssertionError('recalculated')):
  result=read(s,v)['upcoming'][0]['availability']
  assert result['available'] is False and result['checkedAt']==first['checkedAt']
  assert 'rows' not in result
  again=check_availability(s,v,event);assert again['rows']==first['rows']
  restarted=Store(s.url);login=restarted.login('viewer_user','Test-viewer-password!123')
  assert read(restarted,login)['upcoming'][0]['availability']['checkedAt']==first['checkedAt']
  assert check_availability(restarted,login,event)['rows']==first['rows']

def test_quantity_invalidates_but_date_edit_retains_cache(accounts):
 s,a,v=accounts;event=setup(s,a);first=check_availability(s,v,event)
 def change(qty,end,revision):return save(s,a,{'kind':'upcoming','version':event['version'],'plan_id':event['plan_id'],'revision':revision,'value':{'materialCode':'A','product':'A','description':'Size A','batch':'CACHE','quantity':qty,'startDate':'2026-11-01','endDate':end}})['upcoming'][0]
 dated=change(100,'2026-11-03',1)
 assert dated['availability']['checkedAt']==first['checkedAt'] and dated['availability']['revision']==2
 changed=change(10,'2026-11-03',2);assert 'availability' not in changed
 assert check_availability(s,v,{**event,'revision':3})['available'] is True

def test_every_master_upload_invalidates_even_identical_content(accounts):
 s,a,v=accounts;event=setup(s,a);first=check_availability(s,v,event)
 s.save_dataset(a,'identical.xlsx',data());report=read(s,v)
 assert report['version']==event['version'] and report['sourceStamp']!=first['sourceStamp']
 assert 'availability' not in report['upcoming'][0]
 with patch('stock_accounts.production_materials.availability',wraps=__import__('stock_accounts.production_materials',fromlist=['availability']).availability) as calculate:
  second=check_availability(s,v,event);assert calculate.call_count==1
  assert second['sourceStamp']==report['sourceStamp']

def test_cached_status_is_summary_only_and_still_requires_production_access(accounts):
 s,a,v=accounts;event=setup(s,a);check_availability(s,v,event)
 with patch.object(s,'run',wraps=s.run) as queries:
  summary=read(s,v)['upcoming'][0]['availability'];assert 'rows' not in summary and 'calculations' not in summary
  cache_reads=[c.args[1] for c in queries.call_args_list if c.args[1].startswith('SELECT') and 'production_availability_cache' in c.args[1]]
  assert cache_reads and all('payload' not in sql for sql in cache_reads)
 s.update_permissions(a,'viewer_user',{'menu_3':False});v=s.login('viewer_user','Test-viewer-password!123')
 with pytest.raises(PermissionError):check_availability(s,v,event)

def test_workspace_bootstrap_refreshes_saved_status_without_new_login(accounts):
 from stock_accounts import workspace
 s,a,v=accounts;event=setup(s,a);state={}
 with patch.object(workspace.st,'session_state',state),patch.object(workspace,'ui_payload',return_value=({'filename':'master.xlsx'},[],'v1')):
  first,_,_=workspace.workspace_payload(s,v);assert 'availability' not in first['production']['upcoming'][0]
  check_availability(s,v,event)
  restored,_,_=workspace.workspace_payload(s,v)
  assert restored['production']['upcoming'][0]['availability']['available'] is False

def test_permission_scope_does_not_reuse_other_scopes_details(accounts):
 s,a,v=accounts;d=data()
 bom=next(t for t in d['tables'] if t['name']=='BOM');bom['headers'].append('Source.Name')
 for row in bom['rows']:row.append('Red.xlsx')
 s.save_dataset(a,'segments.xlsx',d);report=read(s,a)
 plan=save(s,a,{'kind':'upcoming','version':report['version'],'revision':0,'value':{'materialCode':'A','product':'A','description':'Size A','batch':'SCOPED','quantity':100,'startDate':'2026-11-01','endDate':'2026-11-02'}})['upcoming'][0]
 event={'version':report['version'],'plan_id':plan['id'],'revision':1};check_availability(s,a,event)
 s.update_segments(a,'viewer_user',['Red']);v=s.login('viewer_user','Test-viewer-password!123')
 assert 'availability' not in read(s,v)['upcoming'][0]
 check_availability(s,v,event);assert 'availability' in read(s,v)['upcoming'][0]
 s.update_segments(a,'viewer_user',[]);v=s.login('viewer_user','Test-viewer-password!123')
 assert not read(s,v)['upcoming']
 with pytest.raises(ValueError,match='changed'):check_availability(s,v,event)
