"""Calendar-month totals and exact invoice evidence use the same bounded query engine."""
import copy,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_full_insight_storage import chart_result,st,Store,memory
from grounded_ai import execute_query,normalize_query,ask,QueryPlanError
from stock_accounts.calendar_group import monthly_query,wants_month
from stock_accounts.insight_dashboard import mark_table
from stock_accounts.custom_insight import create
from openpyxl.utils.datetime import to_excel
TABLE={'id':'T1','name':'Primary Sales','headers':['Invoice Date','Invoice value','Segment','Cancelled'],'rows':[['01/06/2026',100,'AWC','N'],['20/06/2026',50,'AWC','N'],['2026-07-03',200,'AWC','N'],['2026-10-02',400,'AWC','N'],['2025-06-01',10,'AWC','N'],[to_excel(date(2026,6,25)),25,'AWC','N'],['2026-06-27',-20,'AWC','Y'],[None,5,'AWC','N']]}
VIEW={'view':20,'title':'Primary Sales','table':'Primary Sales','table_id':'T1'}
def plan():return {'table':'T1','group_by':['Invoice Date'],'metrics':[{'column':'Invoice value','op':'sum'}],'limit':20}
class MonthlyTests(unittest.TestCase):
 def test_months_are_calendar_totals_chronological_and_years_stay_separate(self):
  before=copy.deepcopy(TABLE);query=monthly_query([TABLE],'Month against the Invoice value',plan());result=execute_query([TABLE],query,all_rows=True)
  self.assertEqual([r['Month'] for r in result['records']],['Jun 2025','Jun 2026','Jul 2026','Oct 2026','Unknown month']);self.assertEqual([r['sum(Invoice value)'] for r in result['records']],[10,155,200,400,5]);self.assertEqual(result['matched_records'],8);self.assertIn('1 missing/invalid',result['note']);self.assertEqual(TABLE,before)
  descending=execute_query([TABLE],{**query,'descending':True},all_rows=True);self.assertEqual(descending['records'][-1]['Month'],'Unknown month');self.assertEqual(descending['records'][0]['Month'],'Oct 2026')
  self.assertEqual(monthly_query([TABLE],'date-wise invoice value for this month',plan()),plan());self.assertFalse(wants_month('show this month invoices'))
 def test_date_mark_returns_only_the_clicked_month_and_keeps_original_dates(self):
  q=monthly_query([TABLE],'monthly invoice value',plan());chart=chart_result([TABLE],VIEW,{'title':'Monthly sales','type':'line','label':'Month','value':'sum(Invoice value)','query':q});self.assertEqual(chart['type'],'column','an unknown-date category must not form a dated line')
  dated={**TABLE,'rows':TABLE['rows'][:-1]};trend=chart_result([dated],VIEW,{'title':'Monthly trend','type':'line','label':'Month','value':'sum(Invoice value)','query':q});self.assertEqual(trend['type'],'line');self.assertEqual([r['Month'] for r in trend['evidence']['records']],['Jun 2025','Jun 2026','Jul 2026','Oct 2026'])
  entry={'source_table':TABLE,'query':chart['evidence']['query'],'marks':chart['evidence']['records']};index=next(i for i,r in enumerate(entry['marks']) if r['Month']=='Jun 2026');matched,_=mark_table(entry,{'mark':index});self.assertEqual(len(matched['rows']),4);self.assertTrue(all(r[-1]=='Jun 2026' for r in matched['rows']));self.assertIn('01/06/2026',[r[0] for r in matched['rows']]);self.assertEqual(execute_query([matched],q,all_rows=True)['records'][0]['sum(Invoice value)'],155)
 def test_month_year_sources_and_ambiguous_dates_are_safe(self):
  table={'id':'T1','name':'Monthly Sales','headers':['Month','Year','Invoice value'],'rows':[['June',2026,10],['Jun',2026,20],[7.0,2026.0,30],['June',2025,40],['June, July',2026,5]]};q=monthly_query([table],'monthly invoice value',{'table':'T1','columns':['Month','Invoice value'],'limit':20},'Invoice value');result=execute_query([table],q,all_rows=True);self.assertEqual([r['Calendar Month'] for r in result['records']],['Jun 2025','Jun 2026','Jul 2026','Unknown month']);self.assertEqual(result['records'][1]['sum(Invoice value)'],30)
  with self.assertRaisesRegex(QueryPlanError,'explicit Year'):execute_query([table],{'table':'T1','date_group':{'column':'Month','grain':'month','alias':'Bucket'},'group_by':['Bucket'],'metrics':[{'column':'Invoice value','op':'sum'}]})
  ambiguous={**TABLE,'headers':['Posting Date','Dispatch Date','Invoice value'],'rows':[]}
  with self.assertRaisesRegex(ValueError,'date field'):monthly_query([ambiguous],'monthly invoice value',{'table':'T1','metrics':[{'column':'Invoice value','op':'sum'}]})
  with self.assertRaises(QueryPlanError):execute_query([TABLE],{**plan(),'date_group':{'column':'Invoice Date','grain':'eval','alias':'Month'}})
 def test_ask_ai_repairs_daily_grain_without_an_extra_provider_call(self):
  with patch('grounded_ai.settings',return_value=('key','model')),patch('grounded_ai.generate',side_effect=[{'queries':[plan()]},'Monthly totals are shown.']) as provider:
   result=ask([TABLE],'add graph of Month against Invoice value');self.assertEqual(len(result['evidence'][0]['records']),5);self.assertEqual(provider.call_count,2);self.assertIn('Jun 2026',str(provider.call_args_list[1].args[3]['evidence']))
 def test_manual_graph_replaces_raw_dates_with_month_sums_and_retains_saved_query(self):
  raw={'chart':{'title':'Monthly invoice value','type':'column','label':'Invoice Date','value':'Invoice value','query':{'table':'T1','columns':['Invoice Date','Invoice value'],'limit':10}}}
  with patch('stock_accounts.custom_insight.settings',return_value=('key','model')),patch('stock_accounts.custom_insight.generate',side_effect=[raw,{}]):result=create([TABLE],VIEW,{},'Add graph of Month against Invoice value',[])['chart']
  self.assertEqual(result['label'],'Month');self.assertEqual(result['value'],'sum(Invoice value)');self.assertEqual(result['evidence']['shown_rows'],5);self.assertEqual(result['evidence']['query']['date_group']['column'],'Invoice Date')
 def test_sales_tool_uses_the_same_monthly_arithmetic(self):
  from stock_accounts.sales import summarize
  loaded={'available':True,'rows':TABLE['rows'],'headers':TABLE['headers'],'segmentIndex':2,'source':{'version':'sales1'}}
  with patch('stock_accounts.sales.read',return_value=loaded):result=summarize(None,None,{'kind':'primary','statistic':'sum','value':'Invoice value','date_group':{'column':'Invoice Date','grain':'month','alias':'Month'}})
  self.assertEqual(result['rows'][1],['Jun 2026',155,4]);self.assertEqual(result['source']['version'],'sales1')
 def test_monthly_saved_graph_recalculates_and_keeps_matching_records(self):
  table={**TABLE,'rows':TABLE['rows'][:-1]};query=monthly_query([table],'month against Invoice value',plan());chart=chart_result([table],VIEW,{'title':'Monthly invoice value','type':'line','label':'Month','value':'sum(Invoice value)','query':query})
  planner=types.SimpleNamespace(knowledge=lambda:{'revision':'rules1'});assistant=types.SimpleNamespace(report_scope=lambda s,a:'scope',data_revision=lambda s,a:'rev1')
  with tempfile.TemporaryDirectory() as folder:
   store=Store('sqlite:///'+str(Path(folder)/'db'));store.bootstrap_admin('admin_user','Test-admin-password!123');actor=store.login('admin_user','Test-admin-password!123');st.session_state.clear()
   with store.transaction() as db:store.run(db,"INSERT INTO datasets(id,payload,filename,version,uploaded_by,updated_at) VALUES('current','unused','book.xlsx','v1','admin_user',1)")
   section={'view':20,'title':'Primary Sales','records':7,'charts':[chart],'kpis':[]};report={'report_id':'r1','version':'v1','knowledge_revision':'rules1','sections':[section]};dashboard={'version':'v1','scope':'scope','planning_revision':'rev1','knowledge_revision':'rules1','tables':[table],'views':{20:VIEW},'sections':[section],'context':{}}
   with patch.dict(sys.modules,{'stock_accounts.planning_assistant':planner,'stock_accounts.assistant_insights':assistant}),patch.object(store,'get_dataset',return_value={'version':'v1'}):
    memory.save(store,actor,report,dashboard);loaded=memory.restore(store,actor,'v1');selected=loaded['sections'][0]['charts'][0]
    reply=memory.fast_edit(store,actor,{'action':'save_insight_item','compact':True,'report_id':loaded['report_id'],'version':'v1','view':20,'chart_id':selected['id'],'chart_type':'line'},'v1');self.assertEqual(reply['chart_type'],'line')
    st.session_state.clear();again=memory.restore(store,actor,'v1');self.assertTrue(again['sections'][0]['charts'][0]['saved']);self.assertIn('date_group',again['sections'][0]['charts'][0]['evidence']['query'])
    newer={**table,'rows':table['rows']+[['2026-06-30',1000,'AWC','N']]};new_report={'sections':[{'view':20,'title':'Primary Sales','charts':[],'kpis':[]}]};memory.apply_layout(store,actor,new_report,[newer],[VIEW]);records=new_report['sections'][0]['charts'][0]['evidence']['records'];self.assertEqual(next(r['sum(Invoice value)'] for r in records if r['Month']=='Jun 2026'),1155)
if __name__=='__main__':unittest.main()
