import sys,types,unittest
from unittest.mock import patch
import test_unique_batch_kpi as baseline
class DashboardEvidenceTests(baseline.UniqueBatchKpiTests):
 def test_restored_evidence_respects_saved_section_filter(self):
  table={'id':'T','name':'Stock','headers':['Material','Segment','Qty'],'rows':[['A','Alpha',3],['B','Beta',9]]}
  evidence={'query':{'table':'T','columns':['Material','Qty'],'limit':20},'records':[{'Material':'A','Qty':3}]}
  section={'filters':[{'column':'Segment','op':'eq','value':'Alpha'}],'charts':[{'evidence':evidence}]}
  state={};assistant=types.SimpleNamespace(report_scope=lambda *a:'scope',data_revision=lambda *a:'1');knowledge=types.SimpleNamespace(knowledge=lambda:{'revision':'r'})
  with patch.dict(sys.modules,{'streamlit':types.SimpleNamespace(session_state=state),'stock_accounts.assistant_insights':assistant,'stock_accounts.planning_assistant':knowledge}):
   self.dashboard.register(types.SimpleNamespace(identity=lambda actor:{'role':'admin'}),'user',section,[table],'v')
  entry=state['_stock_insight_sources'][evidence['source_id']]
  self.assertEqual(entry['source_table']['rows'],[['A','Alpha',3]])
  self.assertEqual(state['_stock_ai_exports'][evidence['export_id']]['source_table']['rows'],[['A','Alpha',3]])
if __name__=='__main__':unittest.main()
