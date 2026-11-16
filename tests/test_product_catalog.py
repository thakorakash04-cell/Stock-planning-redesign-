import json,tempfile,unittest
from unittest.mock import patch
from stock_accounts.store import Store,AccessDenied
from stock_accounts.product_catalog import publish,read,metadata,read_detail
PASSWORD='ProductCatalogPassword123!'
class ProductCatalogTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store('sqlite:///'+self.tmp.name+'/source.sqlite');self.store.bootstrap_admin('admin',PASSWORD);self.actor=self.store.login('admin',PASSWORD)
  self.products=[{'id':'p1','name':'Dressing','division':'General Wound Care','sections':[{'kind':'variants','rows':[{'code':'001'}],'hasSfg':True,'sfgRows':[{'code':'S1'}]}]},{'id':'p2','name':'Pouch','division':'Ostomy','sections':[{'kind':'variants','rows':[{'code':'002'}]}]}]
 def tearDown(self):self.tmp.cleanup()
 def test_versioned_names_scope_and_no_private_data(self):
  self.assertEqual(metadata(self.store,self.actor),'empty')
  first=publish(self.store,self.actor,self.products,'https://products.example/app?token=removed#old')
  with patch.object(self.store,'run',wraps=self.store.run) as run:
   self.assertEqual(first,publish(self.store,self.actor,self.products,'https://products.example/app'))
   self.assertFalse(any('INSERT INTO stock_product_snapshots' in c.args[1] for c in run.call_args_list),'Unchanged snapshots must not be re-transmitted')
  result=read(self.store,self.actor);self.assertEqual(result['products'][0]['codes'],['001','S1']);self.assertEqual(result['products'][0]['url'],'https://products.example/app');self.assertNotIn('sections',str(result))
  with patch.object(self.store,'identity',return_value={'role':'viewer','permissions':{},'allowedSegments':['Ostomy Care']}):
   scoped=read(self.store,self.actor);self.assertEqual([p['id'] for p in scoped['products']],['p2']);self.assertNotEqual(scoped['version'],result['version'])
  self.products[0]['name']='New dressing';second=publish(self.store,self.actor,self.products,'https://products.example/app');self.assertNotEqual(first['version'],second['version']);self.assertEqual(read(self.store,self.actor)['products'][0]['name'],'New dressing')
 def test_payload_only_downloads_after_version_change_and_revocation_is_live(self):
  publish(self.store,self.actor,self.products,'https://products.example')
  with patch.object(self.store,'run',wraps=self.store.run) as run:
   read(self.store,self.actor);read(self.store,self.actor)
   self.assertEqual(sum('SELECT payload FROM stock_product_catalog' in c.args[1] for c in run.call_args_list),1)
  with self.store.transaction() as db:self.store.run(db,"UPDATE accounts SET active=0 WHERE username='admin'")
  with self.assertRaises(AccessDenied):read(self.store,self.actor)

 def test_detail_cache_live_grants_scope_version_and_removed_product(self):
  self.products[0]['sections']+=[{'id':'fields','tab':'portfolio','kind':'fields','title':'Dossier','fields':[{'id':'moc','label':'Material','value':'Silicone'}]},{'id':'ready','tab':'readiness','kind':'status','title':'Qualification','items':[{'id':'q','title':'QMS','status':'Completed','remark':'Approved','evidence':'https://files.example/report'}]},{'id':'cost-note','tab':'bom','kind':'fields','fields':[]},{'id':'brief','tab':'portfolio','kind':'briefs','rows':[{'name':'Example','images':['private-image-bytes']}]}]
  publish(self.store,self.actor,self.products,'https://products.example')
  first=read_detail(self.store,self.actor,{'productId':'p1'})
  self.assertEqual(first['product']['documentLinks'][0]['remark'],'Approved')
  self.assertNotIn('private-image-bytes',str(first))
  with patch.object(self.store,'run',wraps=self.store.run) as run:
   read_detail(self.store,self.actor,{'productId':'p1'})
   self.assertFalse(any('SELECT payload,updated_at FROM stock_product_snapshots' in c.args[1] for c in run.call_args_list))
  self.assertTrue(read_detail(self.store,self.actor,{'productId':'p1','knownVersion':first['version'],'accessVersion':read(self.store,self.actor)['accessVersion']})['notModified'])
  with patch.object(self.store,'identity',return_value={'role':'viewer','permissions':{},'allowedSegments':['General Wound Care']}):
   with self.assertRaises(AccessDenied):read_detail(self.store,self.actor,{'productId':'p1'})
  with patch.object(self.store,'identity',return_value={'role':'viewer','permissions':{'view_product_details':True,'menu_1':False},'allowedSegments':['General Wound Care']}):
   scoped=read_detail(self.store,self.actor,{'productId':'p1','knownVersion':first['version'],'accessVersion':first['accessVersion']});self.assertNotIn('notModified',scoped);self.assertFalse(any(s.get('tab')=='bom' for s in scoped['product']['sections']))
   with self.assertRaises(AccessDenied):read_detail(self.store,self.actor,{'productId':'p2'})
  self.products[0]['name']='Changed dossier';publish(self.store,self.actor,self.products,'https://products.example')
  self.assertNotEqual(read_detail(self.store,self.actor,{'productId':'p1'})['version'],first['version'])
  publish(self.store,self.actor,self.products[1:],'https://products.example')
  with self.assertRaises(AccessDenied):read_detail(self.store,self.actor,{'productId':'p1'})
