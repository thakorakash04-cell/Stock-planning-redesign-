from unittest.mock import patch
from test_stock_assistant import accounts
from stock_accounts.workspace import decorate_workspace
from stock_accounts.workspace_delivery import payload,prepared

def test_old_cached_menu_is_repaired_without_rebuilding_rows(accounts):
 s,a,v=accounts
 for actor in (a,v):
  identity=s.identity(actor);rows=[]
  old={'accessibleTabs':list(range(12)),'sheets':rows}
  with patch('stock_accounts.pending_sales.read',return_value=None),patch('stock_accounts.product_catalog.read',return_value={}):
   result=decorate_workspace(s,actor,old,catalog_version='test',identity=identity)
  assert {12,13}.issubset(result['accessibleTabs'])
  assert result['sheets'] is rows and 12 not in old['accessibleTabs']
  before=payload({},None,old,[],'v',identity)
  after=payload({},None,result,[],'v',identity)
  assert before['contentId']!=after['contentId']
  assert before['bootstrapId']!=after['bootstrapId']

def test_prepared_cache_separates_new_floor_permissions(accounts):
 s,a,v=accounts;current={'version':'v','updated_at':1,'data':{}}
 identity=s.identity(v)
 def builder(current,identity,overrides):
  from stock_accounts.access import allowed
  return {'accessibleTabs':[i for i in range(14) if allowed(identity,i)]},[],'v'
 first=prepared(s,current,identity,[],builder)[0]
 disabled={**identity,'permissions':{**identity['permissions'],'menu_12':False,'menu_13':False}}
 second=prepared(s,current,disabled,[],builder)[0]
 assert {12,13}.issubset(first['accessibleTabs'])
 assert not {12,13}.intersection(second['accessibleTabs'])
