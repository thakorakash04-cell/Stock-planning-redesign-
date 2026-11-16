import unittest
from unittest.mock import patch
import daily_sessions as daily

class RecoveryTests(unittest.TestCase):
 def test_transient_cookie_failure_keeps_restore_retryable(self):
  state={};store=object();cookies={daily.cookie_name(store):'t'*43}
  with patch.object(daily,'request_client',return_value='browser-ip'),patch.object(daily,'restore',side_effect=TimeoutError('database unavailable')):
   with self.assertRaises(TimeoutError):daily.restore_cookie(store,state,cookies)
  self.assertFalse(state.get('_daily_restore_checked',False))
  self.assertNotIn('_daily_cookie_action',state)
  with patch.object(daily,'request_client',return_value='browser-ip'),patch.object(daily,'restore',return_value={'email':'test'}) as restore:
   daily.restore_cookie(store,state,cookies)
  self.assertEqual(restore.call_count,1)
  self.assertEqual(restore.call_args.args[:4],(store,'t'*43,'browser-ip','browser-ip'))
  self.assertEqual(state['actor'],{'email':'test'})
  self.assertTrue(state['_daily_restore_checked'])

 def test_stale_local_token_falls_back_without_ignoring_client(self):
  actor=object()
  with patch.object(daily,'restore',side_effect=[None,actor]) as restore:
   self.assertIs(daily.restore_candidates(object(),['s'*43,'c'*43],'browser-ip'),actor)
  self.assertEqual([x.args[2] for x in restore.call_args_list],['browser-ip','browser-ip'])
