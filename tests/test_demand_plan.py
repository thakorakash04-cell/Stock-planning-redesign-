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


def test_suggestion_and_source_uploads_are_server_captured_and_preserved_on_edit(accounts):
 import json
 from stock_accounts import pending_sales as pending
 store,admin,viewer=accounts;event=setup(store,admin);current=store.get_dataset(admin)
 pending.schema(store)
 source={'filename':'Open-orders.xlsx','version':'orders-v1','updated_at':1234.,'dataUpTo':'2026-11-03'}
 with store.transaction() as db:store.run(db,"INSERT INTO stock_open_orders VALUES('current',?,?,?,?,?)",('Open-orders.xlsx','orders-v1',1234.,'admin_user',pending.pack({})))
 demand={'stamp':'demand1','source':source,'result':{'rows':[['A','Product',60,'EA','Credit Hold No Stock: 20; Forecast demand: 40']]}}
 event['value'].update(demandMaterial='A',demandUnit='EA',demandProvenance={'suggestion':'forged'},demandReason='Reviewed batch quantity')
 with patch('stock_accounts.pending_sales.context',return_value=('demand1',{},source)),patch('stock_accounts.pending_sales.read',return_value=demand):
  item=save(store,admin,event)['upcoming'][0]
 original=item['demandProvenance']
 assert original['suggestion']==demand['result']['rows'][0][4] and original['requiredQuantity']==60
 assert original['sources'][0]['filename']=='master.xlsx' and original['sources'][0]['updated_at']==current['updated_at']
 assert original['sources'][1]['filename']=='Open-orders.xlsx' and original['sources'][1]['updated_at']==1234.
 with store.transaction() as db:
  store.run(db,"UPDATE datasets SET filename='New-master.xlsx',updated_at=updated_at+100 WHERE id='current'")
  store.run(db,"UPDATE stock_open_orders SET updated_at=9999 WHERE id='current'")
 value={k:v for k,v in event['value'].items() if k not in ('demandStamp','demandMaterial','demandUnit')};value.update(quantity=30,demandReason='Edited remark',demandProvenance={'sources':[]})
 item=save(store,admin,{**event,'revision':1,'value':value})['upcoming'][0]
 assert item['demandProvenance']==original and item['demandReason']=='Edited remark'
 with store.transaction() as db:
  stored=json.loads(store.run(db,"SELECT payload FROM production_shared WHERE id=?",(event['plan_id'],)).fetchone()['payload'])
 assert stored['demandProvenance']==original


def test_unmatched_requirement_or_source_race_cannot_save_fabricated_provenance(accounts):
 from stock_accounts.demand_provenance import capture
 store,admin,_=accounts;event=setup(store,admin);event['value'].update(demandMaterial='A',demandUnit='EA')
 demand={'stamp':'demand1','source':None,'result':{'rows':[['A','Product',60,'EA','Forecast demand: 60']]}}
 with patch('stock_accounts.pending_sales.context',return_value=('demand1',{},None)),patch('stock_accounts.pending_sales.read',return_value={**demand,'result':{'rows':[]}}):
  with pytest.raises(ValueError,match='no longer available'):save(store,admin,event)
 def changed(*args):
  result=capture(*args)
  with store.transaction() as db:store.run(db,"UPDATE datasets SET updated_at=updated_at+100 WHERE id='current'")
  return result
 with patch('stock_accounts.pending_sales.context',return_value=('demand1',{},None)),patch('stock_accounts.pending_sales.read',return_value=demand),patch('stock_accounts.demand_provenance.capture',side_effect=changed):
  with pytest.raises(ValueError,match='source files changed'):save(store,admin,event)
 assert not read(store,admin)['upcoming']
