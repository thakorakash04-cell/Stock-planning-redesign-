import unittest
from unittest.mock import patch
import daily_sessions as daily
MODULE='stock_accounts.store'

class BrowserContinuityTests(unittest.TestCase):
 def test_background_gate_and_five_minute_boundary(self):
  state={'actor':object(),'_browser_visible':True,'_browser_last_activity':1000}
  self.assertTrue(daily.background_active(state,1299))
  self.assertFalse(daily.background_active(state,1300))
  state['_browser_visible']=False
  self.assertFalse(daily.background_active(state,1001))
  state['_browser_visible']=True;state['actor']=None
  self.assertFalse(daily.background_active(state,1001))
 def test_token_fingerprint_binds_ip_and_browser_without_storing_them(self):
  self.assertNotEqual(daily.digest('opaque-token','same-ip-browser'),daily.digest('opaque-token','different-ip-browser'))
  self.assertEqual(daily.digest('opaque-token','same-ip-browser'),daily.digest('opaque-token','same-ip-browser'))
 def test_cookie_probe_does_not_disable_browser_fallback(self):
  state={}
  with patch('daily_sessions.request_client',return_value='fingerprint'):
   daily.restore_cookie(object(),state,{})
  self.assertTrue(state['_daily_restore_checked'])
  self.assertFalse(state.get('_daily_browser_checked',False))
  self.assertEqual(state['_daily_client'],'fingerprint')

 def test_database_restore_requires_same_client(self):
  import importlib,tempfile
  from pathlib import Path
  module=importlib.import_module(MODULE)
  with tempfile.TemporaryDirectory() as folder:
   url='sqlite:///'+str(Path(folder)/'binding.db')
   if MODULE=='backend':
    store=module.WorkspaceStore(url,'admin@example.com','Initial-admin-password!123')
    actor=store.login('admin@example.com','Initial-admin-password!123')
   else:
    store=module.Store(url);store.bootstrap_admin('admin_user','Initial-admin-password!123')
    actor=store.login('admin_user','Initial-admin-password!123')
   issued,token,expiry=daily.issue(store,actor,'same-browser-ip')
   self.assertIsNotNone(daily.restore(store,token,'same-browser-ip'))
   self.assertIsNone(daily.restore(store,token,'changed-ip'))
   self.assertIsNone(daily.restore(store,token))
   daily.revoke(store,issued)
   self.assertIsNone(daily.restore(store,token,'same-browser-ip'))
