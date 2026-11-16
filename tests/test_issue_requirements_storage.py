"""Issue rows use the existing allocation arithmetic and real SQLite result storage."""
import json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stock_accounts import batch_availability as batch
from stock_accounts.store import Store

def data():
 return {'tables':[
  {'name':'BOM','headers':['Material','Component','Component(text)','Base quantity','Component quantity','Component unit','Bill of material','Alternative BOM','Item Number'],'rows':[['A','RM','Raw material',10,3,'EA',1,1,10],['A','RM','Raw material',10,3,'EA',1,1,10],['A','S','Semi',10,1,'EA',1,1,20]]},
  {'name':'Stock Data','headers':['Material','Current Stock','Base Unit of Measure'],'rows':[['RM',10,'EA'],['S',20,'EA']]}]}
def item(id,qty,batch_name='BATCH',code='A',date='2026-11-01'):
 return {'id':id,'revision':1,'materialCode':code,'row':[code,'Product A',batch_name,qty,date,'2026-11-30']}
class IssueRequirementTests(unittest.TestCase):
 def test_each_plan_keeps_full_requirement_even_when_short_and_duplicate_bom_is_ignored(self):
  result=batch.calculate(data(),[item('later',20,date='2026-11-02'),item('first',20)])
  rows=[dict(zip(result['issueHeaders'],r)) for r in result['issueRows']]
  self.assertEqual(len(rows),4);self.assertEqual(result['planStatuses'],{'first':'Ready','later':'Material shortage'})
  for row in rows:
   self.assertIsNone(row['SAP Order']);self.assertEqual(row['Product Batch'],'BATCH')
   self.assertEqual(row['Required Quantity'],6 if row['Component Code']=='RM' else 2)
  self.assertEqual([r['Plan Reference'] for r in rows],['first','first','later','later'])
  for combined in result['rows']:
   self.assertAlmostEqual(sum(r['Required Quantity'] for r in rows if r['Component Code']==combined[0] and r['Unit']==combined[2]),combined[3])
 def test_fractional_quantities_and_missing_boms_keep_verification_and_no_fabricated_order(self):
  result=batch.calculate(data(),[item('fraction',0.125),item('missing',1,code='NO-BOM')]);rows=[dict(zip(result['issueHeaders'],r)) for r in result['issueRows']]
  rm=next(r for r in rows if r['Component Code']=='RM');self.assertEqual(rm['Required Quantity'],0.0375)
  missing=next(r for r in rows if r['Plan Reference']=='missing');self.assertIsNone(missing['Required Quantity']);self.assertEqual(missing['Plan Readiness'],'Cannot verify');self.assertIn('No BOM',missing['Verification'])
  self.assertEqual(batch.calculate(data(),[])['issueRows'],[])
 def test_changed_units_remain_separate_and_unverified(self):
  d=data();d['tables'][0]['rows'].append(['B','RM','Raw material',1,1,'KG',2,1,10])
  result=batch.calculate(d,[item('a',1),item('b',1,code='B')]);rows=[dict(zip(result['issueHeaders'],r)) for r in result['issueRows']]
  self.assertEqual({r['Unit'] for r in rows if r['Component Code']=='RM'},{'EA','KG'})
  self.assertTrue(all(r['Plan Readiness']=='Cannot verify' for r in rows))
 def test_third_table_survives_relogin_cache_and_revoked_access_is_denied(self):
  with tempfile.TemporaryDirectory() as folder:
   s=Store('sqlite:///'+str(Path(folder)/'db'));s.bootstrap_admin('admin_user','Test-admin-password!123');admin=s.login('admin_user','Test-admin-password!123');s.create_viewer(admin,'viewer_user','Test-viewer-password!123');actor=s.login('viewer_user','Test-viewer-password!123')
   items=[item('one',20),item('two',20,date='2026-11-02')]
   with s.transaction() as db:
    s.run(db,'CREATE TABLE production_shared(id TEXT,kind TEXT,revision INTEGER)')
    for i in items:s.run(db,'INSERT INTO production_shared VALUES(?,?,?)',(i['id'],'upcoming',1))
    s.run(db,'INSERT INTO datasets(id,payload,filename,version,uploaded_by,updated_at) VALUES(?,?,?,?,?,?)',('current','unused','Master.xlsx','v1',admin.username,1))
   current={'version':'v1','updated_at':1,'data':data(),'_scope':'all'}
   production=SimpleNamespace(read=lambda *a,**k:{'version':'v1','sourceStamp':1,'upcoming':items},schema=lambda *a:None)
   with patch.dict(sys.modules,{'stock_accounts.production':production}),patch.object(s,'get_dataset',return_value=current):
    first=batch.check(s,actor,{'version':'v1'});self.assertEqual(len(first['issueRows']),4)
   restarted=Store(s.url);again=restarted.login('viewer_user','Test-viewer-password!123')
   with patch.dict(sys.modules,{'stock_accounts.production':production}),patch.object(restarted,'get_dataset',return_value=current),patch.object(batch,'calculate',side_effect=AssertionError('Recalculated cached result')):
    self.assertEqual(batch.check(restarted,again,{'version':'v1'}),first)
   s.update_permissions(admin,'viewer_user',{'menu_3':False});revoked=s.login('viewer_user','Test-viewer-password!123')
   with self.assertRaises(PermissionError):batch.check(s,revoked,{'version':'v1'})
   with s.transaction() as db:stored=json.loads(s.run(db,'SELECT payload FROM production_batch_availability').fetchone()['payload'])
   self.assertEqual(stored['issueRows'],first['issueRows'])
if __name__=='__main__':unittest.main()
