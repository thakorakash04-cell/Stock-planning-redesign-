"""Storage regressions runnable with the Python standard library alone."""
import importlib.util,sqlite3,tempfile,unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
spec=importlib.util.spec_from_file_location('column_cache_under_test',Path(__file__).resolve().parents[1]/'stock_accounts/column_result_cache.py')
cache=importlib.util.module_from_spec(spec);spec.loader.exec_module(cache)

class Storage:
 def __init__(self,path):self.path=path
 @contextmanager
 def transaction(self):
  db=sqlite3.connect(self.path);db.row_factory=sqlite3.Row
  try:yield db;db.commit()
  except Exception:db.rollback();raise
  finally:db.close()
 def require(self,db,actor):
  if not actor.allowed:raise PermissionError('No active access')
 def run(self,db,sql,args=()):return db.execute(sql,args)

class ColumnCacheStorageTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.store=Storage(str(Path(self.temp.name)/'cache.db'));self.actor=SimpleNamespace(username='alice',allowed=True)
  self.base={'headers':['Material','Qty'],'rows':[['001',2],['002',0],['003',4]]};self.definitions=[{'name':'Amount','plan':{'sources':[]}}]
  self.value={'columns':[{'name':'Amount','values':[20,0,None]}],'warnings':['Missing match']};self.key=cache.fingerprint(self.base,self.definitions,'workbook-one','viewer')
 def tearDown(self):self.temp.cleanup()
 def write(self,scope='main:Stock',key=None):return cache.write(self.store,self.actor,scope,key or self.key,self.value)
 def read(self,scope='main:Stock',key=None,actor=None,store=None):return cache.read(store or self.store,actor or self.actor,scope,key or self.key,self.definitions,3)
 def test_fresh_connection_and_old_timestamp_restore_exact_values(self):
  self.assertTrue(self.write())
  with self.store.transaction() as db:self.store.run(db,'UPDATE user_column_results SET updated_at=0')
  restored=self.read(store=Storage(self.store.path))
  self.assertEqual(restored,self.value)
 def test_user_scope_revision_and_row_order_never_cross_reuse(self):
  self.write();self.assertIsNone(self.read(actor=SimpleNamespace(username='bob',allowed=True)));self.assertIsNone(self.read(scope='main:Other'))
  for revision,role,base,defs in [('workbook-two','viewer',self.base,self.definitions),('workbook-one','admin',self.base,self.definitions),('workbook-one','viewer',{**self.base,'rows':list(reversed(self.base['rows']))},self.definitions),('workbook-one','viewer',self.base,[{'name':'Changed'}])]:
   self.assertIsNone(self.read(key=cache.fingerprint(base,defs,revision,role)))
  with self.assertRaises(PermissionError):self.read(actor=SimpleNamespace(username='alice',allowed=False))
 def test_corrupt_cache_falls_back_and_payload_has_bounds(self):
  self.write()
  with self.store.transaction() as db:self.store.run(db,'UPDATE user_column_results SET payload=?',('corrupt',))
  self.assertIsNone(self.read())
  old=cache.MAX_RAW
  try:
   cache.MAX_RAW=1;self.assertFalse(self.write())
  finally:cache.MAX_RAW=old
 def test_entry_count_is_bounded_and_newest_result_is_retained(self):
  for index in range(35):self.write(scope='table:'+str(index))
  with self.store.transaction() as db:self.assertEqual(self.store.run(db,'SELECT count(*) FROM user_column_results').fetchone()[0],32)
  self.assertEqual(self.read(scope='table:34'),self.value)

class ColumnCacheHandlerTests(unittest.TestCase):
 def test_real_login_and_handler_skip_source_loading_and_calculating(self):
  import sys,json,base64,gzip,hashlib
  from unittest.mock import patch,Mock
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
  from stock_accounts.store import Store,AccessDenied
  from stock_accounts import column_result_cache as real_cache
  with tempfile.TemporaryDirectory() as folder:
   url='sqlite:///'+str(Path(folder)/'account.db');store=Store(url)
   store.bootstrap_admin('admin_user','Test-admin-password!123');admin=store.login('admin_user','Test-admin-password!123')
   store.create_viewer(admin,'viewer_user','Test-viewer-password!123');actor=store.login('viewer_user','Test-viewer-password!123')
   dataset={'sheets':[],'tables':[]};payload=base64.b64encode(gzip.compress(json.dumps(dataset).encode())).decode()
   with store.transaction() as db:store.run(db,'INSERT INTO datasets(id,payload,filename,version,uploaded_by,updated_at) VALUES(?,?,?,?,?,?)',('current',payload,'book.xlsx','v1',admin.username,0))
   module_spec=importlib.util.spec_from_file_location('stock_accounts._column_cache_handler_test',Path(__file__).resolve().parents[1]/'stock_accounts/table_columns.py')
   handler=importlib.util.module_from_spec(module_spec)
   # Provider functions are test doubles; real SQLite accounts, login, access
   # checks, handler and durable result cache execute unchanged.
   provider=SimpleNamespace(generate=Mock(side_effect=AssertionError('Gemini called')),settings=Mock(side_effect=AssertionError('Gemini settings loaded')))
   with patch.dict(sys.modules,{'grounded_ai':provider}):module_spec.loader.exec_module(handler)
   def revision(s,a,version):return hashlib.sha256(json.dumps([version,s.identity(a)],sort_keys=True).encode()).hexdigest()
   base={'headers':['Material','Qty'],'rows':[['A',2],['B',0]]};defs=[{'name':'Amount','plan':{'sources':[]}}];values={'columns':[{'name':'Amount','values':[20,0]}],'warnings':[]}
   current=store.get_dataset(actor)
   cache_revision=json.dumps([revision(store,actor,'v1'),current['updated_at'],current['filename']],separators=(',',':'))
   key=real_cache.fingerprint(base,defs,cache_revision,'viewer');real_cache.write(store,actor,'main:Stock',key,values)
   fresh=Store(url);logged_in=fresh.login('viewer_user','Test-viewer-password!123')
   event={'action':'table_columns_resolve','scope':'main:Stock',**base,'definitions':defs,'version':'v1'}
   with patch.object(handler,'revision',side_effect=revision),patch.object(handler,'source_tables',side_effect=AssertionError('Source tables loaded')),patch.object(handler,'resolve',side_effect=AssertionError('Calculator ran')):
    result=handler.handle(fresh,logged_in,event)
    self.assertTrue(result['cached']);self.assertEqual(result['columns'],values['columns'])
    with fresh.transaction() as db:fresh.run(db,'UPDATE datasets SET updated_at=1')
    new_values=[{'name':'Amount','values':[30,0]}]
    with patch.object(handler,'source_tables',return_value=([],'v1')) as sources,patch.object(handler,'resolve',return_value=({},new_values,[])) as calculator:
     updated=handler.handle(fresh,logged_in,event)
     self.assertEqual(updated['columns'],new_values);self.assertTrue(updated['cache_stored'])
     cached_again=handler.handle(fresh,logged_in,event)
     self.assertTrue(cached_again['cached']);self.assertEqual(cached_again['columns'],new_values)
     self.assertEqual(sources.call_count,1);self.assertEqual(calculator.call_count,1)
    fresh.update_permissions(admin,'viewer_user',{'use_tools':False})
    with self.assertRaises(AccessDenied):handler.handle(fresh,logged_in,event)
   provider.generate.assert_not_called();provider.settings.assert_not_called()

if __name__=='__main__':unittest.main()
