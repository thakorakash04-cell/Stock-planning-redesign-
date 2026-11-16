import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from stock_accounts.store import Store
from stock_accounts.portal_console import handle
from test_segment_access import master

class RetainedStore:
    """Model a cached pre-segment Store exposing the established database API."""
    def __init__(self,store):self.store=store
    def __getattr__(self,name):
        if name=='update_segments':raise AttributeError('old cached Store has no update_segments')
        return getattr(self.store,name)

class AccountSaveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store('sqlite:///'+str(Path(self.tmp.name)/'save.db'))
        self.store.bootstrap_admin('admin','AdminPassword123!');self.admin=self.store.login('admin','AdminPassword123!')
        self.store.save_dataset(self.admin,'master.xlsx',master());self.store.create_viewer(self.admin,'viewer','ViewerPassword123!',email='old@example.invalid')
        self.event={'operation':'memberSave','username':'viewer','email':'new@example.invalid','permissions':{'download':True},'allowedSegments':['Red'],'active':True}
    def tearDown(self):self.tmp.cleanup()
    def test_existing_account_saves_through_retained_store(self):
        result=handle(RetainedStore(self.store),self.admin,self.event,{})
        self.assertTrue(result['ok']);viewer=self.store.login('new@example.invalid','ViewerPassword123!')
        self.assertTrue(self.store.identity(viewer)['permissions']['download'])
        self.assertEqual(self.store.identity(viewer)['allowedSegments'],['Red'])
    def test_initializer_does_not_use_stale_imported_store_class(self):
        from stock_accounts import auth
        auth.initialize.clear()
        with patch.object(auth,'Store',side_effect=AssertionError('stale class used')):
            current=auth.initialize(self.store.url,'admin','AdminPassword123!',store_revision='atomic-save-test')
        self.assertTrue(callable(current.update_segments))
        auth.initialize.clear()
    def test_storage_reload_preserves_session_types_and_migrates_old_schema(self):
        import importlib
        from stock_accounts import store as storage
        actor_type,denied_type=storage.Actor,storage.AccessDenied
        with self.store.transaction() as db:
            self.store.run(db,'ALTER TABLE accounts DROP COLUMN allowed_segments')
        importlib.reload(storage)
        self.assertIs(storage.Actor,actor_type)
        self.assertIs(storage.AccessDenied,denied_type)
        current=storage.Store(self.store.url)
        self.assertEqual(current.identity(self.admin)['role'],'admin')
        handle(current,self.admin,self.event,{})
        viewer=current.login('new@example.invalid','ViewerPassword123!')
        self.assertEqual(current.identity(viewer)['allowedSegments'],['Red'])

    def test_admin_email_change_does_not_expire_own_session(self):
        handle(self.store,self.admin,{'operation':'memberSave','username':'admin','email':'admin@example.invalid','permissions':{}},{})
        self.assertEqual(self.store.identity(self.admin)['role'],'admin')

    def test_new_account_failure_does_not_leave_partial_profile(self):
        event={**self.event,'create':True,'username':'new_viewer','password':'ViewerPassword123!'}
        with patch.object(self.store,'_log',side_effect=RuntimeError('audit write failed')):
            with self.assertRaises(RuntimeError):handle(self.store,self.admin,event,{})
        self.assertNotIn('new_viewer',self.store.profiles(self.admin))
        self.assertFalse(any(u['username']=='new_viewer' for u in self.store.users(self.admin)))

    def test_failure_rolls_back_profile_rights_and_segments(self):
        before=self.store.users(self.admin);version=next(u for u in before if u['username']=='viewer')
        original=self.store.run
        def failing(db,sql,args=()):
            if 'UPDATE accounts' in sql and 'allowed_segments' in sql:raise RuntimeError('simulated database write failure')
            return original(db,sql,args)
        with patch.object(self.store,'run',side_effect=failing):
            with self.assertRaises(RuntimeError):handle(self.store,self.admin,self.event,{})
        self.assertEqual(self.store.profiles(self.admin)['viewer'],'old@example.invalid')
        self.assertEqual(next(u for u in self.store.users(self.admin) if u['username']=='viewer')['permissions'],version['permissions'])
        self.assertIsNotNone(self.store.login('old@example.invalid','ViewerPassword123!'))

if __name__=='__main__':unittest.main()
