import pytest
from unittest.mock import patch
from test_stock_assistant import accounts
from stock_accounts.access import allowed,MENU_LABELS
from stock_accounts.auth import PERMISSION_LABELS
from stock_accounts.store import AccessDenied
from stock_accounts.account_admin import save_member
from stock_accounts.workspace_insights import handle_request,ui_payload
from stock_accounts.production import save

def test_floor_rights_are_listed_saved_and_enforced_before_cache_reads(accounts):
 store,admin,viewer=accounts
 assert len(MENU_LABELS)==14
 assert 'Issue Slip' in PERMISSION_LABELS['menu_12']
 assert 'New Production Batch Required' in PERMISSION_LABELS['menu_13']
 save_member(store,admin,{'username':'viewer_user','permissions':{'menu_12':False,'menu_13':False}})
 viewer=store.login('viewer_user','Test-viewer-password!123');identity=store.identity(viewer)
 assert not allowed(identity,12) and not allowed(identity,13)
 payload=ui_payload(None,identity)[0]
 assert 12 not in payload['accessibleTabs'] and 13 not in payload['accessibleTabs']
 with patch('stock_accounts.pending_sales.read',side_effect=AssertionError('Disabled feature cannot read cached data')):
  with pytest.raises(AccessDenied):handle_request(store,viewer,{'action':'pending_sales_read','known_stamp':'cached'})
 with pytest.raises(AccessDenied):handle_request(store,viewer,{'action':'issue_slip_dataset','known_stamp':'cached'})
 save_member(store,admin,{'username':'viewer_user','permissions':{'menu_12':True,'menu_13':True}})
 viewer=store.login('viewer_user','Test-viewer-password!123');identity=store.identity(viewer)
 assert allowed(identity,12) and allowed(identity,13)
 assert {12,13}.issubset(ui_payload(None,identity)[0]['accessibleTabs'])

def test_child_switches_preserve_parent_access_and_legacy_defaults():
 identity={'role':'viewer','permissions':{'menu_0':True,'menu_3':True}}
 assert allowed(identity,12) and allowed(identity,13)
 identity['permissions']['menu_3']=False;assert not allowed(identity,12) and allowed(identity,13)
 identity['permissions']['menu_0']=False;assert not allowed(identity,13)

def test_disabled_demand_feature_cannot_create_origin_plan(accounts):
 store,admin,viewer=accounts
 store.update_permissions(admin,'viewer_user',{'edit_upcoming':True,'menu_3':True,'menu_13':False})
 viewer=store.login('viewer_user','Test-viewer-password!123');current=store.get_dataset(viewer)
 with pytest.raises(AccessDenied):save(store,viewer,{'kind':'upcoming','version':current['version'],'revision':0,'value':{'quantity':1,'endDate':'2026-11-10','startDate':'2026-11-09','demandStamp':'x'}})
