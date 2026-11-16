"""Real SQL: lazy KPI edits use definitions only, never report/source payloads."""
import copy,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from test_full_insight_storage import st,Store,memory,TABLE,VIEW,card_spec,kpi_result
from stock_accounts import assistant_insights as assistant,insight_kpi_edits as edits,insight_display as display
class BackgroundKpiTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
  self.store=Store('sqlite:///'+str(Path(self.folder.name)/'db'));self.store.bootstrap_admin('admin_user','Test-admin-password!123');self.actor=self.store.login('admin_user','Test-admin-password!123');st.session_state.clear()
  self.patch=patch.dict(sys.modules,{'stock_accounts.planning_assistant':types.SimpleNamespace(knowledge=lambda:{'revision':'rules1'})});self.patch.start();self.addCleanup(self.patch.stop)
  for name,value in [('report_scope','scope'),('data_revision','sources1')]:
   p=patch.object(assistant,name,return_value=value);p.start();self.addCleanup(p.stop)
  with self.store.transaction() as db:self.store.run(db,"INSERT INTO datasets(id,payload,filename,version,uploaded_by,updated_at) VALUES('current','MUST NOT DECODE','book.xlsx','v1','admin_user',1)")
  section={'view':0,'title':'Stock','records':300,'charts':[],'kpis':[kpi_result([TABLE],VIEW,card_spec())]}
  report={'report_id':'original','version':'v1','knowledge_revision':'rules1','sections':[section]};dashboard={'version':'v1','scope':'scope','planning_revision':'sources1','knowledge_revision':'rules1','tables':[TABLE],'views':{0:VIEW},'context':{},'sections':[section]}
  with patch.object(self.store,'get_dataset',return_value={'version':'v1'}):memory.save(self.store,self.actor,report,dashboard)
  self.card=report['sections'][0]['kpis'][0];self.generation=report['cache_generation'];meta=display.metadata(self.store,self.actor,'v1',False,False);self.token=display.reserve(self.store,self.actor,'v1',meta)
  st.session_state['_stock_dashboard_reports']={}
 def request(self,action):
  return assistant.handle_ai(self.store,self.actor,{'action':action,'compact':True,'report_id':self.token,'version':'v1','view':0,'item_kind':'kpi','kpi_id':self.card['id'],'cache_generation':self.generation})
 def test_cached_save_delete_and_lost_ack_retry_are_metadata_only(self):
  with patch.object(memory,'restore',side_effect=AssertionError('no full restore')),patch.object(memory,'unpack',side_effect=AssertionError('no snapshot decode')),patch.object(self.store,'get_dataset',side_effect=AssertionError('no source reload')),patch.object(self.store,'run',wraps=self.store.run) as sql:
   first=self.request('save_insight_item');self.assertTrue(first['saved']);self.assertLess(len(json.dumps(first)),700)
   self.request('save_insight_item') # A lost acknowledgement retries the same state.
   self.assertTrue(self.request('delete_insight_chart')['deleted']);self.assertTrue(self.request('delete_insight_chart')['deleted'])
  selects=[c.args[1].lower() for c in sql.call_args_list if c.args[1].lstrip().lower().startswith('select')]
  self.assertFalse(any('select snapshot' in q or 'select payload' in q for q in selects))
  self.assertFalse(st.session_state['_stock_dashboard_reports'],'Small edit descriptors never become a partial active report')
  with self.store.transaction() as db:
   row=self.store.run(db,'SELECT layout FROM insight_memory').fetchone();catalog=self.store.run(db,'SELECT catalog FROM insight_kpi_catalog').fetchone()['catalog']
  self.assertIn(self.card['id'],json.loads(row['layout'])['deleted_kpis']);self.assertNotIn('M299',catalog);self.assertNotIn('45150',catalog)
 def test_commit_with_lost_reply_is_confirmed_without_repeating_write(self):
  original=memory.fast_edit
  def lost(*args):original(*args);raise TimeoutError('acknowledgement lost')
  with patch.object(memory,'fast_edit',side_effect=lost):
   with self.assertRaises(TimeoutError):self.request('save_insight_item')
  with patch.object(memory,'fast_edit',side_effect=AssertionError('must confirm existing commit')):self.assertTrue(self.request('save_insight_item')['saved'])
 def test_failed_commit_keeps_layout_and_binding_unchanged(self):
  stamp=st.session_state['_stock_insight_lazy'][self.token]['stamp']
  with patch.object(self.store,'_log',side_effect=RuntimeError('commit failed')):
   with self.assertRaisesRegex(RuntimeError,'commit failed'):self.request('delete_insight_chart')
  self.assertEqual(st.session_state['_stock_insight_lazy'][self.token]['stamp'],stamp)
  with self.store.transaction() as db:self.assertNotIn(self.card['id'],json.loads(self.store.run(db,'SELECT layout FROM insight_memory').fetchone()['layout']).get('deleted_kpis',[]))
 def test_legacy_catalog_migrates_once_without_source_or_evidence_restore(self):
  with self.store.transaction() as db:self.store.run(db,'DELETE FROM insight_kpi_catalog')
  with patch.object(memory,'restore',side_effect=AssertionError('no full restore')),patch.object(self.store,'get_dataset',side_effect=AssertionError('no workbook decode')):
   self.request('save_insight_item')
   with patch.object(memory,'unpack',side_effect=AssertionError('migration must not repeat')):self.request('delete_insight_chart')
 def test_expired_binding_and_source_change_fail_closed(self):
  st.session_state['_stock_insight_lazy'][self.token]['scope']='other'
  with self.assertRaisesRegex(ValueError,'expired'):self.request('save_insight_item')
  st.session_state['_stock_insight_lazy'][self.token]['scope']='scope'
  with self.store.transaction() as db:self.store.run(db,"UPDATE datasets SET updated_at=2")
  with self.assertRaisesRegex(ValueError,'changed'):self.request('delete_insight_chart')
if __name__=='__main__':unittest.main()
