from unittest.mock import patch
import pytest
from test_stock_assistant import accounts
from test_production import fixture
from stock_accounts.production import save,read
from stock_accounts.store import AccessDenied


def setup(store,admin):
 store.save_dataset(admin,'master.xlsx',fixture())
 return {'kind':'upcoming','version':read(store,admin)['version'],'revision':0,'plan_id':'a'*32,'value':{'materialCode':'A','product':'A','description':'Size A','batch':'DEMAND1','quantity':25,'startDate':'2026-11-10','endDate':'2026-11-20','demandReason':'Credit Hold No Stock · A · requirement 25 EA','demandStamp':'demand1'}}
def test_demand_plan_note_saved_editable_and_preserved_for_legacy_clients(accounts):
 store,admin,viewer=accounts;event=setup(store,admin)
 with patch('stock_accounts.pending_sales.context',return_value=('demand1',{},None)):
  result=save(store,admin,event)
 item=result['upcoming'][0]
 assert item['demandReason']==event['value']['demandReason']
 assert item['row'][3]==25 and item['materialCode']=='A'
 # The existing row schema and final Segment position remain unchanged.
 assert len(item['row'])==len(result['upcomingHeaders'])==9
 value={k:v for k,v in event['value'].items() if k not in ('demandReason','demandStamp')};value['quantity']=30
 result=save(store,admin,{**event,'revision':1,'value':value})
 assert result['upcoming'][0]['demandReason']==item['demandReason']
 value['demandReason']='Forecast demand · reviewed'
 result=save(store,admin,{**event,'revision':2,'value':value})
 assert result['upcoming'][0]['demandReason']=='Forecast demand · reviewed'
def test_stale_demand_and_edit_denial_do_not_create_plan(accounts):
 store,admin,viewer=accounts;event=setup(store,admin)
 with patch('stock_accounts.pending_sales.context',return_value=('changed',{},None)):
  with pytest.raises(ValueError,match='Demand data changed'):save(store,admin,event)
 assert not read(store,admin)['upcoming']
 with pytest.raises(AccessDenied):save(store,viewer,event)
 assert not read(store,admin)['upcoming']
def test_retry_uses_same_plan_identity_and_cannot_create_second_plan(accounts):
 store,admin,viewer=accounts;event=setup(store,admin)
 with patch('stock_accounts.pending_sales.context',return_value=('demand1',{},None)):
  save(store,admin,event)
  with pytest.raises(ValueError,match='Someone else changed'):save(store,admin,event)
 assert len(read(store,admin)['upcoming'])==1
