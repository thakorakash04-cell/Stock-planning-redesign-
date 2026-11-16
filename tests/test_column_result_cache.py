import copy
from unittest.mock import patch
import pytest
from test_stock_assistant import accounts
from test_table_columns import BASE,TABLES,plan
from stock_accounts import table_columns as cols
from stock_accounts import column_result_cache as cache
from stock_accounts.store import AccessDenied,Store

def event(s,a):return {'action':'table_column_plan','scope':'main:Stock', 'headers':BASE['headers'],'rows':BASE['rows'],'question':'Quantity times standard price','version':s.get_dataset(a)['version'],'consent':True}
def add(s,a):
 e=event(s,a)
 with patch.object(cols,'source_tables',return_value=(TABLES,e['version'])),patch.object(cols,'settings',return_value=('key','model')),patch.object(cols,'generate',return_value={'name':'Amount','plan':plan()}):result=cols.handle(s,a,e)
 assert result['cache_stored'] is True
 return e,result

def test_fresh_store_and_login_load_values_without_sources_calculator_or_gemini(accounts):
 from stock_accounts.preferences import read
 s,a,v=accounts;e,result=add(s,a)
 fresh=Store(s.url)
 actor=fresh.login('admin_user','Test-admin-password!123')
 definitions=read(fresh,actor)['columns:main:Stock']['definitions']
 with patch.object(cols,'source_tables',side_effect=AssertionError('Loaded sources')),patch.object(cols,'resolve',side_effect=AssertionError('Recalculated')),patch.object(cols,'generate',side_effect=AssertionError('Called Gemini')):
  restored=cols.handle(fresh,actor,{**e,'action':'table_columns_resolve','definitions':definitions,'consent':False})
 assert restored['cached'] is True and restored['columns']==result['columns']
 assert restored['columns'][0]['values']==[20,0,None]

def test_workbook_update_changes_fingerprint_and_recalculates_once(accounts):
 s,a,v=accounts;e,first=add(s,a);defs=[first['definition']]
 s.save_dataset(a,'updated.xlsx',s.get_dataset(a)['data']);version=s.get_dataset(a)['version']
 new=copy.deepcopy(TABLES);new[0]['rows'][0][1]=12
 with patch.object(cols,'source_tables',return_value=(new,version)) as source,patch.object(cols,'generate') as ai:
  refreshed=cols.handle(s,a,{**e,'version':version,'action':'table_columns_resolve','definitions':defs})
  assert refreshed['columns'][0]['values']==[24,0,None] and source.call_count==1
  again=cols.handle(s,a,{**e,'version':version,'action':'table_columns_resolve','definitions':defs})
  assert again['cached'] and again['columns']==refreshed['columns'] and source.call_count==1
  ai.assert_not_called()

def test_scope_definition_row_order_and_permission_invalidation(accounts):
 s,a,v=accounts;e,first=add(s,a);defs=[first['definition']]
 with patch.object(cols,'source_tables',return_value=(TABLES,e['version'])) as source:
  reversed_rows=cols.handle(s,a,{**e,'rows':list(reversed(e['rows'])),'action':'table_columns_resolve','definitions':defs})
  assert source.call_count==1 and reversed_rows['columns'][0]['values']==[None,0,20]
  other_scope=cols.handle(s,a,{**e,'scope':'main:Other','action':'table_columns_resolve','definitions':defs})
  assert source.call_count==2 and other_scope['columns'][0]['values']==[20,0,None]
  changed=copy.deepcopy(defs);changed[0]['name']='Different'
  renamed=cols.handle(s,a,{**e,'action':'table_columns_resolve','definitions':changed})
  assert source.call_count==3 and renamed['columns'][0]['name']=='Different'
  # Another user cannot obtain the administrator's cached result.
  cols.handle(s,v,{**e,'action':'table_columns_resolve','definitions':defs})
  assert source.call_count==4
 s.update_permissions(a,v.username,{'use_tools':False});v=s.login(v.username,'Test-viewer-password!123')
 with pytest.raises(AccessDenied):cols.handle(s,v,{**e,'action':'table_columns_resolve','definitions':defs})

def test_relevant_source_revision_invalidates_cached_values(accounts):
 s,a,v=accounts;e,first=add(s,a)
 actual=cols.revision
 with patch.object(cols,'revision',side_effect=lambda *args:actual(*args)+'changed'),patch.object(cols,'source_tables',return_value=(TABLES,e['version'])) as sources:
  result=cols.handle(s,a,{**e,'action':'table_columns_resolve','definitions':[first['definition']]})
 assert sources.call_count==1 and result.get('cached') is not True

def test_corrupt_and_oversized_cache_entries_do_not_replace_calculation(accounts):
 s,a,v=accounts;e,first=add(s,a)
 with s.transaction() as db:s.run(db,'UPDATE user_column_results SET payload=? WHERE username=?',('invalid gzip',a.username))
 with patch.object(cols,'source_tables',return_value=(TABLES,e['version'])) as source:
  restored=cols.handle(s,a,{**e,'action':'table_columns_resolve','definitions':[first['definition']]})
 assert source.call_count==1 and restored['columns']==first['columns']
 with patch.object(cache,'MAX_RAW',1):assert cache.write(s,a,'test','key',first) is False
