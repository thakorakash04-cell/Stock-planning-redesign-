"""Exercise the real query engine; provider/UI imports are isolated, never called."""
import importlib,sys,types,unittest
from unittest.mock import patch

class UniqueBatchKpiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.prior={name:sys.modules.get(name) for name in ('grounded_ai','stock_accounts.insight_dashboard','stock_accounts.custom_insight')}
  cls.patches=patch.dict(sys.modules,{'streamlit':types.ModuleType('streamlit'),'requests':types.ModuleType('requests'),'stock_accounts.insights':types.SimpleNamespace(chart_result=lambda *a:None,chart_brief=lambda *a:None),'stock_accounts.monthly_kpi':types.SimpleNamespace(PROTOCOL='')})
  cls.patches.start()
  cls.dashboard=importlib.import_module('stock_accounts.insight_dashboard');cls.custom=importlib.import_module('stock_accounts.custom_insight')
 @classmethod
 def tearDownClass(cls):
  cls.patches.stop()
  for name,prior in cls.prior.items():
   if prior is not None:sys.modules[name]=prior
   else:
    loaded=sys.modules.pop(name,None)
    if '.' in name:
     parent,attribute=name.rsplit('.',1);package=sys.modules.get(parent)
     if package and getattr(package,attribute,None) is loaded:delattr(package,attribute)
 def setUp(self):
  self.table={'id':'UP','name':'Upcoming Production','headers':['Product','Batch'],'rows':[['P1','B1'],['P2','B1'],['P1','B2'],['P1',None],['P1',''],['P1','   '],['P2','001'],['P3','1']]}
  self.view={'view':3,'table':self.table['name'],'table_id':'UP','title':'Upcoming production'}
 def test_exact_request_uses_unique_nonblank_batches_without_gemini(self):
  with patch.object(self.custom,'settings',side_effect=AssertionError('No Gemini setup needed')),patch.object(self.custom,'generate',side_effect=AssertionError('No Gemini call')):
   result=self.custom.create([self.table],self.view,{},'ADD KPI For Total Unique Batch for Upcoming Production Order',[],'kpi')
  card=result['kpi'];self.assertEqual(card['value'],4);self.assertEqual(card['field'],'distinct_count(Batch)');self.assertEqual(card['evidence']['matched_records'],5);self.assertTrue(card['custom'])
 def test_empty_upcoming_table_is_zero(self):
  self.table['rows']=[]
  result=self.custom.create([self.table],self.view,{},'Total unique batches',[],'kpi');self.assertEqual(result['kpi']['value'],0)
 def test_scope_is_only_the_supplied_permitted_table(self):
  self.table['rows']=[['Permitted','VISIBLE']]
  result=self.custom.create([self.table],self.view,{},'Total unique upcoming batches',[],'kpi');self.assertEqual(result['kpi']['value'],1)
 def test_declared_metric_alias_and_normalized_output_are_resolved(self):
  for metric,value in [({'column':'Batch','op':'distinct_count','alias':'Unique Batches'},'unique batches'),({'field':'Batch','function':'count_distinct','alias':'Total batches'},'COUNT_DISTINCT( BATCH )'),({'column':'Batch','op':'distinct_count'},'DISTINCT_COUNT( batch )')]:
   result=self.dashboard.kpi_result([self.table],self.view,{'title':'Batches','value':value,'query':{'table':'UP','metrics':[metric],'filters':[{'column':'Batch','op':'not_blank','value':None}],'limit':1}})
   self.assertEqual(result['value'],4);self.assertEqual(result['field'],'distinct_count(Batch)')
 def test_other_conditions_or_ambiguous_headers_do_not_use_fast_path(self):
  for question in ['Count unique batches for Product A','Total unique batches excluding B1','Unique batches in November','Compare unique batches and quantity']:
   self.assertIsNone(self.custom.unique_upcoming_batch(self.table,question))
  self.assertIsNone(self.custom.unique_upcoming_batch({**self.table,'headers':['Batch','Product Batch']},'Total unique batches'))
  self.assertIsNone(self.custom.unique_upcoming_batch({**self.table,'name':'Stock'},'Total unique batches'))
 def test_unrelated_measure_and_grouped_kpi_remain_rejected(self):
  query={'table':'UP','metrics':[{'column':'Batch','op':'distinct_count'}],'limit':1}
  with self.assertRaisesRegex(ValueError,'Unsupported KPI measure'):self.dashboard.kpi_result([self.table],self.view,{'value':'sum(Quantity)','query':query})
  with self.assertRaisesRegex(ValueError,'whole-scope'):self.dashboard.kpi_result([self.table],self.view,{'value':'distinct_count(Batch)','query':{**query,'group_by':['Product']}})
