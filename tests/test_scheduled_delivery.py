import importlib,os,tempfile,unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
PKG=os.environ.get('PORTAL_PACKAGE','stock_accounts')
from importlib import import_module
Store=import_module(PKG+'.store').Store
Denied=import_module(PKG+'.store').AccessDenied
mail=import_module(PKG+'.scheduled_delivery')
transport=import_module(PKG+'.mail_transport')
CONFIG={'RESET_FROM_EMAIL':'sender@example.invalid','RESEND_API_KEY':'test-only'}
IST=ZoneInfo('Asia/Kolkata')
def at(day,hour=8,minute=0):return datetime(2026,10,day,hour,minute,tzinfo=IST).timestamp()
class SchedulerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store('sqlite:///'+self.tmp.name+'/db.sqlite');self.store.bootstrap_admin('admin','Administrator123!');self.actor=self.store.login('admin','Administrator123!');self.sent=[]
  rules=[{'enabled':True,'recipient':'reader@example.invalid','section':'Summary','column':'Qty','operator':'>','value':'2','message':'Trigger '+str(i)} for i in range(5)]
  self.store.portal_save(self.actor,{'email_rules':rules})
  self.store.save_dataset(self.actor,'sample.xlsx',{'sheets':[{'name':'Summary','headers':['Qty'],'rows':[[3],[1]]}]})
 def tearDown(self):self.tmp.cleanup()
 def send(self,*args):self.sent.append(args)
 def test_master_cache_reads_payload_once_and_invalidates_on_upload(self):
  self.store.get_dataset(self.actor)
  with patch.object(self.store,'run',wraps=self.store.run) as queries:
   first=self.store.get_dataset(self.actor);first['data']['sheets'].clear()
   self.assertTrue(self.store.get_dataset(self.actor)['data']['sheets'])
   self.assertFalse(any('SELECT * FROM ' in c.args[1] and 'datasets' in c.args[1] for c in queries.call_args_list))
  self.store.save_dataset(self.actor,'replacement.xlsx',{'sheets':[{'name':'Changed','headers':['Qty'],'rows':[[99]]}]})
  self.assertEqual(self.store.get_dataset(self.actor)['data']['sheets'][0]['name'],'Changed')
 def test_catchup_before_today_time_groups_five_rules_and_restart_dedup(self):
  result=mail.tick(self.store,CONFIG,self.send,at(18));self.assertEqual(result['sent'],1);self.assertIn('2026-10-17T09:00',result['slot']);self.assertEqual(len(self.sent),1)
  for i in range(5):self.assertIn('Trigger '+str(i),self.sent[0][2])
  restarted=Store(self.store.url);mail.tick(restarted,CONFIG,self.send,at(18,8,2));self.assertEqual(len(self.sent),1)
 def test_multiple_missed_days_consolidated_and_new_daily_slot_sends(self):
  mail.tick(self.store,CONFIG,self.send,at(18));mail.tick(self.store,CONFIG,self.send,at(21));self.assertEqual(len(self.sent),2);self.assertIn('2026-10-20T09:00',self.sent[-1][2])
  mail.tick(self.store,CONFIG,self.send,at(21,9));self.assertEqual(len(self.sent),3)
 def test_unconfigured_does_not_consume_due_report(self):
  self.assertEqual(mail.tick(self.store,{},self.send,at(18))['state'],'not_configured');self.assertEqual(self.sent,[])
  mail.tick(self.store,CONFIG,self.send,at(18,9));self.assertEqual(len(self.sent),1)
 def test_paused_schedule_and_invalid_time(self):
  self.store.portal_save(self.actor,{'email_schedule':{'enabled':False,'time':'09:00'}});self.assertEqual(mail.tick(self.store,CONFIG,self.send,at(18))['state'],'paused')
  self.store.portal_save(self.actor,{'email_schedule':{'enabled':True,'time':'09:00'}});mail.tick(self.store,CONFIG,self.send,at(21));self.assertEqual(len(self.sent),1)
  with self.assertRaises(ValueError):self.store.portal_save(self.actor,{'email_schedule':{'enabled':True,'time':'25:00'}})
 def test_parallel_sessions_claim_once(self):
  def check(_):return mail.tick(Store(self.store.url),CONFIG,self.send,at(18))
  with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(check,range(4)))
  self.assertEqual(len(self.sent),1)
 def test_definitely_unsent_retries_while_active(self):
  def offline(*args):raise mail.DeliveryDeferred()
  mail.tick(self.store,CONFIG,offline,at(18));self.assertEqual(mail.status(self.store,self.actor)['jobs'][0]['status'],'retry')
  mail.tick(self.store,CONFIG,self.send,at(18,8,2));self.assertEqual(len(self.sent),1);self.assertEqual(mail.status(self.store,self.actor)['jobs'][0]['status'],'sent')
 def test_uncertain_smtp_never_blindly_retried(self):
  def uncertain(*args):self.sent.append(args);raise mail.DeliveryUncertain()
  mail.tick(self.store,CONFIG,uncertain,at(18));mail.tick(Store(self.store.url),CONFIG,self.send,at(18,8,2));self.assertEqual(len(self.sent),1);self.assertEqual(mail.status(self.store,self.actor)['jobs'][0]['status'],'uncertain')
 def test_crashed_sending_claim_expires_without_resend(self):
  mail.tick(self.store,CONFIG,self.send,at(18));state,jobs=mail.tables(self.store)
  with self.store.transaction() as db:self.store.run(db,f"UPDATE {jobs} SET status='sending',lease_until=?",(at(18)+30,))
  mail.tick(Store(self.store.url),CONFIG,self.send,at(18,8,6));self.assertEqual(len(self.sent),1);self.assertEqual(mail.status(self.store,self.actor)['jobs'][0]['status'],'uncertain')
 def test_no_administrator_does_not_deliver(self):
  with self.store.transaction() as db:self.store.run(db,f"UPDATE {self.store.account_table} SET active=0 WHERE role='admin'")
  self.assertEqual(mail.tick(self.store,CONFIG,self.send,at(18))['state'],'no_administrator');self.assertEqual(self.sent,[])
 def test_schedule_settings_and_logs_require_admin(self):
  self.store.create_viewer(self.actor,'viewer','ViewerPassword123!');viewer=self.store.login('viewer','ViewerPassword123!')
  with self.assertRaises(Denied):self.store.portal_save(viewer,{'email_schedule':{'enabled':False,'time':'10:00'}})
  with self.assertRaises(Denied):mail.status(self.store,viewer)
  self.assertNotIn('email_schedule',self.store.portal_read(viewer))
 def test_invalid_rule_does_not_advance_slot(self):
  rules=self.store.portal_read(self.actor)['email_rules'];rules[0]['column']='Unknown';self.store.portal_save(self.actor,{'email_rules':rules});self.assertEqual(mail.tick(self.store,CONFIG,self.send,at(18))['state'],'invalid_rules');self.assertEqual(self.sent,[])
  rules[0]['column']='Qty';self.store.portal_save(self.actor,{'email_rules':rules});mail.tick(self.store,CONFIG,self.send,at(18,8,2));self.assertEqual(len(self.sent),1)
 def test_saved_data_changes_cancel_unsent_snapshot_and_rebuild(self):
  def offline(*args):raise mail.DeliveryDeferred()
  mail.tick(self.store,CONFIG,offline,at(18))
  self.store.save_dataset(self.actor,'updated.xlsx',{'sheets':[{'name':'Summary','headers':['Qty'],'rows':[[4]]}]})
  mail.tick(self.store,CONFIG,self.send,at(18,8,2));self.assertEqual(self.sent,[])
  mail.tick(self.store,CONFIG,self.send,at(18,8,4));self.assertEqual(len(self.sent),1);self.assertIn('updated.xlsx',self.sent[0][2]);self.assertIn('Qty: 4',self.sent[0][2])
class TransportTests(unittest.TestCase):
 def test_resend_idempotency_header_and_retry_classification(self):
  with patch.object(transport,'urlopen',side_effect=TimeoutError()) as request:
   with self.assertRaises(mail.DeliveryDeferred):transport.send(CONFIG,'r@example.invalid','subject','body','job-id')
   self.assertEqual(request.call_args.args[0].get_header('Idempotency-key'),'portal-scheduled-job-id')
 def test_smtp_connect_failure_is_safe_to_retry(self):
  cfg={'RESET_FROM_EMAIL':'s@example.invalid','SMTP_HOST':'example.invalid','SMTP_USER':'s','SMTP_PASSWORD':'test'}
  with patch.object(transport.smtplib,'SMTP',side_effect=ConnectionError()):
   with self.assertRaises(mail.DeliveryDeferred):transport.send(cfg,'r@example.invalid','subject','body','id')
 def test_smtp_after_submission_failure_is_uncertain(self):
  cfg={'RESET_FROM_EMAIL':'s@example.invalid','SMTP_HOST':'example.invalid','SMTP_USER':'s','SMTP_PASSWORD':'test'}
  with patch.object(transport.smtplib,'SMTP') as factory:
   factory.return_value.__enter__.return_value.send_message.side_effect=TimeoutError()
   with self.assertRaises(mail.DeliveryUncertain):transport.send(cfg,'r@example.invalid','subject','body','id')
if __name__=='__main__':unittest.main()
