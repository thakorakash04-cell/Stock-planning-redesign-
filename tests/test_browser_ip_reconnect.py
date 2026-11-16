"""Actual request-context fingerprint + SQL token restore across new connections."""
import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import streamlit as st
import daily_sessions as daily
from stock_accounts.store import Store
class ReconnectTests(unittest.TestCase):
 def fingerprint(self,ip,agent='Test browser'):
  with patch('streamlit.runtime.scriptrunner.get_script_run_ctx',return_value=object()),patch.object(st,'context',SimpleNamespace(ip_address=ip,headers={'User-Agent':agent})):
   return daily.request_client(),daily.request_client(legacy=True)
 def test_new_connection_ip_restores_same_browser_and_revocation_still_wins(self):
  with tempfile.TemporaryDirectory() as folder:
   url='sqlite:///'+str(Path(folder)/'db');store=Store(url);store.bootstrap_admin('admin_user','Test-admin-password-123!');actor=store.login('admin_user','Test-admin-password-123!')
   first,old=self.fingerprint('10.0.0.1');next_client,next_old=self.fingerprint('10.0.0.2');self.assertEqual(first,next_client);self.assertNotEqual(old,next_old)
   actor,token,_=daily.issue(store,actor,first);fresh=Store(url);state={}
   with patch('daily_sessions.request_client',side_effect=lambda legacy=False:next_old if legacy else next_client):daily.restore_cookie(fresh,state,{daily.cookie_name(fresh):token})
   self.assertEqual(state['actor'].session_id,actor.session_id)
   other,_=self.fingerprint('10.0.0.2','Different browser');self.assertIsNone(daily.restore(fresh,token,other));self.assertIsNone(daily.restore(fresh,'x'*43,next_client))
   daily.clear(fresh,state);self.assertIsNone(daily.restore(Store(url),token,next_client))
 def test_diagnostic_contains_only_safe_status_and_no_credential(self):
  with tempfile.TemporaryDirectory() as folder:
   store=Store('sqlite:///'+str(Path(folder)/'db'));store.bootstrap_admin('admin_user','Test-admin-password-123!');actor=store.login('admin_user','Test-admin-password-123!');client,_=self.fingerprint('10.0.0.1');actor,token,_=daily.issue(store,actor,client)
   diagnostic={};self.assertIsNotNone(daily.restore(store,token,client,diagnostic=diagnostic));self.assertEqual(diagnostic,{'validation':'restored'});self.assertNotIn(token,str(diagnostic));self.assertNotIn(actor.username,str(diagnostic))
   self.assertIsNone(daily.restore(store,'x'*43,client,diagnostic=diagnostic));self.assertEqual(diagnostic,{'validation':'token_not_matched'})
 def test_existing_same_connection_token_migrates_without_password(self):
  with tempfile.TemporaryDirectory() as folder:
   store=Store('sqlite:///'+str(Path(folder)/'db'));store.bootstrap_admin('admin_user','Test-admin-password-123!');actor=store.login('admin_user','Test-admin-password-123!');new,legacy=self.fingerprint('10.0.0.1')
   actor,token,_=daily.issue(store,actor,legacy)
   self.assertIsNone(daily.restore(store,token,new))
   self.assertEqual(daily.restore(store,token,new,legacy).session_id,actor.session_id)
   changed,_=self.fingerprint('10.0.0.2');self.assertEqual(daily.restore(Store(store.url),token,changed).session_id,actor.session_id)
   self.assertIsNone(daily.restore(store,token,legacy))
if __name__=='__main__':unittest.main()
