import tempfile,unittest,os
from pathlib import Path
from importlib import import_module
pkg=os.environ.get('PORTAL_PACKAGE','stock_accounts')
Store=import_module(pkg+'.store').Store
AccessDenied=import_module(pkg+'.store').AccessDenied
class PortalTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store('sqlite:///'+self.tmp.name+'/test.db');self.store.bootstrap_admin('admin','Administrator123!');self.admin=self.store.login('admin','Administrator123!');self.store.create_viewer(self.admin,'viewer','ViewerPassword123!');self.viewer=self.store.login('viewer','ViewerPassword123!')
 def tearDown(self):self.tmp.cleanup()
 def test_login_branding_public_fields_validation_and_permissions(self):
  import base64,io
  from PIL import Image
  image=io.BytesIO();Image.new('RGB',(32,32),'teal').save(image,format='PNG')
  logo='data:image/png;base64,'+base64.b64encode(image.getvalue()).decode()
  settings={'portal_logo':logo,'login_text':'First purpose line.\nSecond purpose line.','signin_heading':'Secure sign in','signin_text':'Use your username or email.'}
  self.store.portal_save(self.admin,settings)
  self.assertEqual(Store(self.store.url).portal_read(public=True),settings)
  with self.assertRaises(AccessDenied):self.store.portal_save(self.viewer,{'portal_logo':''})
  for invalid in ['https://example.com/logo.png','data:image/svg+xml;base64,PHN2Zz4=', 'data:image/png;base64,invalid']:
   with self.assertRaises(ValueError):self.store.portal_save(self.admin,{'portal_logo':invalid})
  self.assertEqual(self.store.portal_read(public=True)['portal_logo'],logo)
  with self.assertRaises(ValueError):self.store.portal_save(self.admin,{'login_text':'x'*1501})
  self.store.portal_save(self.admin,{'portal_logo':''});self.assertEqual(self.store.portal_read(public=True)['portal_logo'],'')

 def test_existing_accounts_and_alias(self):
  self.store.profile_email(self.admin,'viewer','Viewer@Example.com');self.assertEqual(self.store.login('VIEWER@example.com','ViewerPassword123!').username,'viewer');self.assertTrue(self.store.login('viewer','ViewerPassword123!'));self.assertIsNone(self.store.login('viewer@example.com','wrong'))
  self.assertTrue(Store(self.store.url).login('viewer@example.com','ViewerPassword123!'))
 def test_admin_only_and_private_rules(self):
  with self.assertRaises(AccessDenied):self.store.profile_email(self.viewer,'viewer','a@example.com')
  with self.assertRaises(AccessDenied):self.store.portal_save(self.viewer,{'title':'hacked'})
  self.store.portal_save(self.admin,{'email_rules':[{'recipient':'private@example.com'}]});self.assertNotIn('email_rules',self.store.portal_read(self.viewer));self.assertNotIn('email_rules',self.store.portal_read(public=True))
 def test_reset_single_use_revoke(self):
  self.store.profile_email(self.admin,'viewer','viewer@example.com');sent=[];username,token=self.store.request_recovery('viewer@example.com',lambda email,code:sent.append((email,code)))
  self.store.complete_recovery(username,token,sent[0][1],'ReplacementPassword123!')
  with self.assertRaises(AccessDenied):self.store.identity(self.viewer)
  self.assertTrue(self.store.login('viewer@example.com','ReplacementPassword123!'))
  with self.assertRaises(ValueError):self.store.complete_recovery(username,token,sent[0][1],'AnotherPassword123!')
 def test_guess_limit_and_enumeration(self):
  self.store.profile_email(self.admin,'viewer','viewer@example.com');sent=[];u,t=self.store.request_recovery('viewer',lambda e,c:sent.append(c))
  for _ in range(5):
   with self.assertRaises(ValueError):self.store.complete_recovery(u,t,'bad','ReplacementPassword123!')
  with self.assertRaises(ValueError):self.store.complete_recovery(u,t,sent[0],'ReplacementPassword123!')
  calls=[];self.store.request_recovery('unknown',lambda *args:calls.append(args));self.assertEqual(calls,[])
 def test_duplicate_email(self):
  self.store.profile_email(self.admin,'admin','a@example.com')
  with self.assertRaises(ValueError):self.store.profile_email(self.admin,'viewer','a@example.com')
 def test_grouping_and_dedup(self):
  alerts=import_module(pkg+'.portal_alerts');rules=[{'enabled':True,'recipient':'a@example.com','section':'Summary','column':'Qty','operator':'>','value':'2','message':'Low'} for _ in range(5)]
  self.store.portal_save(self.admin,{'email_rules':rules});self.store.save_dataset(self.admin,'sample',{'sheets':[{'name':'Summary','headers':['Qty'],'rows':[[3],[1]]}]})
  result=alerts.preview(self.store,self.admin);self.assertEqual(len(result),1);self.assertEqual(result['a@example.com'].count('Low'),5)
  calls=[];self.assertEqual(alerts.dispatch(self.store,self.admin,lambda *args:calls.append(args)),1);self.assertEqual(alerts.dispatch(self.store,self.admin,lambda *args:calls.append(args)),0);self.assertEqual(len(calls),1)
 def test_compare_and_history(self):
  compare=import_module(pkg+'.comparison').compare;old={'sheets':[{'name':'S','headers':['A'],'rows':[[1],[2]]}]};new={'sheets':[{'name':'S','headers':['A'],'rows':[[2],[3]]}]};report=compare(old,new);self.assertEqual(report[0]['Added or changed rows'],1);self.assertEqual(report[0]['Removed or replaced rows'],1)
  self.store.portal_save(self.admin,{'title':'New'});self.assertEqual(self.store.portal_history(self.admin)[0]['section'],'title')
  with self.assertRaises(AccessDenied):self.store.portal_history(self.viewer)
if __name__=='__main__':unittest.main()
