"""Real SQL snapshots and shared arithmetic; UI/provider transports are isolated."""
import copy,sys,types,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_full_insight_storage import st,Store,memory,chart_result,kpi_result
from stock_accounts.insight_dashboard import mark_table

class AutoRefreshTests(unittest.TestCase):
 def test_manual_edit_recalculates_only_changed_sources_and_survives_fresh_login(self):
  with tempfile.TemporaryDirectory() as folder:
   store=Store('sqlite:///'+str(Path(folder)/'db'));store.bootstrap_admin('admin_user','Test-admin-password!123');actor=store.login('admin_user','Test-admin-password!123')
   revision=['manual1'];planner=types.SimpleNamespace(knowledge=lambda:{'revision':'rules1'})
   assistant=types.SimpleNamespace(report_scope=lambda s,a:'scope',data_revision=lambda s,a:revision[0])
   stock={'id':'T1','name':'Stock','headers':['Material','Qty','Unit'],'rows':[['M1',100,'EA']]}
   plans={'id':'INSIGHT12','name':'Upcoming production','headers':['Material','Qty','Unit'],'rows':[['M1',10,'EA']]}
   tables=[stock,plans];views=[{'view':i,'title':t['name'],'table':t['name'],'table_id':t['id']} for i,t in enumerate(tables)]
   def section(t,v):
    query={'table':t['id'],'metrics':[{'column':'Qty','op':'sum'}],'limit':1}
    card=kpi_result(tables,v,{'title':'Total '+t['name'],'value':'sum(Qty)','basis':'EA','query':query})
    graph=chart_result(tables,v,{'title':t['name'],'type':'bar','label':'Material','value':'Qty','query':{'table':t['id'],'columns':['Material','Qty'],'limit':5}})
    return {'view':v['view'],'title':v['title'],'records':1,'kpis':[card],'charts':[graph],'review':{'findings':['Old narrative']}}
   sections=[section(t,v) for t,v in zip(tables,views)]
   report={'report_id':'report1','version':'v1','knowledge_revision':'rules1','planning_revision':'manual1','sections':sections,'overview':'Old AI narrative'}
   dashboard={'version':'v1','scope':'scope','planning_revision':'manual1','knowledge_revision':'rules1','tables':tables,'views':{v['view']:v for v in views},'context':{},'sections':sections}
   current={'version':'v1','updated_at':1,'filename':'book.xlsx'}
   with store.transaction() as db:store.run(db,"INSERT INTO datasets(id,payload,filename,version,uploaded_by,updated_at) VALUES('current','unused','book.xlsx','v1','admin_user',1)")
   st.session_state.clear()
   with patch.dict(sys.modules,{'stock_accounts.assistant_insights':assistant,'stock_accounts.planning_assistant':planner}),patch.object(store,'get_dataset',side_effect=lambda a:copy.deepcopy(current)):
    memory.save(store,actor,report,dashboard);original=memory.restore(store,actor,'v1');old_stock=copy.deepcopy(original['sections'][0]['charts'][0]['evidence']['records'])
    changed=copy.deepcopy(tables);changed[1]['rows']=[['M1',35,'EA'],['M2',5,'EA']];revision[0]='manual2';st.session_state.clear()
    with patch('stock_accounts.insight_refresh.prepare_sources',side_effect=RuntimeError('Source temporarily unavailable')):
     with self.assertRaisesRegex(RuntimeError,'temporarily unavailable'):memory.restore(store,actor,'v1')
    def concurrent_edit(s,a):
     with store.transaction() as db:store.run(db,"UPDATE insight_memory SET revision='concurrent-layout-edit'")
     return changed,views,{'attention':[],'referenceDate':'2026-10-31'},current
    with patch('stock_accounts.insight_refresh.prepare_sources',side_effect=concurrent_edit):
     with self.assertRaisesRegex(ValueError,'saved dashboard changed'):memory.restore(store,actor,'v1')
    with patch('stock_accounts.insight_refresh.prepare_sources',return_value=(changed,views,{'attention':[],'referenceDate':'2026-10-31'},current)) as prepare:
     restored=memory.restore(store,actor,'v1');self.assertEqual(prepare.call_count,1)
     self.assertEqual(restored['sections'][1]['kpis'][0]['value'],40);self.assertEqual(restored['sections'][0]['charts'][0]['evidence']['records'],old_stock)
     self.assertEqual(restored['updated_views'],[1]);self.assertNotIn('Old AI narrative',restored['overview'])
     card=restored['sections'][1]['kpis'][0];source=st.session_state['_stock_insight_sources'][card['evidence']['source_id']];self.assertEqual(source['source_table']['rows'],changed[1]['rows'])
     st.session_state.clear();again=memory.restore(store,actor,'v1');self.assertEqual(again['sections'][1]['kpis'][0]['value'],40);self.assertEqual(prepare.call_count,1,'fresh login must reuse the updated durable snapshot')
     memory.edit(store,actor,{'report_id':again['report_id'],'view':1,'version':'v1','item_kind':'kpi','kpi_id':again['sections'][1]['kpis'][0]['id']},'v1')
     revision[0]='manual3';changed[1]['rows']=[];st.session_state.clear();deleted=memory.restore(store,actor,'v1');self.assertEqual(deleted['sections'][1]['kpis'],[]);self.assertEqual(deleted['sections'][1]['records'],0)
     current['updated_at']=2
     with store.transaction() as db:store.run(db,"UPDATE datasets SET updated_at=2 WHERE id='current'")
     st.session_state.clear();reuploaded=memory.restore(store,actor,'v1');self.assertIsNotNone(reuploaded);self.assertEqual(reuploaded['sections'][0]['charts'][0]['evidence']['records'],old_stock,'an identical reupload preserves unchanged graph values')
 def test_connected_recipe_uses_shared_tool_and_invalid_sources_never_show_stale_values(self):
  from stock_accounts.insight_refresh import recalculate
  t={'id':'INSIGHT12','name':'Plans','headers':['Material','Qty'],'rows':[['A',10]]}
  connected={'id':'CONNECTED0','name':'Compared','headers':['Material','Qty'],'rows':[['A',10]],'refresh_plan':{'sources':[{'table':'INSIGHT12'}]},'refresh_sources':[{'id':'INSIGHT12','name':'Plans'}]}
  v={'view':30,'table':'Compared','title':'Compared','table_id':'CONNECTED0'}
  chart=chart_result([connected],v,{'title':'Plans comparison','type':'bar','label':'Material','value':'Qty','query':{'table':'CONNECTED0','columns':['Material','Qty'],'limit':5}})
  saved={'tables':[t,connected],'views':[v],'context':{},'report':{'sections':[{'view':30,'title':'Compared','charts':[chart],'kpis':[]}]}}
  fresh={**t,'rows':[['A',80]]};current={'version':'v1'};calls=[]
  def run(s,a,plan,c,tables):
   calls.append(plan);return [{'_table':{'headers':fresh['headers'],'rows':fresh['rows']}}],{}
  planner=types.SimpleNamespace(run_tool=run)
  with patch.dict(sys.modules,{'stock_accounts.planning_assistant':planner}),patch('stock_accounts.insight_refresh.prepare_sources',return_value=([fresh],[],{},current)):
   updated=recalculate(None,None,saved);self.assertEqual(calls[0]['operation'],'insight_comparison');self.assertEqual(updated['report']['sections'][0]['charts'][0]['evidence']['records'][0]['Qty'],80)
   old=copy.deepcopy(saved);old['tables'][1].pop('refresh_plan');out=recalculate(None,None,old);c=out['report']['sections'][0]['charts'][0];self.assertEqual(c['evidence']['records'],[]);self.assertTrue(c['refresh_error']);self.assertNotIn('source_id',c['evidence'])
if __name__=='__main__':unittest.main()
