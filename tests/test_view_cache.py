import sys,types,unittest
from unittest.mock import Mock,patch
from test_issue_slip_cache import Store
from stock_accounts.view_cache import read

class ViewCacheTests(unittest.TestCase):
 def setUp(self):
  self.store=Store();self.addCleanup(self.store.db.close);self.actor=object();self.store.db.execute('CREATE TABLE production_availability_cache(plan_id TEXT,scope TEXT,version TEXT,uploaded_at REAL,signature TEXT,available INTEGER,checked_at REAL)');self.store.db.execute('CREATE TABLE production_batch_availability(scope TEXT,version TEXT,uploaded_at REAL,signature TEXT,checked_at REAL)');self.finance={'pnl':'f1'};self.menu=Mock();self.loader=Mock(return_value={'rows':[['A',3]]})
  modules={'stock_accounts.access':types.SimpleNamespace(require_menu=self.menu),'stock_accounts.production':types.SimpleNamespace(schema=lambda *a:None,REVISION=15,shared=lambda store,actor:[dict(r) for r in store.db.execute('SELECT kind,id,revision,updated_at FROM production_shared ORDER BY updated_at DESC,kind,id')]),'stock_accounts.availability_cache':types.SimpleNamespace(schema=lambda *a:None,revision=lambda store,*args:str([tuple(r) for r in store.db.execute('SELECT plan_id,signature,available,checked_at FROM production_availability_cache')])+str([tuple(r) for r in store.db.execute('SELECT signature,checked_at FROM production_batch_availability')])),'stock_accounts.batch_availability':types.SimpleNamespace(schema=lambda *a:None),'stock_accounts.segment_access':types.SimpleNamespace(scope_key=lambda *a:'all'),'stock_accounts.order_snapshot':types.SimpleNamespace(REVISION=2),'stock_accounts.pnl':types.SimpleNamespace(REVISION=9),'stock_accounts.preload':types.SimpleNamespace(versions=lambda *a:self.finance)}
  p=patch.dict(sys.modules,modules);p.start();self.addCleanup(p.stop)
 def call(self,operation,stamp=None,**params):return read(self.store,self.actor,{'action':operation,'known_stamp':stamp,**params},self.loader)
 def test_all_unchanged_views_validate_without_loading_payloads(self):
  for operation,tab in [('production_status',3),('planning_status',6),('pnl_report',10)]:
   first=self.call(operation,fy=2026);self.loader.reset_mock();queries=[];self.store.db.set_trace_callback(queries.append)
   result=self.call(operation,first['stamp'],fy=2026)
   self.assertTrue(result['not_modified']);self.assertNotIn('data',result);self.loader.assert_not_called();self.menu.assert_called_with(self.store,self.actor,tab)
   self.assertFalse(any('payload' in q.lower() or 'select *' in q.lower() for q in queries))
 def test_master_change_invalidates_planning(self):
  first=self.call('planning_status');self.store.db.execute("UPDATE datasets SET updated_at=2")
  self.assertFalse(self.call('planning_status',first['stamp'])['not_modified'])
 def test_plan_edits_invalidate_production_only(self):
  prod=self.call('production_status');planning=self.call('planning_status')
  self.store.db.execute('UPDATE production_shared SET revision=2')
  self.assertFalse(self.call('production_status',prod['stamp'])['not_modified']);self.assertTrue(self.call('planning_status',planning['stamp'])['not_modified'])
 def test_finance_and_filter_scopes_are_distinct(self):
  first=self.call('pnl_report',fy=2026,basis='revenue',segments=['A'])
  for params in [{'fy':2025,'basis':'revenue','segments':['A']},{'fy':2026,'basis':'std_dp','segments':['A']},{'fy':2026,'basis':'revenue','segments':['B']}]:self.assertFalse(self.call('pnl_report',first['stamp'],**params)['not_modified'])
  self.finance['pnl']='f2';self.assertFalse(self.call('pnl_report',first['stamp'],fy=2026,basis='revenue',segments=['A'])['not_modified'])
 def test_live_access_always_precedes_cache_hit(self):
  first=self.call('production_status');self.menu.side_effect=PermissionError('Denied')
  with self.assertRaises(PermissionError):self.call('production_status',first['stamp'])
 def test_new_login_does_not_expire_sources(self):
  first=self.call('planning_status');self.store.identity['session_id']='new-login'
  self.assertTrue(self.call('planning_status',first['stamp'])['not_modified'])
 def test_continuously_changing_sources_are_not_cached(self):
  def changed():self.store.db.execute('UPDATE production_shared SET revision=revision+1');return {}
  self.loader.side_effect=changed
  with self.assertRaisesRegex(ValueError,'changed'):self.call('production_status')

 def test_availability_badges_refresh_without_reading_details(self):
  first=self.call('production_status')
  self.store.db.execute("INSERT INTO production_batch_availability VALUES('all','v1',1,'batch',2)")
  self.assertFalse(self.call('production_status',first['stamp'])['not_modified'])
