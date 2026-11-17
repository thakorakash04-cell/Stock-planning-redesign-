import copy
from unittest.mock import patch
from stock_accounts.demand_readiness import build,READY,SHORT,ORDER,UNKNOWN
from test_production_materials import data
from test_pending_sales import Store,ACTOR,upload,orders
from stock_accounts import pending_sales as pending

def requirement(qty=100,unit='EA'):
 return [['A','Product A',qty,unit]]

def value(d,qty=100,unit='EA'):
 return build(d,requirement(qty,unit))['a'][unit]

def test_three_statuses_bom_base_and_duplicate_stock_not_double_counted():
 d=data();v=value(d)
 assert v['status']==SHORT
 assert v['rows'][0][3:8]==[30,10,5,10000,0]
 assert value(d,10)['status']==READY
 # Current stock already includes 5 QC: 15 requirement remains short at stock10.
 assert value(d,50)['status']==SHORT
 d['tables'][-2]['rows'][0][-1]=19
 v=value(d)
 assert v['status']==ORDER and v['rows'][0][7]==1
 assert d['tables'][-2]['rows'][0][6]==3


def test_actual_purchase_lines_are_summed_once_and_override_joined_totals():
 d=data();d['tables'].append({'name':'Order List','headers':['Material','Purchasing Document','Item','Still to be delivered (qty)'],'rows':[['RM','P1',10,6],['RM','P1',10,6],['RM','P1',20,7],['OTHER','P2',10,900]]})
 assert value(d)['rows'][0][6:9]==[13,7,ORDER]
 d['tables'][-1]['rows'][1][-1]=99
 assert value(d)['status']==UNKNOWN


def test_missing_bom_stock_onorder_units_and_alternatives_cannot_claim_ready():
 d=data();d['tables'][-2]['rows']=[]
 assert value(d)['status']==UNKNOWN
 d=data();d['tables'][-2]['rows'][0][5]=None
 assert value(d)['status']==UNKNOWN
 d=data();d['tables'][-1]['rows'][0][-1]='KG'
 assert value(d)['status']==UNKNOWN
 d=data();d['tables'][-2]['rows'][0][-1]=None
 assert value(d)['status']==UNKNOWN
 assert value(d,10)['status']==READY # Stock covers demand; PO history is unnecessary.
 d=data();d['tables'][-2]['rows'][1][9]=2
 assert value(d)['status']==UNKNOWN
 d=data();d['tables'][-2]['headers'].append('Base unit of measure')
 for r in d['tables'][-2]['rows']:r.append('EA')
 assert value(d,100,'BOX')['status']==UNKNOWN


def test_readiness_is_durable_cached_and_workbook_changes_refresh_it():
 s=Store();d=data();d['sheets'][0]['name']='Summary';d['sheets'][0]['rows']=[['A','Product',0]];d['sheets'][0]['headers']=['Material','Description','Current FG Stock']
 # Keep the demand fixture schema, with A as its SKU and no forecast demand.
 source=orders();source['rows']=[['1','10','A','Product','Release_No Stock',100,'EA']]
 d['tables'].append({'name':'Units','headers':['Material','Base unit of measure','Source.Name'],'rows':[['A','EA','A']]})
 d['sheets']=[d['sheets'][0]]+[{'name':str(i),'headers':[],'rows':[]} for i in range(1,5)]
 s.db.execute("UPDATE datasets SET payload=?",(pending.pack(d),));s.data=d
 with patch.object(pending,'parse',return_value=source):pending.save(s,ACTOR,{'filename':'Orders.xlsx','content':'ZmlsZQ==','expected':None})
 first=pending.read(s,ACTOR)
 assert first['result']['materialReadiness']['a']['EA']['status']==SHORT
 s._pending_sales_values.clear()
 with patch('stock_accounts.demand_readiness.build',side_effect=AssertionError('Must restore cached checks')):
  assert pending.read(s,ACTOR)['result']['materialReadiness']==first['result']['materialReadiness']
  assert pending.read(s,ACTOR,{'known_stamp':first['stamp']})['not_modified']
 d['tables'][-2]['rows'][0][1:3]=[50,5]
 s.db.execute("UPDATE datasets SET version='master2',updated_at=2,payload=?",(pending.pack(d),));s._dataset_payload_cache=None
 refreshed=pending.read(s,ACTOR)
 assert refreshed['result']['materialReadiness']['a']['EA']['status']==READY
 s.member={'role':'viewer','permissions':{'menu_0':True,'menu_4':True,'menu_3':False},'allowedSegments':None}
 assert pending.read(s,ACTOR)['result']['materialReadiness']=={}
