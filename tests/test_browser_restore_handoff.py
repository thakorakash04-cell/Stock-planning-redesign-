import unittest
from types import SimpleNamespace
from unittest.mock import patch
import streamlit as st
import streamlit.components.v2 as v2
import daily_sessions as daily

class Rerun(Exception):pass
class Stop(Exception):pass

class HandoffTests(unittest.TestCase):
 def mount(self,state,result,button=False):
  with patch.object(st,'session_state',state),patch.object(st,'fragment',lambda fn:fn),patch.object(v2,'component',return_value=lambda **kwargs:result),patch.object(st,'rerun',side_effect=Rerun),patch.object(st,'stop',side_effect=Stop),patch.object(st,'caption'),patch.object(st,'warning'),patch.object(st,'button',return_value=button):daily.mount(object())
 def test_duplicate_browser_messages_restore_only_once(self):
  state={'_daily_browser_instance':'instance'};result=SimpleNamespace(session={'instance':'instance','browser':{'instance':'instance','token':'t'*43,'tokens':['t'*43],'at':1,'visible':True}})
  with patch.object(daily,'restore_candidates',return_value=object()) as restore:
   with self.assertRaises(Rerun):self.mount(state,result)
   self.mount(state,result)
  self.assertEqual(restore.call_count,1);self.assertTrue(state['_daily_browser_checked'])
 def test_retry_reprobes_without_erasing_pending_cookie_write(self):
  action={'name':'workspace_day_stock','value':'t'*43,'expires':1,'nonce':'write'};state={'_daily_browser_instance':'old','_daily_cookie_action':action}
  with self.assertRaises(Rerun):self.mount(state,SimpleNamespace(),True)
  self.assertNotEqual(state['_daily_browser_instance'],'old');self.assertEqual(state['_daily_cookie_action']['value'],action['value']);self.assertEqual(state['_daily_cookie_action']['expires'],action['expires']);self.assertNotEqual(state['_daily_cookie_action']['nonce'],action['nonce'])
 def test_blocked_write_is_recorded_before_ack_releases_login(self):
  state={'_daily_browser_instance':'instance','_daily_browser_checked':True,'_daily_cookie_action':{'nonce':'write'}}
  with self.assertRaises(Rerun):self.mount(state,SimpleNamespace(session={'instance':'instance','receipt':{'nonce':'write','saved':False}}))
  self.assertTrue(state['_daily_storage_failed']);self.assertNotIn('_daily_cookie_action',state)
