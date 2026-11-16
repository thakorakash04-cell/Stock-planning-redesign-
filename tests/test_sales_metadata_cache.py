import ast,copy,hashlib,json,sqlite3,unittest
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import Mock

class Store:
 def __init__(self):
  self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
  self.db.execute('CREATE TABLE datasets(id TEXT,version TEXT)');self.db.execute("INSERT INTO datasets VALUES('current','master-v1')")
  self.db.execute('CREATE TABLE stock_sales_documents(kind TEXT,filename TEXT,version TEXT,updated_at REAL,updated_by TEXT,metadata TEXT)')
  self.db.execute("INSERT INTO stock_sales_documents VALUES('primary','sales.xlsx','sales-v1',1,'a','{}')")
 @contextmanager
 def transaction(self):yield self.db
 def require(self,*args):pass
 def run(self,db,sql,args=()):return db.execute(sql,args)

class SalesMetadataTests(unittest.TestCase):
 def setUp(self):
  self.store=Store();self.addCleanup(self.store.db.close)
  self.identity={'role':'viewer','permissions':{'sales':True},'allowedSegments':['A']}
  self.authorize=Mock(side_effect=lambda *a:copy.deepcopy(self.identity));self.bom=Mock(side_effect=AssertionError('Must not read the BOM payload'))
  source=ast.parse((Path(__file__).resolve().parents[1]/'stock_accounts/sales.py').read_text())
  nodes=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='read' or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REVISION' for t in n.targets)]
  self.ns={'authorize':self.authorize,'schema':lambda *a:None,'kind':lambda k:k,'segment':lambda s:s,'hashlib':hashlib,'json':json,'bom_source_index':self.bom}
  exec(compile(ast.Module(body=nodes,type_ignores=[]),'sales.py','exec'),self.ns)
  self.version=hashlib.sha256(json.dumps([self.ns['REVISION'],'primary','sales-v1',['A'],False,'master-v1']).encode()).hexdigest()
 def call(self):return self.ns['read'](self.store,object(),{'kind':'primary','knownVersion':self.version})
 def test_unchanged_sales_does_not_read_master_or_sales_payload(self):
  queries=[];self.store.db.set_trace_callback(queries.append)
  result=self.call();self.assertTrue(result['notModified']);self.assertNotIn('rows',result);self.bom.assert_not_called()
  self.assertFalse(any('payload' in q.lower() or 'select *' in q.lower() for q in queries))
 def test_changed_bom_uses_existing_full_source_path(self):
  self.store.db.execute("UPDATE datasets SET version='master-v2'")
  with self.assertRaisesRegex(AssertionError,'BOM payload'):self.call()
 def test_access_change_during_validation_rejects_restore(self):
  changed={**self.identity,'allowedSegments':['B']};self.authorize.side_effect=[self.identity,changed]
  with self.assertRaisesRegex(ValueError,'access changed'):self.call()
