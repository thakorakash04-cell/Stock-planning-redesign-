"""A migrated TEXT account version must match the INTEGER remembered-session version."""
import sqlite3,tempfile,unittest
from pathlib import Path
from dataclasses import replace
from stock_accounts.store import Store,AccessDenied,session_version
import daily_sessions as daily
class ImportedSessionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'legacy.db'
  with sqlite3.connect(self.path) as db:db.execute("CREATE TABLE accounts(username TEXT PRIMARY KEY,salt TEXT NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,session_version TEXT NOT NULL DEFAULT '1',failed_attempts INTEGER NOT NULL DEFAULT 0,locked_until DOUBLE PRECISION NOT NULL DEFAULT 0,created_at DOUBLE PRECISION NOT NULL)")
  self.store=Store('sqlite:///'+str(self.path));self.store.bootstrap_admin('test_admin','Synthetic-test-password!123');self.actor=self.store.login('test_admin','Synthetic-test-password!123')
 def tearDown(self):self.tmp.cleanup()
 def test_real_text_schema_login_then_integer_token_restores_new_store(self):
  self.assertIsInstance(self.actor.version,str);actor,token,expiry=daily.issue(self.store,self.actor,'browser')
  restored=daily.restore(Store(self.store.url),token,'browser');self.assertIsNotNone(restored);self.assertIsInstance(restored.version,int);self.assertEqual(restored.expires_at,expiry);self.assertEqual(self.store.identity(restored)['username'],'test_admin')
  daily.revoke(self.store,actor);self.assertIsNone(daily.restore(Store(self.store.url),token,'browser'))
 def test_changed_version_and_disabled_account_still_reject(self):
  actor,token,_=daily.issue(self.store,self.actor,'browser')
  with self.store.transaction() as db:self.store.run(db,'UPDATE accounts SET session_version=session_version+1 WHERE username=?',('test_admin',))
  self.assertIsNone(daily.restore(Store(self.store.url),token,'browser'))
  current=self.store.login('test_admin','Synthetic-test-password!123');_,other,_=daily.issue(self.store,current,'browser')
  with self.store.transaction() as db:self.store.run(db,'UPDATE accounts SET active=0 WHERE username=?',('test_admin',))
  self.assertIsNone(daily.restore(Store(self.store.url),other,'browser'))
  for value in [None,True,False,1.5,'1.0','bad','0',0,-1]:
   self.assertIsNone(session_version(value))
   with self.assertRaises(AccessDenied):self.store.identity(replace(actor,version=value))
if __name__=='__main__':unittest.main()
