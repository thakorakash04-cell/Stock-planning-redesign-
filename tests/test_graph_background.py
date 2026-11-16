"""Cached graph definitions/styles can be edited without transferring chart rows."""
import json,unittest
from unittest.mock import patch
import test_kpi_background as baseline
from test_full_insight_storage import st,memory,TABLE,VIEW,spec,chart_result
from stock_accounts import assistant_insights as assistant,insight_display as display
class BackgroundGraphTests(unittest.TestCase):
 def setUp(self):
  baseline.BackgroundKpiTests.setUp(self)
  section={'view':0,'title':'Stock','records':300,'charts':[chart_result([TABLE],VIEW,spec())],'kpis':[]}
  report={'report_id':'graph-original','version':'v1','knowledge_revision':'rules1','sections':[section]};dashboard={'version':'v1','scope':'scope','planning_revision':'sources1','knowledge_revision':'rules1','tables':[TABLE],'views':{0:VIEW},'context':{},'sections':[section]}
  with patch.object(self.store,'get_dataset',return_value={'version':'v1'}):memory.save(self.store,self.actor,report,dashboard)
  self.graph=report['sections'][0]['charts'][0];self.generation=report['cache_generation'];meta=display.metadata(self.store,self.actor,'v1',False,False);self.token=display.reserve(self.store,self.actor,'v1',meta);st.session_state['_stock_dashboard_reports']={}
 def request(self,action,style='column'):
  return assistant.handle_ai(self.store,self.actor,{'action':action,'compact':True,'report_id':self.token,'version':'v1','view':0,'item_kind':'chart','chart_id':self.graph['id'],'chart_type':style,'cache_generation':self.generation})
 def test_save_delete_retry_no_snapshot_source_rows_or_full_report(self):
  with patch.object(memory,'restore',side_effect=AssertionError('no restore')),patch.object(memory,'unpack',side_effect=AssertionError('no decode')),patch.object(self.store,'get_dataset',side_effect=AssertionError('no workbook')),patch.object(self.store,'run',wraps=self.store.run) as sql:
   response=self.request('save_insight_item');self.assertEqual(response['chart_type'],'column');self.assertLess(len(json.dumps(response)),700)
   self.request('delete_insight_chart');self.request('delete_insight_chart')
  self.assertFalse(any('select snapshot' in c.args[1].lower() or 'select payload' in c.args[1].lower() for c in sql.call_args_list))
  with self.store.transaction() as db:
   layout=json.loads(self.store.run(db,'SELECT layout FROM insight_memory').fetchone()['layout']);catalog=self.store.run(db,'SELECT catalog FROM insight_kpi_catalog').fetchone()['catalog']
  self.assertIn(self.graph['id'],layout['deleted']);self.assertNotIn('M299',catalog);self.assertNotIn('M000',catalog);self.assertFalse(st.session_state['_stock_dashboard_reports'])
 def test_server_style_capabilities_preserve_fallbacks_without_rows(self):
  with patch.object(memory,'unpack',side_effect=AssertionError('no decode')):
   self.assertEqual(self.request('save_insight_item','donut')['chart_type'],'bar')
   self.assertEqual(self.request('save_insight_item','line')['chart_type'],'column')
   with self.assertRaises(ValueError):self.request('save_insight_item','scatter')
   with self.assertRaises(ValueError):self.request('save_insight_item','unknown')
 def test_lost_save_ack_confirms_only_the_same_durable_style(self):
  original=memory.fast_edit
  def lost(*args):original(*args);raise TimeoutError('lost reply')
  with patch.object(memory,'fast_edit',side_effect=lost):
   with self.assertRaises(TimeoutError):self.request('save_insight_item','column')
  with self.assertRaisesRegex(ValueError,'changed'):self.request('save_insight_item','bar')
  with patch.object(memory,'fast_edit',side_effect=AssertionError('no repeat write')):self.assertEqual(self.request('save_insight_item','column')['chart_type'],'column')
 def test_failed_delete_is_not_durable(self):
  with patch.object(self.store,'_log',side_effect=RuntimeError('commit failed')):
   with self.assertRaises(RuntimeError):self.request('delete_insight_chart')
  with self.store.transaction() as db:self.assertNotIn(self.graph['id'],json.loads(self.store.run(db,'SELECT layout FROM insight_memory').fetchone()['layout']).get('deleted',[]))
 def test_previous_kpi_only_catalog_upgrades_once(self):
  with self.store.transaction() as db:self.store.run(db,'UPDATE insight_kpi_catalog SET catalog=?',(json.dumps({'items':[],'period_sensitive':False}),))
  self.request('save_insight_item')
  with patch.object(memory,'unpack',side_effect=AssertionError('no second migration')):self.request('delete_insight_chart')
if __name__=='__main__':unittest.main()
