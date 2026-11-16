import importlib,tempfile,unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo
import daily_sessions as daily

MODULE='stock_accounts.store'

class DailySessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.url='sqlite:///'+str(Path(self.tmp.name)/'daily.db')
        self.module=importlib.import_module(MODULE);self.store=self.module.Store(self.url)
        self.store.bootstrap_admin('admin_user','Initial-admin-password!123')
        self.admin=self.store.login('admin_user','Initial-admin-password!123')
        self.store.create_viewer(self.admin,'viewer_user','Initial-viewer-password!123')
        self.viewer=self.store.login('viewer_user','Initial-viewer-password!123')
    def tearDown(self):self.tmp.cleanup()
    def test_permission_denial_keeps_daily_login_and_stale_storage_falls_back_to_cookie(self):
        actor,token,_=daily.issue(self.store,self.viewer,'same-browser-ip')
        with self.assertRaises(self.module.AccessDenied):self.store.identity(actor) and self.store.users(actor)
        self.assertTrue(daily.session_valid(self.store,actor))
        restored=daily.restore_candidates(self.store,['s'*43,token],'same-browser-ip')
        self.assertEqual(restored.session_id,actor.session_id)
        self.assertIsNone(daily.restore_candidates(self.store,[token],'different-ip'))
        daily.revoke(self.store,actor)
        self.assertFalse(daily.session_valid(self.store,actor))
        self.assertIsNone(daily.restore_candidates(self.store,['s'*43,token],'same-browser-ip'))
    def test_token_survives_new_store_and_browser_refresh(self):
        state={};actor=daily.start(self.store,state,self.viewer)
        cookie=state['_daily_cookie_action'];self.assertNotIn('password',str(cookie));self.assertEqual(len(cookie['value']),43)
        with self.store.transaction() as db:
            row=self.store.run(db,f'SELECT token_hash FROM {daily.table(self.store)}').fetchone()
            self.assertNotEqual(row['token_hash'],cookie['value'])
        new_store=self.module.Store(self.url);new_state={}
        daily.restore_cookie(new_store,new_state,{daily.cookie_name(new_store):cookie['value']})
        self.assertEqual(new_state['actor'].username,'viewer_user');self.assertEqual(new_state['actor'].session_id,actor.session_id)
        self.assertEqual(new_store.identity(new_state['actor'])['role'],'viewer')
    def test_expiry_is_fixed_midnight_not_renewed_by_restore(self):
        now=datetime(2026,10,20,23,59,50,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
        with patch('daily_sessions.time.time',return_value=now):
            actor,token,expiry=daily.issue(self.store,self.viewer)
            self.assertEqual(expiry,now+10)
        with patch('daily_sessions.time.time',return_value=now+9):
            self.assertEqual(daily.restore(self.store,token).expires_at,expiry)
        with patch('daily_sessions.time.time',return_value=expiry):
            self.assertIsNone(daily.restore(self.store,token))
            with self.assertRaises(PermissionError):self.store.identity(actor)
    def test_signout_revokes_even_another_restored_tab(self):
        state={};actor=daily.start(self.store,state,self.viewer);token=state['_daily_cookie_action']['value']
        tab=daily.restore(self.store,token);daily.clear(self.store,state)
        self.assertIsNone(daily.restore(self.store,token));self.assertFalse(state['_daily_cookie_action']['value'])
        with self.assertRaises(PermissionError):self.store.identity(tab)
    def test_account_disable_password_and_right_changes_invalidate_token(self):
        for operation in ('password','rights','disable'):
            viewer=self.store.login('viewer_user','Initial-viewer-password!123')
            actor,token,_=daily.issue(self.store,viewer)
            if operation=='password':
                self.store.update_viewer(self.admin,'viewer_user',password='Replacement-password!123')
                self.assertIsNone(daily.restore(self.store,token))
                self.store.update_viewer(self.admin,'viewer_user',password='Initial-viewer-password!123')
            elif operation=='rights':self.store.update_permissions(self.admin,'viewer_user',{'download':True})
            else:self.store.update_viewer(self.admin,'viewer_user',active=False)
            self.assertIsNone(daily.restore(self.store,token))
            with self.assertRaises(PermissionError):self.store.identity(actor)
    def test_invalid_tokens_and_copied_other_database_token_fail(self):
        _,token,_=daily.issue(self.store,self.viewer)
        for value in (None,'','forged',token[:-1]+'!',token[:-1]+('a' if token[-1]!='a' else 'b')):
            self.assertIsNone(daily.restore(self.store,value))
        other=self.module.Store('sqlite:///'+str(Path(self.tmp.name)/'other.db'))
        self.assertIsNone(daily.restore(other,token))
    def test_cannot_issue_for_revoked_or_forged_actor(self):
        self.store.update_viewer(self.admin,'viewer_user',active=False)
        with self.assertRaises(PermissionError):daily.issue(self.store,self.viewer)

