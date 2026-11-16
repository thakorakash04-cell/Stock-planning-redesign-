import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from stock_accounts.workspace_delivery import prepared,payload,model_scope

class DeliveryTests(unittest.TestCase):
 def setUp(self):
  self.store=SimpleNamespace();self.current={'version':'v1','updated_at':1,'_scope':'segment-a'}
  self.identity={'username':'viewer','role':'viewer','permissions':{'menu_10':True},'allowedSegments':['Segment A']}
 def test_prepared_display_is_reused_but_invalidates_and_cannot_be_mutated(self):
  builder=Mock(return_value=({'sheets':[{'rows':[['A',10]]}]},[],'v1'))
  a=prepared(self.store,self.current,self.identity,[],builder);a[0]['sheets'][0]['rows'][0][1]=999
  self.assertEqual(prepared(self.store,self.current,self.identity,[],builder)[0]['sheets'][0]['rows'][0][1],10)
  self.assertEqual(builder.call_count,1)
  for current,identity,overrides in [({**self.current,'updated_at':2},self.identity,[]),(self.current,{**self.identity,'allowedSegments':['Segment B']},[]),(self.current,{**self.identity,'permissions':{'menu_10':False}},[]),(self.current,self.identity,[{'kind':'ongoing','id':'o','revision':2,'updated_at':3}])]:prepared(self.store,current,identity,overrides,builder)
  self.assertEqual(builder.call_count,5)
  self.assertLessEqual(len(self.store._prepared_workspace_cache),4)
  other=SimpleNamespace();prepared(other,self.current,self.identity,[],builder);self.assertEqual(builder.call_count,6)
 def test_oversized_result_is_not_cached(self):
  builder=Mock(return_value=({'large':'x'*500},[],'v1'))
  with patch('stock_accounts.workspace_delivery.MAX_BYTES',20):
   prepared(self.store,self.current,self.identity,[],builder);prepared(self.store,self.current,self.identity,[],builder)
  self.assertEqual(builder.call_count,2)
 def test_existing_rpc_ack_omits_payload_and_missing_browser_can_recover(self):
  state={'_workspace_payload':(('scope','v1','availability-v1'),None)};data={'productCatalogue':{'version':'c1'},'portal':{'title':'Stock'}};tables=[{'rows':[['A',1]]}]
  initial=payload(state,None,data,tables,'v1',self.identity);self.assertIsNone(initial['data']);self.assertTrue(initial['dataDeferred']);self.assertTrue(initial['contentId']);
  first=payload(state,{'action':'workspace_bootstrap'},data,tables,'v1',self.identity);self.assertIs(first['data'],data);self.assertIsNone(first['tables']);self.assertTrue(first['tablesDeferred']);self.assertEqual(first['modelScope'],model_scope(self.identity,'v1'))
  ack={'action':'heartbeat','knownBootstrapId':first['bootstrapId']}
  compact=payload(state,ack,data,tables,'v1',self.identity);self.assertIsNone(compact['data']);self.assertIsNone(compact['tables'])
  recovered=payload(state,{'action':'workspace_bootstrap'},data,tables,'v1',self.identity);self.assertIs(recovered['data'],data);self.assertIsNone(recovered['tables'])
  payload(state,ack,data,tables,'v1',self.identity)
  for changed in ({**data,'productCatalogue':{'version':'c2'}},{**data,'portal':{'title':'Renamed'}}):self.assertIsNotNone(payload(state,ack,changed,tables,'v1',self.identity)['data'])
  state['_workspace_payload']=(('scope','v1','availability-v2'),None)
  self.assertIsNotNone(payload(state,ack,data,tables,'v1',self.identity)['data'])

 def test_content_fingerprint_survives_new_login_but_not_data_or_access_changes(self):
  key=('viewer','session1',('v1',1),'permissions',27,(),'plans','segments','availability')
  data={'productCatalogue':{'version':'c1'},'portal':{'title':'Stock'}}
  first=payload({'_workspace_payload':(key,None)},None,data,[],'v1',self.identity)
  newer=(key[0],'session2',*key[2:]);second=payload({'_workspace_payload':(newer,None)},None,data,[],'v1',self.identity)
  self.assertNotEqual(first['bootstrapId'],second['bootstrapId']);self.assertEqual(first['contentId'],second['contentId'])
  edited=(*newer[:6],'new plans',*newer[7:]);third=payload({'_workspace_payload':(edited,None)},None,data,[],'v1',self.identity);self.assertNotEqual(first['contentId'],third['contentId'])
  narrowed={**self.identity,'allowedSegments':['Segment B']};fourth=payload({'_workspace_payload':(key,None)},None,data,[],'v1',narrowed);self.assertNotEqual(first['contentId'],fourth['contentId'])
