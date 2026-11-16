"""Regression for Streamlit processes retaining pre-update generic helper modules."""
import sys,tempfile,types
from pathlib import Path
from unittest.mock import patch
import streamlit as st
from streamlit.testing.v1 import AppTest

def test_startup_and_login_ignore_stale_legacy_helper_modules():
    old_auth=types.ModuleType('workspace_auth')
    old_auth.require_workspace=lambda:None
    old_store=types.ModuleType('workspace_store')
    # Deliberately omit can/require_permission/Store, as an older cached helper can.
    with tempfile.TemporaryDirectory() as folder:
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)
        at.secrets.update({'DATABASE_URL':'sqlite:///'+str(Path(folder)/'startup.db'),
            'ADMIN_USERNAME':'startup_admin','ADMIN_PASSWORD':'Startup-admin-password!123'})
        with patch('daily_sessions.mount',return_value=None), patch.dict(sys.modules,{'workspace_auth':old_auth,'storage':old_store,'exact_ui':types.ModuleType('exact_ui')}):
            at.run()
            assert not at.exception
            assert any(field.label=='Username or email' for field in at.text_input)
            at.text_input(key='login_username').set_value('startup_admin')
            at.text_input(key='login_password').set_value('Startup-admin-password!123')
            next(button for button in at.button if button.label=='Sign in').click().run()
            assert not at.exception
            assert at.session_state['actor'].username=='startup_admin'
            assert len(at.get('component_instance'))==1
        st.cache_resource.clear()

def test_startup_refreshes_an_older_analysis_protocol_without_reloading_accounts():
    import stock_accounts.workspace_insights as workspace
    import stock_accounts.store as account_store
    old_store_class=account_store.Store
    with tempfile.TemporaryDirectory() as folder:
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)
        at.secrets.update({'DATABASE_URL':'sqlite:///'+str(Path(folder)/'analysis-startup.db'),
            'ADMIN_USERNAME':'startup_admin','ADMIN_PASSWORD':'Startup-admin-password!123'})
        def stale(*args,**kwargs):raise ValueError('Unknown operation.')
        with patch.object(workspace,'INSIGHTS_REVISION',1),patch.object(workspace,'handle_request',stale):
            at.run()
            assert not at.exception
            assert workspace.INSIGHTS_REVISION==36
            assert workspace.handle_request is not stale
            assert account_store.Store is old_store_class
        st.cache_resource.clear()

def test_startup_refreshes_dispatcher_from_before_planning():
    import stock_accounts.workspace_insights as workspace
    import stock_accounts.store as account_store
    old_store_class=account_store.Store
    with tempfile.TemporaryDirectory() as folder:
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)
        at.secrets.update({'DATABASE_URL':'sqlite:///'+str(Path(folder)/'planning-startup.db'),
            'ADMIN_USERNAME':'startup_admin','ADMIN_PASSWORD':'Startup-admin-password!123'})
        def stale(*args,**kwargs):raise ValueError('Unknown operation.')
        with patch.object(workspace,'PLANNING_REVISION',0),patch.object(workspace,'handle_request',stale):
            at.run()
            assert not at.exception
            assert workspace.PLANNING_REVISION==36
            assert workspace.handle_request is not stale
            assert account_store.Store is old_store_class
        st.cache_resource.clear()


def test_startup_uses_new_account_cache_revision_after_permission_upgrade():
    from stock_accounts.auth import initialize
    from stock_accounts.store import Store
    with tempfile.TemporaryDirectory() as folder:
        url='sqlite:///'+str(Path(folder)/'permission-cache.db')
        legacy=initialize(url,'startup_admin','Startup-admin-password!123',store_revision='2026-10-15-login-fix')
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)
        at.secrets.update({'DATABASE_URL':url,'ADMIN_USERNAME':'startup_admin','ADMIN_PASSWORD':'Startup-admin-password!123'})
        at.run();assert not at.exception
        current=initialize(url,'startup_admin','Startup-admin-password!123',store_revision='2026-10-17-access-rights-v2')
        assert current is not legacy
        assert isinstance(current,Store)
    st.cache_resource.clear()




def test_startup_refreshes_custom_column_planner_without_reloading_accounts():
    import stock_accounts.cross_sheet as cross_sheet
    import grounded_ai as grounded
    import stock_accounts.preferences as preferences
    import stock_accounts.table_columns as columns
    import stock_accounts.assistant_insights as assistant
    import stock_accounts.store as account_store
    old_store_class=account_store.Store
    with tempfile.TemporaryDirectory() as folder:
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)
        at.secrets.update({'DATABASE_URL':'sqlite:///'+str(Path(folder)/'column-startup.db'),
            'ADMIN_USERNAME':'startup_admin','ADMIN_PASSWORD':'Startup-admin-password!123'})
        def stale(*args,**kwargs):raise ValueError('The first source must be the unchanged current table.')
        with patch.object(cross_sheet,'REVISION',4),patch.object(cross_sheet,'calculate',stale),patch.object(grounded,'QUERY_SCHEMA_REVISION',3),patch.object(grounded,'execute_query',stale),patch.object(preferences,'REVISION',0),patch.object(preferences,'validate_scope',stale),patch.object(columns,'REVISION',8),patch.object(columns,'handle',stale),patch.object(assistant,'INSIGHTS_REVISION',10),patch.object(assistant,'stock_tables',stale):
            at.run()
            assert not at.exception
            assert cross_sheet.REVISION==5
            assert cross_sheet.calculate is not stale
            assert grounded.QUERY_SCHEMA_REVISION==5
            assert grounded.execute_query is not stale
            assert preferences.REVISION==1
            assert preferences.validate_scope is not stale
            assert columns.REVISION==9
            assert columns.handle is not stale
            assert assistant.INSIGHTS_REVISION==21
            assert assistant.stock_tables is not stale
            assert account_store.Store is old_store_class
        st.cache_resource.clear()
