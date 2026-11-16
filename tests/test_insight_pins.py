"""Saved canonical definitions survive AI reruns; deletes win and values stay current."""
import copy,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_full_insight_storage import st,Store,memory,TABLE,VIEW,spec,card_spec,chart_result,kpi_result
class SavedItemsTests(unittest.TestCase):
 def test_save_rerun_append_and_delete_keep_canonical_full_scope_definitions(self):
  planner=types.SimpleNamespace(knowledge=lambda:{'revision':'rules1'});assistant=types.SimpleNamespace(report_scope=lambda s,a:'scope',data_revision=lambda s,a:'rev1')
  with tempfile.TemporaryDirectory() as folder:
   store=Store('sqlite:///'+str(Path(folder)/'db'));store.bootstrap_admin('admin_user','Test-admin-password!123');actor=store.login('admin_user','Test-admin-password!123');st.session_state.clear()
   def build(token,table):
    section={'view':0,'title':'Stock overview','records':len(table['rows']),'charts':[chart_result([table],VIEW,spec())],'kpis':[kpi_result([table],VIEW,card_spec())]}
    report={'version':'v1','report_id':token,'knowledge_revision':'rules1','sections':[section]};dashboard={'version':'v1','scope':'scope','planning_revision':'rev1','knowledge_revision':'rules1','tables':[table],'views':{0:VIEW},'context':{},'sections':[section]};return report,dashboard
   with patch.dict(sys.modules,{'stock_accounts.assistant_insights':assistant,'stock_accounts.planning_assistant':planner}),patch.object(store,'get_dataset',return_value={'version':'v1'}):
    report,dashboard=build('r1',TABLE);memory.save(store,actor,report,dashboard);loaded=memory.restore(store,actor,'v1');card=loaded['sections'][0]['kpis'][0];graph=loaded['sections'][0]['charts'][0]
    def edit(current,**fields):return memory.edit(store,actor,{'report_id':current['report_id'],'view':0,'version':'v1',**fields},'v1')['report']
    loaded=edit(loaded,action='save_insight_item',item_kind='kpi',kpi_id=card['id'],query={'table':'unauthorized'});loaded=edit(loaded,action='save_insight_item',chart_id=graph['id'],chart_type='column')
    loaded=edit(loaded,action='save_insight_item',item_kind='kpi',kpi_id=card['id'])
    self.assertTrue(loaded['sections'][0]['kpis'][0]['saved']);self.assertTrue(loaded['sections'][0]['charts'][0]['saved']);self.assertEqual(loaded['sections'][0]['charts'][0]['type'],'column')
    with store.transaction() as db:layout=__import__('json').loads(store.run(db,'SELECT layout FROM insight_memory').fetchone()['layout'])
    self.assertEqual(len(layout['custom_kpis']),1);self.assertEqual(layout['custom_kpis'][0]['spec']['query']['table'],'T1')
    new_table=copy.deepcopy(TABLE);new_table['rows']=[[r[0],r[1]*2,r[2]] for r in TABLE['rows']]
    report,dashboard=build('r2',new_table);report['sections'][0]['kpis']=[];report['sections'][0]['charts']=[]
    extra=chart_result([new_table],VIEW,{**spec(),'title':'Other comparison','label':'Unit','query':{'table':'T1','group_by':['Unit'],'metrics':[{'column':'Qty','op':'sum'}],'limit':1},'value':'sum(Qty)'})
    report['sections'][0]['charts']=[extra];memory.save(store,actor,report,dashboard);st.session_state.clear();rerun=memory.restore(store,actor,'v1')
    self.assertEqual(rerun['sections'][0]['kpis'][0]['value'],90300);self.assertEqual(len(rerun['sections'][0]['charts']),2);self.assertEqual(next(c for c in rerun['sections'][0]['charts'] if c['id']==graph['id'])['type'],'column')
    deleted=edit(rerun,item_kind='kpi',kpi_id=card['id']);deleted=edit(deleted,chart_id=graph['id'])
    report,dashboard=build('r3',new_table);memory.save(store,actor,report,dashboard);again=memory.restore(store,actor,'v1');self.assertEqual(again['sections'][0]['kpis'],[]);self.assertEqual(again['sections'][0]['charts'],[])
    with self.assertRaisesRegex(ValueError,'deleted'):edit(again,action='save_insight_item',chart_id=graph['id'])
 def test_saved_connected_view_is_rebuilt_when_new_ai_comparisons_differ(self):
  from stock_accounts.cross_sheet import calculate
  left={'id':'NEWL','name':'Plans','headers':['Material','Qty'],'rows':[['A',20]]}
  right={'id':'NEWR','name':'Prices','headers':['Code','Price'],'rows':[['A',8]]}
  plan={'sources':[{'alias':'s0','table':'OLDL'},{'alias':'s1','table':'OLDR'}],'joins':[{'left_on':['s0.Material'],'right_on':['s1.Code']}],'calculations':[{'name':'Value','op':'multiply','operands':['s0.Qty','s1.Price']}],'columns':['s0.Material','calc.Value']}
  definition={'id':'old-id','view':30,'table':'Saved comparison','spec':{'title':'Saved potential value','type':'column','label':'s0.Material','value':'calc.Value','query':{'table':'CONNECTED0','columns':['s0.Material','calc.Value'],'limit':5}},'source_recipe':{'plan':copy.deepcopy(plan),'sources':[{'id':'OLDL','name':'Plans'},{'id':'OLDR','name':'Prices'}]}}
  layout={'custom':[definition]};dashboard={'tables':[left,right],'views':{30:{'view':30,'title':'New AI comparison','table':'Different comparison'}}};report={'sections':[]};calls=[]
  def run(store,actor,request,current,tables):
   calls.append(request);result=calculate(tables,request);return [{'_table':t} for t in result['tables']],{}
  planner=types.SimpleNamespace(run_tool=run)
  store=types.SimpleNamespace(get_dataset=lambda actor:{'version':'v1'})
  with patch.dict(sys.modules,{'stock_accounts.planning_assistant':planner}):
   memory.restore_saved_sources(store,None,report,dashboard,layout)
   memory.apply_layout(store,None,report,dashboard['tables'],list(dashboard['views'].values()),layout)
  self.assertEqual(len(calls),1);self.assertEqual(calls[0]['sources'][0]['table'],'NEWL');self.assertEqual(plan['sources'][0]['table'],'OLDL')
  self.assertNotEqual(definition['view'],30);self.assertEqual(report['sections'][0]['charts'][0]['evidence']['records'][0]['calc.Value'],160)
  self.assertTrue(report['sections'][0]['charts'][0]['saved']);self.assertEqual(dashboard['views'][30]['table'],'Different comparison')
if __name__=='__main__':unittest.main()
