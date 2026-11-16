"""Authenticated startup must open the workspace, including old safe bookmarks."""
import time
from pathlib import Path
from unittest.mock import patch
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

@pytest.mark.parametrize('safe_bookmark',[False,True])
def test_restored_session_opens_workspace_without_landing(tmp_path,safe_bookmark):
    at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)
    at.secrets.update({'DATABASE_URL':'sqlite:///'+str(tmp_path/'startup.db'),
        'ADMIN_USERNAME':'startup_admin','ADMIN_PASSWORD':'Startup-admin-password!123'})
    if safe_bookmark:at.query_params['safe']='1'
    def restore(store,state,cookies):
        if not state.get('actor'):
            state['actor']=store.login('startup_admin','Startup-admin-password!123')
            state['login_at']=time.time()
    def workspace(*args):st.caption('Authenticated workspace rendered')
    with patch('daily_sessions.restore_cookie',restore),patch('daily_sessions.mount',return_value=None),patch('stock_accounts.workspace_insights.render_exact_workspace',workspace):
        for _ in range(2):
            at.run()
            assert not at.exception
            assert not at.error
            assert any(x.value=='Authenticated workspace rendered' for x in at.caption)
            assert not any('Recovery' in b.label or 'Open full workspace' in b.label for b in at.button)
    st.cache_resource.clear()
