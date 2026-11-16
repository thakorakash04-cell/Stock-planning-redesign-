import os,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
import streamlit as st
from streamlit.testing.v1 import AppTest
from storage import Store,AccessDenied
IS_STOCK=True
RIGHT='download'

class AccountScreenTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.url='sqlite:///'+str(Path(self.tmp.name)/'screens.db')
        self.env=patch.dict(os.environ,{'DATABASE_URL':self.url,'ADMIN_USERNAME':'admin_user','ADMIN_PASSWORD':'Initial-admin-password!123'});self.env.start()
        self.store=Store(self.url);self.store.bootstrap_admin('admin_user','Initial-admin-password!123');self.admin=self.store.login('admin_user','Initial-admin-password!123')
        self.store.create_viewer(self.admin,'viewer_user','Initial-viewer-password!123')
    def tearDown(self):st.cache_resource.clear();self.env.stop();self.tmp.cleanup()
    def test_branded_login_uses_saved_public_appearance(self):
        self.store.portal_save(self.admin,{'title':'Custom portal','login_text':'First purpose line.\nSecond purpose line.','signin_heading':'Secure portal sign in'})
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)
        at.secrets.update({'DATABASE_URL':self.url,'ADMIN_USERNAME':'admin_user','ADMIN_PASSWORD':'Initial-admin-password!123'})
        at.run();self.assertFalse(at.exception)
        self.assertTrue(any(x.value=='Secure portal sign in' for x in at.title))
        markup=' '.join(x.value for x in at.markdown)
        self.assertIn('portal-brand',markup);self.assertIn('First purpose line.',markup);self.assertIn('Portal logo',markup)
        self.assertIsNotNone(at.text_input(key='login_username'));self.assertTrue(any(x.label=='Forgot password?' for x in at.expander))

    def login(self,username,password):
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)
        at.secrets.update({'DATABASE_URL':self.url,'ADMIN_USERNAME':'admin_user','ADMIN_PASSWORD':'Initial-admin-password!123'})
        at.run();at.text_input(key='login_username').set_value(username);at.text_input(key='login_password').set_value(password)
        next(b for b in at.button if b.label=='Sign in').click().run();self.assertEqual(len(at.exception),0)
        return at
    def open_screen(self,at,screen):
        if IS_STOCK:
            at.session_state['exact_website_ui']={'id':uuid.uuid4().hex,'action':'open_admin' if screen=='users' else 'open_password'};at.run()
        else:at.toggle(key='workspace_'+screen).set_value(True).run()
        self.assertEqual(len(at.exception),0)
    def test_navigation_preserves_pending_table_preferences(self):
        from stock_accounts.workspace import handle_request
        from stock_accounts.preferences import read
        for page in ('admin','workbook','email','history'):
            result=handle_request(self.store,self.admin,{'action':'open_'+page,'preferences':[
                {'scope':'grid:main:A','value':{'hidden':[page]}},
                {'scope':'invalid?','value':{}},
            ]})
            self.assertEqual(result['route'],page)
            self.assertEqual(read(self.store,self.admin)['grid:main:A'],{'hidden':[page]})

    def test_admin_can_edit_rights_and_inspect_logs(self):
        at=self.login('admin_user','Initial-admin-password!123');self.open_screen(at,'users')
        self.assertEqual(len(at.get('component_instance')),1)
        at.session_state['portal_admin_console']={'id':uuid.uuid4().hex,'operation':'memberSave','username':'viewer_user','email':'viewer@example.invalid','permissions':{'download':True},'active':True};at.run()
        self.assertFalse(at.exception);self.assertNotIn('error',at.session_state['_console_response'])
        viewer=self.store.login('viewer_user','Initial-viewer-password!123')
        self.assertTrue(self.store.identity(viewer)['permissions']['download'])
        self.assertTrue(any(e['action']=='permissions_changed' for e in self.store.access_log(self.admin)))

    def test_every_role_can_change_own_password(self):
        for username,old,new in [('viewer_user','Initial-viewer-password!123','New-viewer-password!123'),('admin_user','Initial-admin-password!123','New-admin-password!123')]:
            at=self.login(username,old);self.open_screen(at,'password')
            next(x for x in at.text_input if x.label=='Current password').set_value(old)
            next(x for x in at.text_input if x.label=='New password (at least 12 characters)').set_value(new)
            next(x for x in at.text_input if x.label=='Confirm new password').set_value(new)
            next(b for b in at.button if b.label=='Change password').click().run()
            self.assertEqual(len(at.exception),0)
            self.assertTrue(any(x.label=='Username or email' for x in at.text_input))
            self.assertIsNotNone(Store(self.url).login(username,new))
    def test_manage_users_opens_in_one_run_and_returns_to_dashboard(self):
        at=self.login('admin_user','Initial-admin-password!123')
        at.session_state['exact_website_ui']={'id':uuid.uuid4().hex,'action':'open_admin'}
        with patch('streamlit.rerun',side_effect=AssertionError('Initial navigation must not trigger an extra rerun')):at.run()
        self.assertFalse(at.exception);self.assertEqual(len(at.get('component_instance')),1)
        self.assertEqual(at.session_state['_account_page'],'admin')
        at.session_state['portal_admin_console']={'id':uuid.uuid4().hex,'operation':'consoleClose'};at.run()
        self.assertFalse(at.exception);self.assertNotIn('_account_page',at.session_state)
        self.assertEqual(len(at.get('component_instance')),1)

    def test_back_returns_in_same_run_without_extra_rerun(self):
        at=self.login('admin_user','Initial-admin-password!123');self.open_screen(at,'users')
        at.session_state['portal_admin_console']={'id':uuid.uuid4().hex,'operation':'consoleClose'}
        with patch('streamlit.rerun',side_effect=AssertionError('Back must render workspace in the same run')):
            at.run()
        self.assertFalse(at.exception)
        self.assertNotIn('_account_page',at.session_state)
        if not IS_STOCK:
            self.assertFalse(at.session_state['workspace_users'])
            self.assertEqual(at.session_state['portal_admin_navigation'],'Workspace')
            self.assertTrue(any(x.value=='Regulatory Framework' for x in at.title))

    def test_live_app_component_receives_production_rows_at_login(self):
        import json
        from test_production_snapshot import dataset
        self.store.save_dataset(self.admin,'master.xlsx',dataset())
        at=self.login('admin_user','Initial-admin-password!123')
        args=json.loads(at.get('component_instance')[0].proto.json_args)
        self.assertEqual(len(args['data']['production']['ongoing']),1)
        self.assertEqual(len(args['data']['production']['qc']['rows']),1)
        self.assertEqual(args['data']['production']['ongoing'][0]['row'][5],100)
        self.store.update_permissions(self.admin,'viewer_user',{'menu_3':False})
        restricted=self.login('viewer_user','Initial-viewer-password!123')
        args=json.loads(restricted.get('component_instance')[0].proto.json_args)
        self.assertNotIn('production',args['data'])

    def test_live_app_includes_cached_order_materials_at_login(self):
        import json
        from test_order_snapshot import planning_dataset
        self.store.save_dataset(self.admin,'master.xlsx',planning_dataset())
        at=self.login('admin_user','Initial-admin-password!123')
        args=json.loads(at.get('component_instance')[0].proto.json_args)
        self.assertEqual([r['code'] for r in args['data']['orderRequirements']['options']],['A','S'])
        self.assertEqual(len(args['data']['orderRequirements']['summary']['rows']),3)
        self.store.update_permissions(self.admin,'viewer_user',{'menu_6':False})
        restricted=self.login('viewer_user','Initial-viewer-password!123')
        args=json.loads(restricted.get('component_instance')[0].proto.json_args)
        self.assertNotIn('orderRequirements',args['data'])

    def test_segment_limited_login_never_sends_other_segment_rows(self):
        import json
        from test_segment_access import master
        self.store.save_dataset(self.admin,'master.xlsx',master())
        self.store.update_segments(self.admin,'viewer_user',['Red'])
        at=self.login('viewer_user','Initial-viewer-password!123')
        args=json.loads(at.get('component_instance')[0].proto.json_args)
        text=json.dumps(args['data'])+json.dumps(args['tables'])
        self.assertNotIn('Blue product',text)
        self.assertNotIn('BLUE-PRIVATE',text)
        self.assertNotIn('Shared mixed-segment demand',text)
        self.assertEqual([m['code'] for m in args['data']['orderRequirements']['options']],['A'])

    def test_deployment_replaces_old_bootstrap_and_embedded_screens(self):
        import json
        from test_segment_access import master
        self.store.save_dataset(self.admin,'master.xlsx',master())
        at=self.login('admin_user','Initial-admin-password!123')
        component=at.get('component_instance')[0]
        self.assertTrue(component.proto.component_name.endswith('stock_planning_web_ui_v2'))
        self.assertEqual(json.loads(component.proto.json_args)['data']['workspaceRevision'],2)
        at.session_state['_console_bootstrap']={'users':[],'segments':[]}
        at.session_state['_console_bootstrap_revision']=1
        self.open_screen(at,'users')
        component=at.get('component_instance')[0]
        self.assertTrue(component.proto.component_name.endswith('portal_admin_console_v4'))
        bootstrap=json.loads(component.proto.json_args)['bootstrap']
        self.assertEqual(bootstrap['segments'],['Blue','Red'])
        self.assertTrue(any(u['username']=='viewer_user' for u in bootstrap['users']))

    def test_viewer_cannot_open_admin_console(self):
        at=self.login('viewer_user','Initial-viewer-password!123')
        if IS_STOCK:
            at.session_state['exact_website_ui']={'id':uuid.uuid4().hex,'action':'open_admin'};at.run()
            self.assertNotIn('_account_page',at.session_state)
        else:self.assertFalse(any(x.label=='Manage users' for x in at.toggle))
        self.assertFalse(any(x.value=='Access log' for x in at.subheader))

    def test_production_and_menu_rights_save_repeatedly_with_confirmation(self):
        at=self.login('admin_user','Initial-admin-password!123');self.open_screen(at,'users')
        old_viewer=self.store.login('viewer_user','Initial-viewer-password!123')
        for enabled in [True,False]:
            at.session_state['portal_admin_console']={'id':uuid.uuid4().hex,'operation':'memberSave','username':'viewer_user','email':'','permissions':{'edit_production':enabled,'edit_upcoming':enabled,'menu_0':not enabled},'active':True};at.run()
            self.assertFalse(at.exception);self.assertNotIn('error',at.session_state['_console_response'])
            viewer=self.store.login('viewer_user','Initial-viewer-password!123');rights=self.store.identity(viewer)['permissions']
            self.assertEqual(rights['edit_production'],enabled);self.assertEqual(rights['menu_0'],not enabled)
        with self.assertRaises(AccessDenied):self.store.identity(old_viewer)

    def test_permission_save_error_is_shown_without_crashing(self):
        at=self.login('admin_user','Initial-admin-password!123');self.open_screen(at,'users')
        at.session_state['portal_admin_console']={'id':uuid.uuid4().hex,'operation':'memberSave','username':'viewer_user','email':'','permissions':{'download':True}}
        with patch('stock_accounts.account_admin.save_member',side_effect=ValueError('Permission settings need refresh')):at.run()
        self.assertFalse(at.exception);self.assertEqual(at.session_state['_console_response']['error'],'Permission settings need refresh')

    def test_unexpected_save_failure_has_safe_diagnostic_reference(self):
        at=self.login('admin_user','Initial-admin-password!123');self.open_screen(at,'users')
        at.session_state['portal_admin_console']={'id':uuid.uuid4().hex,'operation':'memberSave','username':'viewer_user','permissions':{}}
        with patch('stock_accounts.account_admin.save_member',side_effect=RuntimeError('private database connection details')):at.run()
        self.assertFalse(at.exception)
        error=at.session_state['_console_response']['error']
        self.assertIn('Reference ',error);self.assertIn('(RuntimeError)',error)
        self.assertNotIn('private database connection details',error)
