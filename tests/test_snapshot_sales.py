import base64,gzip,json,tempfile,unittest
from unittest.mock import patch
from stock_accounts.store import Store,AccessDenied
from stock_accounts.snapshot_sales import snapshot_sales

class SnapshotSalesTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store('sqlite:///'+self.tmp.name+'/source.sqlite');self.store.bootstrap_admin('admin','TestAccountPassword123!');self.actor=self.store.login('admin','TestAccountPassword123!')
  self.data={'tables':[{'name':'BOM','headers':['Material','Component'],'rows':[['001','RM']]}]}
 def tearDown(self):self.tmp.cleanup()
 def upload(self,version,value):
  with self.store.transaction() as db:
   self.store.run(db,'CREATE TABLE IF NOT EXISTS stock_sales_documents(kind TEXT PRIMARY KEY,filename TEXT,version TEXT,updated_at REAL,payload TEXT)')
   raw=base64.b64encode(gzip.compress(json.dumps({'headers':['Material Code','Value'],'rows':[['001',value],['RM',99],['1',999]]}).encode())).decode()
   for kind in ('primary','secondary'):self.store.run(db,'INSERT INTO stock_sales_documents VALUES(?,?,?,?,?) ON CONFLICT(kind) DO UPDATE SET version=excluded.version,payload=excluded.payload',(kind,'Sales.xlsx',version,1,raw))
 def test_warm_source_cache_checks_version_and_refreshes_only_changed_payload(self):
  self.upload('v1',5)
  with patch.object(self.store,'run',wraps=self.store.run) as run:
   first=snapshot_sales(self.store,self.actor,self.data,{'001','RM'})
   self.assertEqual(first[0][0]['rows'],[['001',5]])
   self.assertEqual(first[0][1]['rows'],[['001',5],['RM',99]])
   count=lambda:sum('SELECT payload FROM stock_sales_documents' in c.args[1] for c in run.call_args_list)
   self.assertEqual(count(),2);snapshot_sales(self.store,self.actor,self.data,{'001'});self.assertEqual(count(),2)
   self.upload('v2',8);fresh=snapshot_sales(self.store,self.actor,self.data,{'001'});self.assertEqual(count(),4);self.assertEqual(fresh[0][0]['rows'],[['001',8]])
 def test_missing_uploads_and_live_admin_authorization(self):
  self.assertEqual(snapshot_sales(self.store,self.actor,self.data,{'001'}),([],{}))
  self.upload('v1',5);snapshot_sales(self.store,self.actor,self.data,{'001'})
  with self.store.transaction() as db:self.store.run(db,"UPDATE accounts SET active=0 WHERE username='admin'")
  with self.assertRaises(AccessDenied):snapshot_sales(self.store,self.actor,self.data,{'001'})
