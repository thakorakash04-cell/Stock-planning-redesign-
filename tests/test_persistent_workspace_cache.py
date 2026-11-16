import unittest
from unittest.mock import Mock,MagicMock,patch
from contextlib import ExitStack
from stock_accounts.workspace import workspace_payload
from stock_accounts.store import AccessDenied
class PersistentWorkspaceTests(unittest.TestCase):
 def setUp(self):
  self.store=Mock();self.store.identity.return_value={'username':'viewer','role':'viewer','permissions':{},'allowedSegments':None};self.store.transaction=MagicMock();self.store.run.return_value.fetchone.return_value={'version':'v1','updated_at':1};self.store.get_dataset.return_value=None;self.store.portal_read.return_value={};self.actor=Mock(username='viewer',session_id='first');self.state={};self.stack=ExitStack();self.addCleanup(self.stack.close)
  self.stack.enter_context(patch('stock_accounts.workspace.st.session_state',self.state));self.day=self.stack.enter_context(patch('time.time',return_value=1793442600));self.stack.enter_context(patch('stock_accounts.product_catalog.metadata',return_value='empty'));self.stack.enter_context(patch('stock_accounts.product_catalog.read',return_value={'version':'empty','products':[]}));self.shared=self.stack.enter_context(patch('stock_accounts.production.shared',return_value=[]));self.stack.enter_context(patch('stock_accounts.availability_cache.revision',return_value=''));self.build=self.stack.enter_context(patch('stock_accounts.workspace.ui_payload',return_value=({'sheets':[{'rows':[['A',10]]}]},[{'headers':['Code'],'rows':[['A']]}],'v1')))
 def fresh(self):self.state.clear();self.actor.session_id='next';return workspace_payload(self.store,self.actor)
 def test_refresh_reuses_full_prepared_data_and_models_without_loading_master(self):
  first=workspace_payload(self.store,self.actor);first[0]['sheets'][0]['rows'][0][1]=999
  again=self.fresh();self.assertEqual(again[0]['sheets'][0]['rows'][0][1],10);self.assertEqual(again[1][0]['rows'],[['A']]);self.assertEqual(self.build.call_count,1);self.assertEqual(self.store.get_dataset.call_count,1);self.assertNotIn('cacheDay',again[0])
  self.store.require.side_effect=AccessDenied('Revoked')
  with self.assertRaises(AccessDenied):self.fresh()
 def test_day_source_edit_and_access_changes_invalidate(self):
  workspace_payload(self.store,self.actor);self.day.return_value+=86400;self.fresh();self.assertEqual(self.build.call_count,1)
  self.store.run.return_value.fetchone.return_value={'version':'v2','updated_at':2};self.fresh();self.assertEqual(self.build.call_count,2)
  self.shared.return_value=[{'kind':'ongoing','id':'o','revision':2,'updated_at':3}];self.fresh();self.assertEqual(self.build.call_count,3)
  self.store.identity.return_value={**self.store.identity.return_value,'allowedSegments':['A']};self.fresh();self.assertEqual(self.build.call_count,4)
 def test_oversize_falls_back_instead_of_claiming_cache(self):
  with patch('stock_accounts.workspace_delivery.RETAINED_MAX_BYTES',1):workspace_payload(self.store,self.actor);self.fresh()
  self.assertEqual(self.build.call_count,2)
if __name__=='__main__':unittest.main()
