import base64,copy,sqlite3
from contextlib import contextmanager
from unittest.mock import patch
from types import SimpleNamespace
ACTOR=SimpleNamespace(username="user",session_id="session")
import pytest
from stock_accounts import pending_sales as p

def dataset():
 sheets=[{'name':'Summary','headers':['Material','Description','Current FG Stock'],'rows':[['FG1','Product',30],['FG2','Other',20]]}]
 sheets += [{'name':str(i),'headers':[],'rows':[]} for i in range(1,4)]
 sheets += [{'name':'Forecast Planning','headers':['Material','Text','Year','Month','Forecast','Transfer','Stock','Pending'],'rows':[['FG1','Product',2026,'Nov',100,10,30,60],['FG1','Product',2026,'Dec',20,0,30,-10]]}]
 return {'sheets':sheets,'tables':[{'name':'Units','headers':['Material','Base unit of measure','Source.Name'],'rows':[['FG1','EA','A'],['FG2','BOX','B']]}]}
def orders():
 headers=['Sales Document','Sales Document Item','Material','Description','Remarks','Pending Qty','Sales unit']
 return {'name':'Master','headers':headers,'indexes':{p.norm(h):i for i,h in enumerate(headers)},'rows':[['1','10','FG1','Product','Release_No Stock',20,'EA'],['2','10','FG1','Product','Credit Hold_No Stock',50,'EA'],['3','10','FG1','Product','Credit Hold_Available',900,'EA'],['4','10','FG1','Product','Release_Pricing Issue',800,'EA'],['5','10','FG2','Other','Release_No Stock',10,'BOX']]}
ADMIN={'role':'admin','permissions':{},'allowedSegments':None}
def test_sales_and_forecast_combine_with_traceable_breakdown():
 result=p.build(dataset(),orders(),ADMIN)
 assert result['summary']['fg1']['quantity']==150
 assert result['summary']['fg2']['quantity']==10
 assert result['rows']==[['FG1','Product',120.,'EA','Credit Hold No Stock: 40; Forecast demand: 80',150.,30.,'A']]
 assert result['summary']['fg1']['salesQuantity']==70
 assert result['summary']['fg1']['forecastQuantity']==80
 assert [d['quantity'] for d in result['summary']['fg1']['breakdown']]==[20,50,80]
 assert [d['requiredQuantity'] for d in result['summary']['fg1']['breakdown']]==[0,40,80]
 assert not result['warnings']
def test_release_shortage_then_hold_does_not_subtract_stock_twice():
 d=dataset();d['sheets'][0]['rows'][0][2]=5
 result=p.build(d,orders(),ADMIN);sales=[r for r in result['components'] if r[4]!='Forecast demand']
 assert [(r[4],r[2],r[6]) for r in sales]==[('Credit Release No Stock',15,5),('Credit Hold No Stock',50,0)]
 assert sum(r[2] for r in sales)==70-5
def test_unit_mismatch_and_missing_stock_never_invent_conversion():
 o=orders();o['rows'][0][-1]='BOX';result=p.build(dataset(),o,ADMIN)
 assert result['summary']['fg1']['quantity'] is None
 assert any('sales unit BOX' in w for w in result['warnings'])
 assert not any(r[0]=='FG1' and r[3]=='BOX' for r in result['components'])
 d=dataset();d['sheets'][0]['rows']=[];result=p.build(d,orders(),ADMIN)
 assert not any(r[4]!='Forecast demand' for r in result['components'])
 assert any('missing or ambiguous' in w for w in result['warnings'])
def test_scope_and_forecast_permission():
 user={'role':'viewer','permissions':{'menu_0':True,'menu_4':False},'allowedSegments':['A']}
 result=p.build(dataset(),orders(),user)
 assert set(result['summary'])=={'fg1'}
 assert all(r[4]!='Forecast demand' for r in result['components'])
 user['allowedSegments']=[];assert not p.build(dataset(),orders(),user)['summary']

class Store:
 def __init__(self):
  self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
  self.db.execute('CREATE TABLE datasets(id TEXT,version TEXT,updated_at DOUBLE PRECISION,filename TEXT,payload TEXT)');self.member=copy.deepcopy(ADMIN);self.data=dataset();self.db.execute("INSERT INTO datasets VALUES('current','master1',1,'master.xlsx',?)",(p.pack(self.data),))
 @contextmanager
 def transaction(self):
  try:yield self.db;self.db.commit()
  except BaseException:self.db.rollback();raise
 def require(self,db,actor,admin=False):
  if getattr(actor,'username',None)!='user' or admin and self.member['role']!='admin':raise PermissionError('Denied')
  return self.member
 def run(self,db,sql,args=()):return db.execute(sql,args)
 def identity(self,actor):return self.require(self.db,actor)
 def get_dataset(self,actor):self.require(self.db,actor);return {'data':self.data,'version':'master1'}
 def _log(self,*a,**k):pass
 def require_permission(self,actor,permission):
  if self.member['role']!='admin':raise PermissionError('Denied')
def upload(store,expected=None):
 with patch.object(p,'parse',return_value=orders()):return p.save(store,ACTOR,{'filename':'Orders.xlsx','content':base64.b64encode(b'file').decode(),'expected':expected})
def test_persistent_cache_metadata_only_restore_and_version_invalidation():
 s=Store();upload(s);first=p.read(s,ACTOR);queries=[];s.db.set_trace_callback(queries.append)
 assert p.read(s,ACTOR,{'known_stamp':first['stamp']})=={'stamp':first['stamp'],'not_modified':True}
 assert not any('payload' in q.casefold() for q in queries)
 s._pending_sales_values.clear()
 with patch.object(p,'build',side_effect=AssertionError('Must use persisted snapshot')):assert p.read(s,ACTOR)['result']==first['result']
 s.db.execute("UPDATE datasets SET version='master2'")
 assert p.read(s,ACTOR)['stamp']!=first['stamp']
 old=p.info(s,ACTOR)['version'];upload(s,old)
 assert p.read(s,ACTOR)['source']['version']==old
 with pytest.raises(ValueError,match='changed'):upload(s,'wrong-version')
def test_permissions_and_stale_evidence():
 s=Store();upload(s);first=p.read(s,ACTOR)
 e=p.records(s,ACTOR,{'material':'FG1','stamp':first['stamp'],'source':'orders'})
 assert len(e['rows'])==2 and sum(r[5] for r in e['rows'])==70
 with pytest.raises(ValueError):p.records(s,ACTOR,{'material':'PRIVATE','stamp':first['stamp']})
 with pytest.raises(ValueError,match='changed'):p.records(s,ACTOR,{'material':'FG1','stamp':'old'})
 s.member={'role':'viewer','permissions':{'menu_0':False},'allowedSegments':None}
 with pytest.raises(PermissionError):p.read(s,ACTOR,{'known_stamp':first['stamp']})
 with pytest.raises(PermissionError):upload(s)

def test_parser_preserves_all_source_columns_and_checks_duplicate_order_items():
 class Sheet:
  title='Master';sheet_state='visible';max_row=3;max_column=7
  def __init__(self,rows):self.rows=rows
  def iter_rows(self,min_row=1,**kwargs):return iter(self.rows[min_row-1:])
 class Workbook:
  def __init__(self,rows):self.sheet=Sheet(rows)
  def __iter__(self):return iter([self.sheet])
  def close(self):pass
 value=orders();rows=[value['headers'],*value['rows'][:2]]
 with patch('stock_accounts.pnl_import.open_saved',return_value=Workbook(rows)):
  parsed=p.parse(b'file','Orders.xlsx');assert len(parsed['rows'])==2;assert parsed['headers']==value['headers']
 with patch('stock_accounts.pnl_import.open_saved',return_value=Workbook([rows[0],rows[1],rows[1]])):
  with pytest.raises(ValueError,match='Duplicate'):p.parse(b'file','Orders.xlsx')
 bad=copy.deepcopy(rows);bad[1][5]=-1
 with patch('stock_accounts.pnl_import.open_saved',return_value=Workbook(bad)):
  with pytest.raises(ValueError,match='non-negative'):p.parse(b'file','Orders.xlsx')


def test_negative_fg_stock_increases_literal_sales_deficit():
 d=dataset();d['sheets'][0]['rows'][0][2]=-5
 result=p.build(d,orders(),ADMIN)
 assert sum(r[2] for r in result['components'] if r[4]!='Forecast demand')==75

def test_cache_survives_day_change_and_rechecks_download_permission():
 s=Store();upload(s);first=p.read(s,ACTOR)
 with patch.object(p.time,'time',return_value=10**10):assert p.read(s,ACTOR,{'known_stamp':first['stamp']})['not_modified']
 s.member={'role':'viewer','permissions':{'menu_0':True,'menu_4':True},'allowedSegments':None}
 current=p.read(s,ACTOR)
 with pytest.raises(PermissionError):p.records(s,ACTOR,{'material':'FG1','stamp':current['stamp'],'source':'orders','export':True})

def test_bootstrap_and_browser_snapshot_identity_include_demand_stamp():
 from stock_accounts.workspace_delivery import payload
 member={'username':'user','role':'admin','permissions':{},'allowedSegments':None}
 state={};data={'productCatalogue':{'version':'catalog1'},'portal':{},'pendingSales':{'stamp':'orders1'}}
 first=payload(state,None,data,[],'master1',member)
 data['pendingSales']['stamp']='orders2';second=payload(state,None,data,[],'master1',member)
 assert first['bootstrapId']!=second['bootstrapId']
 assert first['contentId']!=second['contentId']


def test_assistant_tool_reuses_same_read_only_demand_calculation():
 from stock_accounts.planning_assistant import run_tool
 s=Store();upload(s);current=s.get_dataset(ACTOR)
 evidence,scenario=run_tool(s,ACTOR,{'operation':'pending_batch_requirements'},current)
 assert evidence[0]['_table']['rows']==p.read(s,ACTOR)['result']['rows']
 assert scenario['operation']=='pending_batch_requirements'


def test_shared_sku_totals_require_full_segment_visibility_including_drills():
 s=Store();s.data['tables'][0]['rows'].append(['FG1','EA','B']);s.db.execute("UPDATE datasets SET payload=?",(p.pack(s.data),));upload(s)
 s.member={'role':'viewer','permissions':{'menu_0':True,'menu_4':True},'allowedSegments':['A']}
 report=p.read(s,ACTOR)
 assert 'fg1' not in report['result']['summary']
 assert 'fg1' not in report['result']['visibleStock']
 with pytest.raises(ValueError,match='visible demand'):p.records(s,ACTOR,{'material':'FG1','stamp':report['stamp']})


def test_forecast_only_material_and_breakdown_totals():
 s=Store();report=p.read(s,ACTOR)
 assert report['result']['summary']['fg1']['quantity']==80
 assert report['result']['rows'][0][2]==80
 upload(s);report=p.read(s,ACTOR)
 details=p.records(s,ACTOR,{'material':'FG1','stamp':report['stamp'],'source':'breakdown'})
 assert sum(r[2] for r in details['rows'])==150
 assert sum(r[3] for r in details['rows'])==120
 release=p.records(s,ACTOR,{'material':'FG1','stamp':report['stamp'],'source':'orders','reason':'Credit Release No Stock','unit':'EA'})
 assert len(release['rows'])==1 and release['rows'][0][5]==20


def test_stock_metadata_matches_bom_pack_source_without_orders():
 d=dataset();d['tables'].append({'name':'DP MRP','headers':['Material','Pack Size'],'rows':[['FG1',10],['FG1',10],['FG2',20],['FG2',30]]})
 result=p.build(d,None,ADMIN)
 assert result['productDetails']['fg1']=={'unit':'EA','packSize':10}
 assert result['productDetails']['fg2']=={'unit':'BOX','packSize':None}
 scoped=p.build(d,None,{'role':'viewer','permissions':{},'allowedSegments':['A']})
 assert 'fg2' not in scoped['productDetails']
