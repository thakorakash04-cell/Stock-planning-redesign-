"""Real durable SQL with a deliberately unreadable workbook payload: edits must be metadata-only."""
import ast,copy,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_full_insight_storage import st,Store,memory,TABLE,VIEW,spec,card_spec,chart_result,kpi_result
from stock_accounts import assistant_insights as assistant
class FastEditTests(unittest.TestCase):
 def test_compact_saves_deletes_filters_and_facets_reuse_registered_data(self):
  with tempfile.TemporaryDirectory() as folder:
   store=Store('sqlite:///'+str(Path(folder)/'db'));store.bootstrap_admin('admin_user','Test-admin-password!123');actor=store.login('admin_user','Test-admin-password!123');st.session_state.clear()
   with store.transaction() as db:store.run(db,"INSERT INTO datasets(id,payload,filename,version,uploaded_by,updated_at) VALUES('current','DO NOT DECODE','book.xlsx','v1','admin_user',1)")
   planner=types.SimpleNamespace(knowledge=lambda:{'revision':'rules1'})
   with patch.dict(sys.modules,{'stock_accounts.planning_assistant':planner}),patch.object(assistant,'report_scope',return_value='scope'),patch.object(assistant,'data_revision',return_value='rev1'):
    section={'view':0,'title':'Stock','records':300,'charts':[chart_result([TABLE],VIEW,spec())],'kpis':[kpi_result([TABLE],VIEW,card_spec())]};report={'report_id':'original','version':'v1','knowledge_revision':'rules1','sections':[section]};dashboard={'version':'v1','scope':'scope','planning_revision':'rev1','knowledge_revision':'rules1','tables':[TABLE],'views':{0:VIEW},'sections':[section],'context':{}}
    with patch.object(store,'get_dataset',return_value={'version':'v1'}):memory.save(store,actor,report,dashboard)
    loaded=memory.restore(store,actor,'v1');token=loaded['report_id'];graph=loaded['sections'][0]['charts'][0];card=loaded['sections'][0]['kpis'][0]
    with store.transaction() as db:original_snapshot=store.run(db,'SELECT snapshot FROM insight_memory').fetchone()['snapshot']
    def request(action,**payload):return assistant.handle_ai(store,actor,{'action':action,'version':'v1','report_id':token,'view':0,**payload})
    with patch.object(store,'get_dataset',side_effect=AssertionError('workbook must not be decoded')),patch.object(assistant,'stock_tables',side_effect=AssertionError('table catalogue must not be rebuilt')),patch.object(memory,'restore',side_effect=AssertionError('edits must not restore every graph')),patch.object(store,'run',wraps=store.run) as sql:
     result=request('save_insight_item',compact=True,chart_id=graph['id'],chart_type='column');self.assertEqual(result['report_id'],token);self.assertTrue(result['saved']);self.assertNotIn('report',result);self.assertLess(len(json.dumps(result)),500)
     request('save_insight_item',compact=True,item_kind='kpi',kpi_id=card['id'])
     request('save_insight_item',compact=True,chart_id=graph['id'],chart_type='column')
     with patch.object(store,'_log',side_effect=RuntimeError('audit commit failed')):
      with self.assertRaisesRegex(RuntimeError,'audit commit failed'):request('save_insight_item',compact=True,chart_id=graph['id'],chart_type='bar')
     self.assertEqual(st.session_state['_stock_dashboard_reports'][token]['sections'][0]['charts'][0]['type'],'column','failed commits must not update the active report')
     filtered=request('filter_insights',filters=[{'column':'Material','op':'eq','value':'M299'}]);self.assertEqual(filtered['section']['kpis'][0]['value'],300);self.assertEqual(filtered['report_id'],token)
     facet=request('insight_filter_values',column='Material',query='M29',offset=0);self.assertEqual(len(facet['values']),10)
     request('save_insight_item',compact=True,item_kind='kpi',kpi_id=card['id'])
     removed=request('delete_insight_chart',compact=True,chart_id=graph['id']);self.assertTrue(removed['deleted']);request('delete_insight_chart',compact=True,chart_id=graph['id'])
     with self.assertRaisesRegex(ValueError,'deleted'):request('save_insight_item',compact=True,chart_id=graph['id'])
     statements=[call.args[1] for call in sql.call_args_list];self.assertFalse(any('SET snapshot=' in q or 'SELECT snapshot' in q for q in statements));self.assertFalse(any('payload' in q for q in statements))
    st.session_state.clear();restored=memory.restore(store,actor,'v1');self.assertEqual(restored['sections'][0]['charts'],[]);self.assertTrue(restored['sections'][0]['kpis'][0]['saved']);self.assertEqual(restored['sections'][0]['kpis'][0]['value'],45150,'saving from a filtered view preserves canonical full-scope arithmetic')
    with store.transaction() as db:
     row=store.run(db,'SELECT snapshot,layout FROM insight_memory').fetchone();self.assertEqual(row['snapshot'],original_snapshot);layout=json.loads(row['layout']);self.assertIn(graph['id'],layout['deleted']);self.assertEqual(len(layout['custom_kpis']),1)
    token=restored['report_id']
    with patch.object(assistant,'data_revision',return_value='new-source'):
     with self.assertRaisesRegex(ValueError,'sources changed'):request('delete_insight_chart',compact=True,item_kind='kpi',kpi_id=card['id'])
    rerun=copy.deepcopy(report);rerun['report_id']='new-run';rerun.pop('cache_generation',None);next_dashboard={**dashboard,'sections':rerun['sections']}
    with patch.object(store,'get_dataset',return_value={'version':'v1'}):memory.save(store,actor,rerun,next_dashboard)
    with self.assertRaisesRegex(ValueError,'regenerated'):request('save_insight_item',compact=True,item_kind='kpi',kpi_id=card['id'])
    again=memory.restore(store,actor,'v1');self.assertEqual(again['sections'][0]['charts'],[]);self.assertTrue(again['sections'][0]['kpis'][0]['saved'])
 def test_revision_check_for_segmented_account_uses_metadata_and_hides_plan_ids(self):
  with tempfile.TemporaryDirectory() as folder:
   store=Store('sqlite:///'+str(Path(folder)/'db'));store.bootstrap_admin('admin_user','Test-admin-password!123');admin=store.login('admin_user','Test-admin-password!123');store.create_viewer(admin,'viewer_user','Test-viewer-password!123');
   with store.transaction() as db:store.run(db,"UPDATE accounts SET allowed_segments='[\"AWC\"]' WHERE username='viewer_user'")
   actor=store.login('viewer_user','Test-viewer-password!123')
   from stock_accounts.production import schema
   with store.transaction() as db:
    schema(store,db);store.run(db,"INSERT INTO production_shared(kind,id,payload,revision,updated_by,updated_at) VALUES('upcoming','private-plan-id','unused',1,'admin_user',1)")
   with patch.object(store,'get_dataset',side_effect=AssertionError('metadata revision must not decode the workbook')),patch('stock_accounts.insight_dashboard.source_revision',return_value=[]):
    first=assistant.data_revision(store,actor);self.assertNotIn('private-plan-id',str(first))
    with store.transaction() as db:store.run(db,"UPDATE production_shared SET revision=2")
    self.assertNotEqual(first,assistant.data_revision(store,actor))
 def test_success_reply_reuses_workspace_only_for_matching_session_access_and_workbook(self):
  tree=ast.parse((Path(__file__).resolve().parents[1]/'stock_accounts/workspace.py').read_text());function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='workspace_payload')
  scope={'st':st,'__package__':'stock_accounts','decorate_workspace':lambda store,actor,payload:{**payload,'decorated':True}}
  exec(compile(ast.Module(body=[function],type_ignores=[]),'workspace-cache','exec'),scope)
  with tempfile.TemporaryDirectory() as folder:
   store=Store('sqlite:///'+str(Path(folder)/'db'));store.bootstrap_admin('admin_user','Test-admin-password!123');actor=store.login('admin_user','Test-admin-password!123');identity=store.identity(actor)
   with store.transaction() as db:store.run(db,"INSERT INTO datasets(id,payload,filename,version,uploaded_by,updated_at) VALUES('current','DO NOT DECODE','book.xlsx','v1','admin_user',1)")
   key=(actor.username,actor.session_id,('v1',1.0),str(identity['permissions']),27,(),'plans',str(identity.get('allowedSegments')),'availability');st.session_state['_workspace_payload']=(key,({'filename':'book.xlsx'},[], 'v1'))
   def full(*args):raise AssertionError('full rebuild required')
   with patch.dict(sys.modules,{'stock_accounts.production':types.SimpleNamespace(shared=full)}),patch.object(store,'get_dataset',side_effect=AssertionError('no workbook decode')):
    result=scope['workspace_payload'](store,actor,cached_only=True);self.assertTrue(result[0]['decorated']);self.assertEqual(result[2],'v1')
    other=store.login('admin_user','Test-admin-password!123')
    with self.assertRaisesRegex(AssertionError,'full rebuild'):scope['workspace_payload'](store,other,cached_only=True)
    with store.transaction() as db:store.run(db,"UPDATE datasets SET updated_at=2")
    with self.assertRaisesRegex(AssertionError,'full rebuild'):scope['workspace_payload'](store,actor,cached_only=True)
if __name__=='__main__':unittest.main()
