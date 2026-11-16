import copy,sys,types,unittest,sqlite3
from contextlib import contextmanager
from unittest.mock import patch,Mock
from stock_accounts.issue_slip import read

class Store:
 def __init__(self):
  self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
  self.db.execute('CREATE TABLE datasets(id TEXT,version TEXT,updated_at REAL)');self.db.execute("INSERT INTO datasets VALUES('current','v1',1)")
  self.db.execute('CREATE TABLE production_shared(kind TEXT,id TEXT,revision INTEGER,updated_at REAL)');self.db.execute("INSERT INTO production_shared VALUES('upcoming','p',1,1)")
  self.identity={'username':'a','role':'viewer','permissions':{'production':True},'allowedSegments':['A']}
 @contextmanager
 def transaction(self):yield self.db
 def require(self,db,actor):return copy.deepcopy(self.identity)
 def run(self,db,sql,args=()):return db.execute(sql,args)

class IssueSlipCacheTests(unittest.TestCase):
 def setUp(self):
  self.store=Store();self.addCleanup(self.store.db.close);self.actor=object()
  self.report={'version':'v1','sourceStamp':1,'upcoming':[{'id':'p','revision':1,'materialCode':'FG','row':['FG',5]}]}
  self.value={'version':'v1','sourceStamp':1,'issueHeaders':['Plan','Component','Qty'],'issueRows':[['p','RM',0.0375]],'checkedAt':1}
  self.production=Mock(side_effect=lambda *a:copy.deepcopy(self.report));self.calculate=Mock(return_value=self.value);self.authorize=Mock()
  modules={'stock_accounts.access':types.SimpleNamespace(require_menu=self.authorize),'stock_accounts.production':types.SimpleNamespace(read=self.production,schema=lambda *a:None,REVISION=13),'stock_accounts.batch_availability':types.SimpleNamespace(check=self.calculate,REVISION=2)}
  self.patch=patch.dict(sys.modules,modules);self.patch.start();self.addCleanup(self.patch.stop)
 def test_unchanged_login_reads_metadata_only(self):
  first=read(self.store,self.actor,{});self.calculate.reset_mock();self.production.reset_mock()
  queries=[];self.store.db.set_trace_callback(queries.append)
  result=read(self.store,self.actor,{'known_stamp':first['stamp']})
  self.assertEqual(result,{'stamp':first['stamp'],'not_modified':True});self.calculate.assert_not_called();self.production.assert_not_called()
  self.assertFalse(any('payload' in q.lower() or 'select *' in q.lower() for q in queries));self.authorize.assert_called_with(self.store,self.actor,12)
 def test_plan_and_workbook_changes_invalidate(self):
  before=read(self.store,self.actor,{});self.store.db.execute('UPDATE production_shared SET revision=2')
  after=read(self.store,self.actor,{'known_stamp':before['stamp']});self.assertFalse(after['not_modified']);self.assertNotEqual(before['stamp'],after['stamp'])
  self.store.db.execute("UPDATE datasets SET version='v2'");self.assertNotEqual(after['stamp'],read(self.store,self.actor,{})['stamp'])
 def test_refresh_updates_edited_and_deleted_plans(self):
  first=read(self.store,self.actor,{});self.store.db.execute('UPDATE production_shared SET revision=2')
  self.calculate.return_value={**self.value,'issueRows':[['p','RM',0.075]]}
  refreshed=read(self.store,self.actor,{'known_stamp':first['stamp']});self.assertEqual(refreshed['result']['issueRows'],[['p','RM',0.075]])
  self.report['upcoming']=[];self.store.db.execute('DELETE FROM production_shared');self.assertIsNone(read(self.store,self.actor,{'known_stamp':refreshed['stamp']})['result'])
 def test_current_saved_table_reused(self):
  self.report['batchAvailability']=self.value;result=read(self.store,self.actor,{})
  self.calculate.assert_not_called();self.assertEqual(result['result']['issueRows'],self.value['issueRows']);self.assertNotIn('upcoming',result)
 def test_access_denial_never_returns_cache_hit(self):
  first=read(self.store,self.actor,{});self.authorize.side_effect=PermissionError('Denied')
  with self.assertRaises(PermissionError):read(self.store,self.actor,{'known_stamp':first['stamp']})
 def test_empty_results_and_access_changes(self):
  self.report['upcoming']=[];self.store.db.execute('DELETE FROM production_shared');first=read(self.store,self.actor,{})
  self.assertIsNone(first['result']);self.calculate.assert_not_called();self.store.identity['allowedSegments']=['B']
  self.assertFalse(read(self.store,self.actor,{'known_stamp':first['stamp']})['not_modified'])
 def test_new_login_or_day_does_not_expire_cache(self):
  first=read(self.store,self.actor,{});self.store.identity['last_login']='tomorrow'
  self.assertTrue(read(self.store,self.actor,{'known_stamp':first['stamp']})['not_modified'])
 def test_change_during_calculation_cannot_be_cached(self):
  def changed(*args):self.store.db.execute('UPDATE production_shared SET revision=2');return self.value
  self.calculate.side_effect=changed
  with self.assertRaisesRegex(ValueError,'changed'):read(self.store,self.actor,{})

 def test_postgres_mapping_rows_include_actual_source_values(self):
  original=self.store.run
  class Rows:
   def __init__(self,cursor):self.cursor=cursor
   def fetchone(self):
    row=self.cursor.fetchone();return dict(row) if row else None
   def fetchall(self):return [dict(row) for row in self.cursor.fetchall()]
  self.store.run=lambda *args:Rows(original(*args))
  first=read(self.store,self.actor,{})
  self.store.db.execute("UPDATE datasets SET version='v2'")
  self.assertFalse(read(self.store,self.actor,{'known_stamp':first['stamp']})['not_modified'])
