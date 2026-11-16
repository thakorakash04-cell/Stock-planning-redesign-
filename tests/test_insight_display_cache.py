import copy,tempfile,unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import streamlit as st
from stock_accounts.store import Store,AccessDenied
from stock_accounts import insight_memory as memory,insight_display as display,assistant_insights as ai
from stock_accounts.insights import chart_result
TABLE={'id':'T1','name':'Stock','headers':['Material','Qty'],'rows':[['A',10],['B',20]]}
VIEW={'view':0,'table':'Stock','table_id':'T1','title':'Stock'}
class InsightDisplayTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.store=Store('sqlite:///'+str(Path(self.tmp.name)/'db'));self.store.bootstrap_admin('admin_user','Test-admin-password!123');self.actor=self.store.login('admin_user','Test-admin-password!123');self.state={};self.stack=ExitStack();self.addCleanup(self.stack.close)
  self.stack.enter_context(patch.object(st,'session_state',self.state));self.stack.enter_context(patch.object(ai,'data_revision',return_value='sources1'));self.stack.enter_context(patch('stock_accounts.planning_assistant.knowledge',return_value={'revision':'rules1'}));self.stack.enter_context(patch('grounded_ai.settings',return_value=('key','model')));self.stack.enter_context(patch('grounded_ai.generate',side_effect=AssertionError('Cache must not call AI')));self.stack.enter_context(patch.object(self.store,'get_dataset',return_value={'version':'v1'}))
  with self.store.transaction() as db:self.store.run(db,"INSERT INTO datasets VALUES('current','unused','Master.xlsx','v1','admin_user',1)")
  chart=chart_result([TABLE],VIEW,{'title':'Quantities','type':'bar','label':'Material','value':'Qty','query':{'table':'T1','columns':['Material','Qty']}})
  section={'view':0,'title':'Stock','records':2,'charts':[chart],'kpis':[],'facets':[]};scope=ai.report_scope(self.store,self.actor)
  self.report={'report_id':'r1','version':'v1','knowledge_revision':'rules1','sections':[section]};self.dashboard={'version':'v1','scope':scope,'planning_revision':'sources1','knowledge_revision':'rules1','tables':[TABLE],'views':{0:VIEW},'sections':[section],'context':{}}
  memory.save(self.store,self.actor,self.report,self.dashboard)
 def call(self,event):return ai.handle_ai(self.store,self.actor,{'action':'ai_status','display_cache':True,**event})
 def test_cold_display_does_not_materialize_all_source_evidence(self):
  with patch('stock_accounts.insight_dashboard.register',side_effect=AssertionError('Display must defer evidence registration')):
   first=self.call({})
  self.assertEqual(first['saved_report']['sections'][0]['charts'][0]['evidence']['records'][0]['Qty'],10)
  self.assertNotIn('_stock_dashboard_reports',self.state)
  self.assertTrue(first['report_binding'].startswith('lazy_'))
 def test_fresh_session_cache_hit_is_metadata_only_and_lazy_drill_is_exact(self):
  first=self.call({});self.assertTrue(first['workbook_ready']);chart=first['saved_report']['sections'][0]['charts'][0];self.state.clear();queries=[];run=self.store.run
  def trace(db,sql,args=()):queries.append(sql);return run(db,sql,args)
  with patch.object(self.store,'run',side_effect=trace),patch.object(memory,'restore',side_effect=AssertionError('Cache hit must not rehydrate raw source tables')),patch.object(ai,'stock_tables',side_effect=AssertionError('No source preparation')):
   hit=self.call({'known_report_stamp':first['report_stamp']});self.assertTrue(hit['report_not_modified']);self.assertTrue(hit['workbook_ready']);self.assertNotIn('saved_report',hit)
  self.assertFalse(any('SELECT snapshot' in q for q in queries));alias=hit['report_binding'];token=f"lazy:{alias}:0:charts:{chart['id']}:current"
  with patch.object(ai,'stock_tables',side_effect=AssertionError('Snapshot drill does not need fresh master tables')):
   result=ai.handle_ai(self.store,self.actor,{'action':'insight_records','source_id':token,'version':'v1','mark':1,'page':0})
  self.assertEqual([{k:v for k,v in r.items() if k!='Source row'} for r in result['records']],[{'Material':'B','Qty':20.0}]);self.assertEqual(result['total'],1)
  for forged in [token.replace(chart['id'],'forged'),token.replace(':0:',':999:')]:
   with self.assertRaises(ValueError):ai.handle_ai(self.store,self.actor,{'action':'insight_records','source_id':forged,'version':'v1'})
 def test_delete_is_durable_and_stale_cached_binding_cannot_resurrect_it(self):
  first=self.call({});chart=first['saved_report']['sections'][0]['charts'][0];self.state.clear();hit=self.call({'known_report_stamp':first['report_stamp']});alias=hit['report_binding']
  reply=ai.handle_ai(self.store,self.actor,{'action':'delete_insight_chart','compact':True,'report_id':alias,'version':'v1','view':0,'chart_id':chart['id']});self.assertTrue(reply['deleted']);self.assertNotEqual(reply['report_stamp'],first['report_stamp'])
  self.state.clear();again=self.call({'known_report_stamp':first['report_stamp']});self.assertEqual(again['saved_report']['sections'][0]['charts'],[])
 def test_workbook_replacement_updates_only_affected_display_sections(self):
  other={'id':'T2','name':'Other','headers':['Material','Qty'],'rows':[['C',30]]};view={'view':1,'table':'Other','table_id':'T2','title':'Other'}
  graph=chart_result([other],view,{'title':'Other quantities','type':'bar','label':'Material','value':'Qty','query':{'table':'T2','columns':['Material','Qty']}})
  section={'view':1,'title':'Other','records':1,'charts':[graph],'kpis':[],'facets':[]};self.report['sections'].append(section);self.dashboard['sections'].append(section) if self.dashboard['sections'] is not self.report['sections'] else None;self.dashboard['tables'].append(other);self.dashboard['views'][1]=view
  memory.save(self.store,self.actor,self.report,self.dashboard);before=self.call({});self.state.clear()
  with self.store.transaction() as db:self.store.run(db,"UPDATE datasets SET version='v2',updated_at=2")
  fresh=[{**TABLE,'id':'NEW1','rows':[['A',99],['B',20]]},{**other,'id':'NEW2'}]
  with patch('stock_accounts.insight_refresh.prepare_sources',return_value=(fresh,[VIEW,view],{}, {'version':'v2'})),patch.object(self.store,'get_dataset',return_value={'version':'v2'}):
   after=self.call({'known_report_stamp':before['report_stamp'],'known_sections':before['section_stamps']})
  self.assertTrue(after['report_patch']);self.assertEqual(after['saved_report']['version'],'v2');self.assertEqual([s['view'] for s in after['saved_report']['sections']],[0]);self.assertEqual(after['saved_report']['sections'][0]['charts'][0]['evidence']['records'][0]['Qty'],99)
 def test_other_account_cannot_use_cached_reference(self):
  before=self.call({});self.state.clear();hit=self.call({'known_report_stamp':before['report_stamp']});self.store.create_viewer(self.actor,'viewer_user','Test-viewer-password!123');viewer=self.store.login('viewer_user','Test-viewer-password!123')
  with self.assertRaisesRegex(ValueError,'expired'):display.resolve(self.store,viewer,{'report_id':hit['report_binding'],'version':'v1'})
 def test_access_revocation_and_source_change_reject_lazy_handles(self):
  first=self.call({});self.state.clear();hit=self.call({'known_report_stamp':first['report_stamp']});alias=hit['report_binding']
  with patch.object(ai,'data_revision',return_value='changed'):
   with self.assertRaisesRegex(ValueError,'changed'):display.resolve(self.store,self.actor,{'action':'filter_insights','report_id':alias,'version':'v1'})
  with patch.object(self.store,'require_permission',side_effect=AccessDenied('Revoked')):
   with self.assertRaises(AccessDenied):self.call({'known_report_stamp':first['report_stamp']})
if __name__=='__main__':unittest.main()
