import copy,sys,types,unittest
from unittest.mock import patch
from stock_accounts import dashboard_builder as builder
class DashboardBuilderTests(unittest.TestCase):
 def test_authorized_scope(self):
  views=[{'view':v} for v in [0,5,12,20]]
  self.assertEqual(builder.select_views(views,{'template':'production'}),[{'view':12}])
  self.assertEqual(builder.select_views(views,{'template':'custom','views':[20,99]}),[{'view':20}])
  self.assertEqual(builder.select_views(views,{'template':'current'}),views)
 def test_validation(self):
  for config in [{'template':'unknown'},{'views':[True]},{'question':'x'*2001},{'views':'0'}]:
   with self.assertRaises(ValueError):builder.configuration(config)
 def fixture(self):
  return {'sections':[{'view':0,'title':'Stock','filters':[{'column':'Qty','op':'gt','value':0}]},{'view':5,'title':'Purchase','filters':[]}],'views':{0:{'table':'Stock'},5:{'table':'Purchase'}},'tables':[{'name':'Stock','headers':['Segment','Qty']},{'name':'Purchase','headers':['Qty']}],'active_tables':{},'active_filters':{}}
 def test_filters_keep_local_and_skip_missing_field(self):
  saved=self.fixture();calls=[]
  def refresh(store,actor,event,version):
   calls.append(event);return {'section':{**next(s for s in saved['sections'] if s['view']==event['view']),'filters':event['filters']}}
  helper=types.SimpleNamespace(refresh=refresh,filter_table=lambda *a:None,validate_entry=lambda *a:None)
  with patch.object(builder,'_dashboard',return_value=saved),patch.dict(sys.modules,{'stock_accounts.insight_dashboard':helper}):
   result=builder.common_filters(None,None,{'report_id':'r','views':[0,5],'filters':[{'column':'Segment','op':'in','value':['A']}]},'v')
  self.assertEqual(len(calls[0]['filters']),2);self.assertEqual(calls[1]['filters'],[]);self.assertEqual(result['skipped'],[{'view':5,'title':'Purchase'}])
 def test_failure_rolls_back(self):
  saved=self.fixture();before=copy.deepcopy(saved)
  def refresh(store,actor,event,version):
   saved['active_tables']['new']=3;saved['sections']=[{'view':0,'title':'modified'}]
   if event['view']==5:raise ValueError('failed')
   return {'section':saved['sections'][0]}
  with patch.object(builder,'_dashboard',return_value=saved),patch.dict(sys.modules,{'stock_accounts.insight_dashboard':types.SimpleNamespace(refresh=refresh,filter_table=lambda *a:None,validate_entry=lambda *a:None)}):
   with self.assertRaisesRegex(ValueError,'failed'):builder.common_filters(None,None,{'report_id':'r','views':[0,5]},'v')
  self.assertEqual(saved,before)
if __name__=='__main__':unittest.main()
