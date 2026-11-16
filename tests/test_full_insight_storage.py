"""Full-result graphs, bounded interpretation and saved KPI layout against real SQL."""
import copy,importlib.util,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
# Streamlit's session transport is isolated; query arithmetic and SQL stay real.
if importlib.util.find_spec('streamlit') is None:
 st=types.ModuleType('streamlit');st.session_state={};st.secrets={};sys.modules['streamlit']=st
import streamlit as st
if importlib.util.find_spec('requests') is None:sys.modules['requests']=types.SimpleNamespace()
from stock_accounts.insights import chart_result,chart_brief
from stock_accounts.insight_dashboard import kpi_result,mark_table,refresh
from stock_accounts.custom_insight import create
from stock_accounts.store import Store
from stock_accounts import insight_memory as memory
TABLE={'id':'T1','name':'Stock','headers':['Material','Qty','Unit'],'rows':[[f'M{i:03}',i+1,'EA'] for i in range(300)]}
VIEW={'view':0,'table_id':'T1','table':'Stock','title':'Stock overview'}
def spec():return {'title':'All material quantities','type':'bar','label':'Material','value':'Qty','query':{'table':'T1','columns':['Material','Qty'],'sort_by':'Qty','descending':True,'limit':5}}
def card_spec():return {'title':'Total quantity','value':'sum(Qty)','basis':'All stock records, EA','query':{'table':'T1','metrics':[{'column':'Qty','op':'sum'}],'limit':1}}
class CompleteInsightTests(unittest.TestCase):
 def test_all_300_marks_are_retained_despite_small_model_limit_and_late_mark_drills(self):
  chart=chart_result([TABLE],VIEW,spec());e=chart['evidence'];self.assertEqual(e['shown_rows'],300);self.assertEqual(e['result_rows'],300)
  self.assertEqual(e['records'][-1]['Material'],'M000');table,query=mark_table({'source_table':TABLE,'query':e['query'],'marks':e['records']},{'mark':299});self.assertEqual(table['rows'][0][0],'M000')
  preview=chart_brief(chart);self.assertEqual(len(preview['evidence']['records']),20);self.assertTrue(preview['evidence']['interpretation_preview']);self.assertEqual(preview['evidence']['full_result_extrema']['maximum']['Qty'],300);self.assertEqual(len(chart['evidence']['records']),300)
 def test_large_composition_becomes_readable_bars_and_explicit_top_count_is_honoured(self):
  chart=chart_result([TABLE],VIEW,{'title':'Material counts','type':'donut','label':'Material','value':'count(*)','query':{'table':'T1','group_by':['Material'],'metrics':[{'column':'*','op':'count'}],'limit':10}});self.assertEqual(chart['type'],'bar');self.assertEqual(chart['evidence']['shown_rows'],300)
  request={'chart':spec()}
  with patch('stock_accounts.custom_insight.settings',return_value=('key','model')),patch('stock_accounts.custom_insight.generate',side_effect=[request,{}]):top=create([TABLE],VIEW,{},'Show top 7 materials by Qty',[])['chart']
  self.assertEqual(top['evidence']['shown_rows'],7);self.assertEqual(top['evidence']['result_rows'],300)
  with patch('stock_accounts.custom_insight.settings',return_value=('key','model')),patch('stock_accounts.custom_insight.generate',side_effect=[request,{}]):complete=create([TABLE],VIEW,{},'Compare all materials by Qty',[])['chart']
  self.assertEqual(complete['evidence']['shown_rows'],300)
 def test_kpi_uses_all_rows_and_rejects_unsafe_unit_rate_and_repeated_stock_sums(self):
  with patch('stock_accounts.custom_insight.settings',return_value=('key','model')),patch('stock_accounts.custom_insight.generate',return_value={'kpi':card_spec()}):card=create([TABLE],VIEW,{},'Add total stock quantity in EA',[],'kpi')['kpi']
  self.assertEqual(card['value'],45150);self.assertTrue(card['custom'])
  mixed=copy.deepcopy(TABLE);mixed['rows'][-1][-1]='KG'
  with self.assertRaisesRegex(ValueError,'unit/currency'):kpi_result([mixed],VIEW,card_spec())
  forecast=copy.deepcopy(TABLE);forecast['rows'].append(copy.deepcopy(forecast['rows'][0]));forecast.update(name='Forecast Planning',headers=['Material','Current Stock','Unit']);view={**VIEW,'table':forecast['name']}
  bad={'value':'sum(Current Stock)','query':{'table':'T1','metrics':[{'column':'Current Stock','op':'sum'}],'limit':1}}
  with self.assertRaisesRegex(ValueError,'Repeated forecast'):kpi_result([forecast],view,bad)
 def test_kpi_rejects_mixed_currency_and_mixed_pnl_measures(self):
  currency={'id':'T1','name':'Sales','headers':['Amount','Currency'],'rows':[[10,'INR'],[20,'USD']]}
  with self.assertRaisesRegex(ValueError,'unit/currency'):kpi_result([currency],VIEW,{'value':'sum(Amount)','query':{'table':'T1','metrics':[{'column':'Amount','op':'sum'}],'limit':1}})
  pnl={'id':'T1','name':'PnL','headers':['Particulars','Value'],'rows':[['Sales',100],['EBIDTA',30]]}
  specification={'value':'sum(Value)','query':{'table':'T1','metrics':[{'column':'Value','op':'sum'}],'limit':1}}
  with self.assertRaisesRegex(ValueError,'one PnL'):kpi_result([pnl],VIEW,specification)
  ratio={**pnl,'rows':[['EBIDTA %',30],['EBIDTA %',35]]}
  with self.assertRaisesRegex(ValueError,'cannot be summed'):kpi_result([ratio],VIEW,specification)
 def test_kpi_save_restore_filter_delete_regeneration_and_access_revocation(self):
  assistant=types.SimpleNamespace(report_scope=lambda s,a:'scope',data_revision=lambda s,a:'sources1')
  planner=types.SimpleNamespace(knowledge=lambda:{'revision':'rules1'})
  with tempfile.TemporaryDirectory() as folder:
   store=Store('sqlite:///'+str(Path(folder)/'db'));store.bootstrap_admin('admin_user','Test-admin-password!123');admin=store.login('admin_user','Test-admin-password!123');store.create_viewer(admin,'viewer_user','Test-viewer-password!123');actor=store.login('viewer_user','Test-viewer-password!123')
   st.session_state.clear();section={'view':0,'title':'Stock overview','records':300,'charts':[chart_result([TABLE],VIEW,spec())],'kpis':[],'facets':[]}
   dashboard={'version':'v1','scope':'scope','planning_revision':'sources1','knowledge_revision':'rules1','tables':[TABLE],'views':{0:VIEW},'context':{},'sections':[section]}
   report={'version':'v1','report_id':'r1','sections':[section],'generated_at':'saved'}
   with patch.dict(sys.modules,{'stock_accounts.assistant_insights':assistant,'stock_accounts.planning_assistant':planner}),patch.object(store,'get_dataset',return_value={'version':'v1'}):
    memory.save(store,actor,report,dashboard);loaded=memory.restore(store,actor,'v1')
    result=memory.edit(store,actor,{'report_id':loaded['report_id'],'view':0,'version':'v1','question':'Total quantity'},'v1',kpi=kpi_result([TABLE],VIEW,card_spec()))
    self.assertEqual(result['report']['sections'][0]['kpis'][0]['value'],45150)
    st.session_state.clear();restored=memory.restore(store,actor,'v1');card=restored['sections'][0]['kpis'][0];self.assertTrue(card['id']);self.assertTrue(card['custom']);self.assertTrue(card['evidence']['source_id'])
    fresh=copy.deepcopy(TABLE);fresh['id']='CURRENT';fresh['rows']=[[r[0],r[1]*2,r[2]] for r in fresh['rows']]
    recalculated={'sections':[copy.deepcopy(section)]};memory.apply_layout(store,actor,recalculated,[fresh],[{**VIEW,'table_id':'CURRENT'}]);self.assertEqual(recalculated['sections'][0]['kpis'][0]['value'],90300);self.assertEqual(recalculated['sections'][0]['kpis'][0]['id'],card['id'])
    filtered=refresh(store,actor,{'report_id':restored['report_id'],'view':0,'version':'v1','filters':[{'column':'Material','op':'eq','value':'M299'}]},'v1')['section'];self.assertEqual(filtered['kpis'][0]['value'],300);self.assertEqual(filtered['kpis'][0]['id'],card['id'])
    deleted=memory.edit(store,actor,{'report_id':restored['report_id'],'view':0,'version':'v1','item_kind':'kpi','kpi_id':card['id']},'v1')['report'];self.assertEqual(deleted['sections'][0]['kpis'],[])
    regeneration={'sections':[copy.deepcopy(section)]};memory.apply_layout(store,actor,regeneration,[TABLE],[VIEW]);self.assertEqual(regeneration['sections'][0]['kpis'],[])
    with store.transaction() as db:layout=json.loads(store.run(db,'SELECT layout FROM insight_memory').fetchone()['layout'])
    self.assertIn(card['id'],layout['deleted_kpis'])
    store.update_permissions(admin,'viewer_user',{'menu_8':False});revoked=store.login('viewer_user','Test-viewer-password!123')
    with self.assertRaises(PermissionError):memory.restore(store,revoked,'v1')
if __name__=='__main__':unittest.main()
