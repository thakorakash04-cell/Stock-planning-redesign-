"""Never consume a login write acknowledgement without its storage result."""
from types import SimpleNamespace
from unittest.mock import patch
import pytest
import streamlit as st
import daily_sessions as daily

class Rerun(Exception):pass
class Stop(Exception):pass

def mount_result(state,result):
    with patch('streamlit.session_state',state),patch('streamlit.fragment',side_effect=lambda fn:fn),patch('streamlit.components.v2.component',return_value=lambda **kw:result),patch('streamlit.rerun',side_effect=Rerun),patch('streamlit.stop',side_effect=Stop),patch('streamlit.caption'),patch('streamlit.warning'),patch('streamlit.button',return_value=False):
        daily.mount(object())

def test_old_partial_ack_cannot_discard_pending_cookie_write():
    state={'_daily_browser_instance':'instance','_daily_browser_checked':True,'_daily_cookie_action':{'nonce':'n'}}
    with pytest.raises(Stop):mount_result(state,SimpleNamespace(ack='n',storage=None))
    assert state['_daily_cookie_action']['nonce']=='n'
    for saved in (True,False):
        current=dict(state)
        with pytest.raises(Rerun):mount_result(current,SimpleNamespace(session={'instance':'instance','receipt':{'nonce':'n','saved':saved}}))
        assert '_daily_cookie_action' not in current
        assert current['_daily_storage_failed'] is (not saved)

def test_storage_receipt_from_old_connection_cannot_ack_new_connection():
    state={'_daily_browser_instance':'new','_daily_browser_checked':True,'_daily_cookie_action':{'nonce':'n'}}
    with pytest.raises(Stop):mount_result(state,SimpleNamespace(session={'instance':'old','receipt':{'nonce':'n','saved':True}}))
    assert '_daily_cookie_action' in state

def test_request_client_is_stable_through_native_login_and_fragment_handoffs():
    state={}
    with patch.object(daily,'request_client',side_effect=['initial-browser-ip','transient-proxy-value']):
        daily.restore_cookie(object(),state,{})
        daily.restore_cookie(object(),state,{})
    assert state['_daily_client']=='initial-browser-ip'


def test_browser_hydration_preserves_visible_activity_for_existing_daily_jobs():
    state={'_daily_browser_instance':'instance','_daily_browser_checked':True}
    mount_result(state,SimpleNamespace(session={'instance':'instance','browser':{'at':100,'visible':True}}))
    assert state['_browser_last_activity']==100 and state['_browser_visible'] is True
