"""Retained Store resources must restore across module eviction, not only reload."""
import importlib,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import stock_accounts
import stock_accounts.store as original
import daily_sessions as daily
class StoreActorReloadTests(unittest.TestCase):
 def test_cached_store_restores_after_its_module_is_evicted(self):
  with tempfile.TemporaryDirectory() as folder:
   store=original.Store('sqlite:///'+str(Path(folder)/'db'));store.bootstrap_admin('test_admin','Synthetic-test-password!123');actor=store.login('test_admin','Synthetic-test-password!123');actor,token,_=daily.issue(store,actor,'browser')
   name='stock_accounts.store';old=sys.modules.pop(name)
   try:
    newer=importlib.import_module(name);self.assertIsNot(newer.Actor,original.Actor)
    self.assertFalse(isinstance(actor,newer.Actor))
    with self.assertRaises(original.AccessDenied):store.identity(newer.Actor(actor.username,actor.version,actor.session_id,actor.expires_at))
    restored=daily.restore(store,token,'browser');self.assertIsNotNone(restored);self.assertIsInstance(restored,original.Actor);self.assertEqual(store.identity(restored)['username'],'test_admin')
    # A fresh resource still uses its own class and the same live SQL checks.
    fresh=newer.Store(store.url);other=daily.restore(fresh,token,'browser');self.assertIsInstance(other,newer.Actor)
    daily.revoke(fresh,other);self.assertIsNone(daily.restore(store,token,'browser'))
   finally:sys.modules[name]=old;stock_accounts.store=old
 def test_pre_factory_cached_store_uses_its_login_constructor(self):
  with tempfile.TemporaryDirectory() as folder:
   store=original.Store('sqlite:///'+str(Path(folder)/'db'));store.bootstrap_admin('test_admin','Synthetic-test-password!123');actor=store.login('test_admin','Synthetic-test-password!123');actor,token,_=daily.issue(store,actor,'browser')
   with patch.object(store,'make_actor',None):
    restored=daily.restore(store,token,'browser');self.assertIsInstance(restored,original.Actor);self.assertEqual(restored.session_id,actor.session_id)
if __name__=='__main__':unittest.main()
