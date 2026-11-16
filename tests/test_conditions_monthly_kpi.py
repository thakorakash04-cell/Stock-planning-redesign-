import copy,sys,unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_monthly_insights import TABLE,VIEW
from stock_accounts.insight_dashboard import filter_table,kpi_result,mark_table
from stock_accounts.monthly_kpi import proposal,needs_refresh
from stock_accounts.insight_memory import kpi_spec,kpi_id
class Tests(unittest.TestCase):
 def test_conditions_intersect_choices_and_dates_and_numbers(self):
  rows=filter_table(TABLE,[{'column':'Segment','op':'in','value':['AWC']},{'column':'Invoice Date','op':'date_between','value':['2026-06-01','2026-06-30']},{'column':'Invoice value','op':'number_between','value':[20,100]}])['rows'];self.assertEqual([r[1] for r in rows],[100,50,25])
  self.assertEqual(len(filter_table(TABLE,[{'column':'Invoice Date','op':'date_blank','value':None}])['rows']),1)
  for rule in [{'column':'Invoice value','op':'number_between','value':[4,1]},{'column':'Invoice Date','op':'date_between','value':['2026-02-30','2026-03-01']}]:
   with self.assertRaises(ValueError):filter_table(TABLE,[rule])
 def test_month_over_month_evidence_and_persistent_definition(self):
  table={**TABLE,'rows':TABLE['rows']+[['2026-09-01',200,'AWC','N']]}
  spec=proposal(table,'Current Month Sales Value with Percentage growth from Last month Sales value')
  with patch('stock_accounts.monthly_kpi.current_month',return_value='2026-10'):card=kpi_result([table],VIEW,spec)
  self.assertEqual(card['value'],400);self.assertEqual(card['comparison_result']['growth_percent'],100);self.assertEqual(card['comparison_result']['previous_value'],200)
  for evidence,month in [(card['evidence'],'Oct 2026'),(card['comparison_evidence'],'Sep 2026')]:self.assertEqual(evidence['query']['filters'][-1]['value'],month)
  definition=kpi_spec(card);self.assertNotIn('date_group',definition['query']);self.assertEqual(definition['comparison']['reference_month'],'current')
  with patch('stock_accounts.monthly_kpi.current_month',return_value='2026-11'):
   updated=kpi_result([table],VIEW,definition);self.assertTrue(needs_refresh({'sections':[{'kpis':[card]}]}));self.assertIsNone(updated['value']);self.assertEqual(updated['comparison_result']['previous_value'],400);self.assertEqual(kpi_id(20,card,[table]),kpi_id(20,updated,[table]))
 def test_model_unsupported_reply_is_repaired_without_an_extra_request(self):
  from stock_accounts.custom_insight import create
  table={**TABLE,'rows':TABLE['rows']+[['2026-09-01',200,'AWC','N']]}
  with patch('stock_accounts.custom_insight.settings',return_value=('key','model')),patch('stock_accounts.custom_insight.generate',return_value={'kpi':None,'clarification':'Unsupported calculation'}) as model,patch('stock_accounts.monthly_kpi.current_month',return_value='2026-10'):
   result=create([table],VIEW,{},'Current month sales value with percentage growth from last month',[],kind='kpi')
  self.assertEqual(model.call_count,1);self.assertEqual(result['kpi']['comparison_result']['growth_percent'],100)
 def test_january_and_zero_baseline(self):
  table={**TABLE,'rows':[['2025-12-02',0,'AWC','N'],['2026-01-03',10,'AWC','N']]};spec=proposal(table,'this month sales value percentage growth')
  with patch('stock_accounts.monthly_kpi.current_month',return_value='2026-01'):card=kpi_result([table],VIEW,spec)
  self.assertEqual(card['comparison_result']['previous_month'],'2025-12');self.assertIsNone(card['comparison_result']['growth_percent']);self.assertEqual(card['value'],10)
if __name__=='__main__':unittest.main()
