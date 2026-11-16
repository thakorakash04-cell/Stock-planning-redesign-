import os,unittest,tempfile,importlib
from unittest.mock import patch
PKG=os.environ.get('PORTAL_PACKAGE','stock_accounts')
store_module=importlib.import_module(PKG+'.store');Store=store_module.Store
console=importlib.import_module(PKG+'.portal_console')
class ConsoleTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store('sqlite:///'+self.tmp.name+'/db.sqlite');self.store.bootstrap_admin('admin','Administrator123!');self.actor=self.store.login('admin','Administrator123!');self.store.create_viewer(self.actor,'reader','ReaderPassword123!',email='reader@example.invalid');self.viewer=self.store.login('reader','ReaderPassword123!');self.session={}
  self.data={'sheets':[{'name':'Summary','headers':['Material','Need to order','Status'],'rows':[['A',5,'Pending'],['B',0,'Complete']]}]};self.store.save_dataset(self.actor,'source.xlsx',self.data)
 def tearDown(self):self.tmp.cleanup()
 def call(self,operation,**event):return console.handle(self.store,self.actor,{'operation':operation,**event},self.session)
 def test_access_log_is_admin_only_filtered_bounded_and_omits_session_details(self):
  with self.assertRaises(store_module.AccessDenied):console.handle(self.store,self.viewer,{'operation':'accessLog'},{})
  with self.store.transaction() as db:
   for i in range(105):self.store._log(db,'reader','view','Summary','private-session',{'private':'hidden'})
  first=self.call('accessLog',username='reader');self.assertEqual(len(first['rows']),100);self.assertEqual(first['nextOffset'],100)
  self.assertTrue(all(r['username']=='reader' for r in first['rows']));self.assertNotIn('private',str(first))
  last=self.call('accessLog',username='reader',offset=100);self.assertIsNone(last['nextOffset']);self.assertGreater(len(last['rows']),0)
 def test_workbook_record_segment_labels_reuse_mapping_without_duplicating_rows(self):
  self.data['tables']=[{'name':'Unique Material','headers':['Material','Source.Name'],'rows':[['A','Care.xlsx'],['A','Surgical.xlsx'],['B','Care.xlsx']]}]
  self.data['sheets'][0]['rows'].append(['C',7,'Unknown'])
  self.store.save_dataset(self.actor,'mapped.xlsx',self.data)
  result=self.call('workbookRecords',table='Summary',page=0)
  self.assertEqual(result['rows'],self.data['sheets'][0]['rows'])
  self.assertEqual(result['segmentLabels'],['Care / Surgical','Care','Unmapped segment'])
  self.assertEqual(result['total'],3)
  with self.assertRaises(store_module.AccessDenied):console.handle(self.store,self.viewer,{'operation':'workbookRecords','table':'Summary'},self.session)
  self.data['sheets'][0]['headers'].append('Source.Name')
  self.data['sheets'][0]['rows']=[r+['Explicit.xlsx'] for r in self.data['sheets'][0]['rows']]
  self.store.save_dataset(self.actor,'explicit.xlsx',self.data)
  self.assertEqual(self.call('workbookRecords',table='Summary')['segmentLabels'],['Explicit']*3)
 def rule(self):return {'id':'test','name':'Purchase shortage','recipients':['reader@example.invalid'],'section':'Summary','column':'Need to order','operator':'>','value':0,'filters':[{'column':'Status','operator':'contains','value':'Pending'}],'enabled':True}
 def test_viewer_cannot_open_admin_or_invoke_ai(self):
  with self.assertRaises(store_module.AccessDenied):console.handle(self.store,self.viewer,{'operation':'consoleInit'},{})
  with patch('grounded_ai.generate') as model:
   with self.assertRaises(store_module.AccessDenied):console.handle(self.store,self.viewer,{'operation':'emailDraft','question':'send'},{} )
   model.assert_not_called()
 def test_ai_drafts_are_disabled_and_never_save_or_send(self):
  with patch('grounded_ai.settings',return_value=('test-key','test-model')),patch('grounded_ai.generate',return_value={'rules':[self.rule()],'answer':'One report point is ready.','replace_ids':[]}) as model:
   result=self.call('emailDraft',question='Send this person shortage materials, and only pending ones',recipients=['reader@example.invalid'],history=[{'role':'user','text':'Use the same person'}],existingRules=[])
  self.assertFalse(result['rules'][0]['enabled']);self.assertEqual(self.store.portal_read(self.actor).get('email_rules',[]),[]);self.assertNotIn('password',str(model.call_args.args[3]).lower());self.assertIn('history',model.call_args.args[3])
 def test_unknown_ai_columns_rejected(self):
  rule=self.rule();rule['column']='Invented'
  with patch('grounded_ai.settings',return_value=('test-key','test-model')),patch('grounded_ai.generate',return_value={'rules':[rule]}):
   with self.assertRaises(ValueError):self.call('emailDraft',question='Send it',recipients=['reader@example.invalid'])
 def test_preview_combines_points_without_saving_and_save_version_is_checked(self):
  rules=[{**self.rule(),'id':str(i),'name':'Point '+str(i)} for i in range(5)];info=self.call('emailInfo');preview=self.call('emailPreview',rules=rules)
  self.assertEqual(len(preview['reports']),1);self.assertEqual(len(preview['reports'][0]['points']),5);self.assertEqual(preview['reports'][0]['points'][0]['count'],1)
  self.assertEqual(self.store.portal_read(self.actor).get('email_rules',[]),[])
  saved=self.call('emailSave',rules=rules,version=info['version']);self.assertEqual(len(saved['rules']),5)
  with self.assertRaises(ValueError):self.call('emailSave',rules=rules,version=info['version'])
 def test_user_email_keeps_username_login_and_permission_change_revokes_session(self):
  self.call('memberSave',username='reader',email='new@example.invalid',permissions={'download':False,'use_tools':False,'menu_0':False},active=True)
  self.assertTrue(self.store.login('reader','ReaderPassword123!'));self.assertTrue(self.store.login('new@example.invalid','ReaderPassword123!'))
  with self.assertRaises(store_module.AccessDenied):self.store.identity(self.viewer)
 def test_workbook_preview_never_saves_and_stale_confirmation_rejected(self):
  new={'sheets':[{'name':'Summary','headers':['Material','Need to order','Status'],'rows':[['C',9,'Pending']]}]}
  with patch.object(console,'parse_upload',return_value=('new.xlsx',new)):preview=self.call('workbookPreview',content='ignored')
  self.assertEqual(self.store.get_dataset(self.actor)['filename'],'source.xlsx');self.assertEqual(preview['comparison'][0]['New rows'],1)
  self.store.save_dataset(self.actor,'concurrent.xlsx',self.data)
  # save_dataset hashes identical data; use changed data to represent a real concurrent revision.
  self.store.save_dataset(self.actor,'concurrent.xlsx',{'sheets':[]})
  with self.assertRaises(ValueError):self.call('workbookConfirm',token=preview['token'])
  self.assertEqual(self.store.get_dataset(self.actor)['filename'],'concurrent.xlsx')
 def test_registered_recipient_revocation_applies_to_reports(self):
  rules=[self.rule()];info=self.call('emailInfo');self.call('emailSave',rules=rules,version=info['version']);self.store.update_permissions(self.actor,'reader',{'menu_0':False})
  self.assertEqual(self.call('emailPreview',rules=rules)['reports'],[])

 def test_ai_questions_and_schedule_proposals_do_not_require_recipients(self):
  initial=self.call('emailInfo')
  with patch('grounded_ai.settings',return_value=('test-key','test-model')),patch('grounded_ai.generate',return_value={'rules':[],'schedule':{'enabled':True,'time':'08:30'},'answer':'Review daily delivery at 8:30 IST.'}):
   reply=self.call('emailDraft',question='Send the saved report every morning at 8:30',recipients=[],existingRules=[],workingSchedule=initial['schedule'],version=initial['version'],scheduleVersion=initial['scheduleVersion'])
  self.assertEqual(reply['schedule']['time'],'08:30');self.assertNotIn('email_schedule',self.store.portal_read(self.actor));self.assertEqual(reply['proposedRules'],[])
  with patch('grounded_ai.settings',return_value=('test-key','test-model')),patch('grounded_ai.generate',return_value={'rules':[],'answer':'Use Save rules after reviewing the proposal.'}):
   reply=self.call('emailDraft',question='How do I review and save this?',recipients=[])
  self.assertIn('Save rules',reply['answer']);self.assertIsNone(reply['schedule'])

 def test_ai_explicit_rule_changes_stay_staged_and_preserve_other_points(self):
  existing=[self.rule(),{**self.rule(),'id':'second','name':'Keep this point'}]
  with patch('grounded_ai.settings',return_value=('test-key','test-model')),patch('grounded_ai.generate',return_value={'rules':[{**self.rule(),'value':'10'}],'replace_ids':['test'],'answer':'Threshold revised.'}):
   reply=self.call('emailDraft',question='Change the first limit to ten; keep the second point',recipients=[],existingRules=existing)
  self.assertEqual(len(reply['proposedRules']),2);self.assertEqual(reply['proposedRules'][0]['id'],'second');self.assertEqual(reply['proposedRules'][1]['value'],'10');self.assertFalse(reply['proposedRules'][1]['enabled']);self.assertEqual(self.store.portal_read(self.actor).get('email_rules',[]),[])
  with patch('grounded_ai.settings',return_value=('test-key','test-model')),patch('grounded_ai.generate',return_value={'rules':[],'delete_ids':['second'],'answer':'Deletion proposed.'}):
   revised=self.call('emailDraft',question='Now remove the second point',recipients=[],existingRules=reply['proposedRules'])
  self.assertEqual(len(revised['proposedRules']),1)

 def test_reviewed_rule_and_schedule_save_is_atomic_and_keeps_sessions(self):
  info=self.call('emailInfo');self.call('emailApplyProposal',rules=[self.rule()],version=info['version'],schedule={'enabled':True,'time':'08:30'},scheduleVersion=info['scheduleVersion'])
  saved=self.call('emailInfo');self.assertEqual(saved['schedule']['time'],'08:30');self.assertEqual(len(saved['rules']),1);self.assertEqual(self.store.identity(self.viewer)['username'],'reader')
  self.store.portal_save(self.actor,{'email_schedule':{'enabled':True,'time':'10:00'}})
  with self.assertRaises(ValueError):self.call('emailApplyProposal',rules=[],version=saved['version'],schedule={'enabled':False,'time':'09:00'},scheduleVersion=saved['scheduleVersion'])
  current=self.call('emailInfo');self.assertEqual(current['schedule']['time'],'10:00');self.assertEqual(len(current['rules']),1)

 def test_ai_rejects_invalid_schedule_and_stale_context(self):
  with patch('grounded_ai.settings',return_value=('test-key','test-model')),patch('grounded_ai.generate',return_value={'rules':[],'schedule':{'enabled':True,'time':'25:00'}}):
   with self.assertRaises(ValueError):self.call('emailDraft',question='Make it 25 oclock',recipients=[])
  with self.assertRaises(ValueError):self.call('emailDraft',question='Set my report',recipients=[],version='old')

if __name__=='__main__':unittest.main()


