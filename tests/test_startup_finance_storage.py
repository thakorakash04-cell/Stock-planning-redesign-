"""Preload failure/retry checks using real SQLite accounts and provider doubles."""
import sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stock_accounts.store import Store
from stock_accounts import preload

class FinanceStartupTests(unittest.TestCase):
 def test_failed_preload_retries_sources_without_ack_and_then_reuses_success(self):
  with tempfile.TemporaryDirectory() as folder:
   store=Store('sqlite:///'+str(Path(folder)/'db'));store.bootstrap_admin('admin_user','Test-admin-password!123');admin=store.login('admin_user','Test-admin-password!123')
   store.create_viewer(admin,'viewer_user','Test-viewer-password!123');store.update_permissions(admin,'viewer_user',{'menu_11':True});actor=store.login('viewer_user','Test-viewer-password!123')
   failed=True
   def read(s,a,event):
    if failed and event['kind']=='secondary':raise ValueError('Temporary source failure')
    return {'available':True,'headers':['Material'],'rows':[['A']]}
   def schema(s):
    with s.transaction() as db:s.run(db,'CREATE TABLE IF NOT EXISTS stock_sales_documents(kind TEXT,version TEXT)')
   sales=SimpleNamespace(read=Mock(side_effect=read),schema=schema,REVISION=7)
   state={}
   with patch.dict(sys.modules,{'stock_accounts.sales':sales}):
    first=preload.load_after_paint(store,actor,state)
    self.assertEqual(first['preload']['errors'],['Secondary Sales could not be loaded.'])
    failed=False
    second=preload.load_after_paint(store,actor,state)
    self.assertEqual(second['preload']['errors'],[]);self.assertNotEqual(first['preload']['id'],second['preload']['id']);self.assertEqual(sales.read.call_count,4)
    again=preload.load_after_paint(store,actor,state)
    self.assertEqual(again['preload']['id'],second['preload']['id']);self.assertEqual(sales.read.call_count,4)

class SourceStartupTests(unittest.TestCase):
 def test_preloaded_models_apply_source_permissions_and_access_scope(self):
  from stock_accounts.workspace_delivery import model_tables,model_scope
  from stock_accounts.access import require_menu
  with tempfile.TemporaryDirectory() as folder:
   store=Store('sqlite:///'+str(Path(folder)/'db'));store.bootstrap_admin('admin_user','Test-admin-password!123');admin=store.login('admin_user','Test-admin-password!123')
   store.create_viewer(admin,'viewer_user','Test-viewer-password!123');store.update_permissions(admin,'viewer_user',{'menu_1':False});actor=store.login('viewer_user','Test-viewer-password!123')
   with store.transaction() as db:store.run(db,'INSERT INTO datasets(id,payload,filename,version,uploaded_by,updated_at) VALUES(?,?,?,?,?,?)',('current','unused','Master.xlsx','v1',admin.username,0))
   tables=[{'name':'Stock','headers':['Material','Qty'],'rows':[['A',3]]},{'name':'Prices','headers':['Material','Std DP'],'rows':[['A',10]]}]
   def check(s,a,table,selected):require_menu(s,a,1 if 'Std DP' in table['headers'] else 0)
   checker=Mock(side_effect=check)
   event={'version':'v1','modelScope':model_scope(store.identity(actor),'v1')}
   with patch.dict(sys.modules,{'stock_accounts.workspace':SimpleNamespace(workspace_payload=lambda *args:({},tables,'v1')),'stock_accounts.planning_assistant':SimpleNamespace(require_source_table=checker)}):
    result=model_tables(store,actor,event)
    self.assertEqual([t['name'] for t in result['tables']],['Stock']);self.assertEqual(checker.call_count,2)
    store.update_permissions(admin,'viewer_user',{'menu_1':True})
    actor=store.login('viewer_user','Test-viewer-password!123')
    with self.assertRaises(ValueError):model_tables(store,actor,event)

if __name__=='__main__':unittest.main()
