"""First-paint delivery, deferred source scope and native/fragment session handoffs."""
import json,unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
import pytest
import streamlit as st
from test_stock_assistant import accounts
import test_segment_access as segment_fixture
from test_segment_access import master
from stock_accounts.workspace_insights import _render_exact_workspace,handle_request
from stock_accounts.workspace_delivery import model_scope,payload
from stock_accounts import preload
import test_sales as sales_fixture

class State(dict):
    __getattr__=dict.__getitem__
    __setattr__=dict.__setitem__
class Rerun(BaseException):pass


def test_first_component_render_does_not_read_finance_or_ship_models():
    identity={'username':'admin','role':'admin','permissions':{},'allowedSegments':None}
    store=SimpleNamespace(identity=Mock(return_value=identity),record_access=Mock())
    models=[{'name':'MB52','headers':['Material','Qty'],'rows':[['M'+str(i),i] for i in range(10000)]}]
    data={'filename':'Master.xlsx','sheets':[{'name':'Stock','headers':['Material','Qty'],'rows':[['M1',1]]}]}
    with patch('streamlit.session_state',State()),patch('streamlit.markdown'),patch('stock_accounts.workspace_insights.workspace_payload',return_value=(data,models,'v1')),patch('stock_accounts.preferences.read',return_value={}),patch('stock_accounts.workspace_insights._component') as component,patch('stock_accounts.sales.read',side_effect=AssertionError('Sales blocked first paint')),patch('stock_accounts.pnl.report',side_effect=AssertionError('PnL blocked first paint')):
        _render_exact_workspace(store,object(),identity)
    args=component.call_args.kwargs
    assert args['data']['filename']=='Master.xlsx' and args['tables'] is None
    assert args['tablesDeferred'] and args['preload']['deferred']
    assert len(json.dumps(args))<5000


def test_fragment_logout_revokes_token_and_hands_browser_clear_to_outer_app(accounts):
    import daily_sessions as daily
    store,admin,_=accounts;state=State();actor=daily.start(store,state,admin);token=state['_daily_cookie_action']['value']
    state['exact_website_ui']={'id':'logout-now','action':'logout'}
    with patch('streamlit.session_state',state),patch('streamlit.markdown'),patch('streamlit.rerun',side_effect=Rerun):
        with pytest.raises(Rerun):_render_exact_workspace(store,actor,store.identity(actor))
    assert daily.restore(store,token) is None and not state['_daily_cookie_action']['value']


def test_fragment_administration_navigation_keeps_actor_and_requests_full_handoff(accounts):
    store,admin,_=accounts;state=State(actor=admin,exact_website_ui={'id':'open-admin','action':'open_admin'})
    with patch('streamlit.session_state',state),patch('streamlit.markdown'),patch('streamlit.rerun',side_effect=Rerun):
        with pytest.raises(Rerun):_render_exact_workspace(store,admin,store.identity(admin))
    assert state['_account_page']=='admin' and state['actor']==admin

class DeferredModelTests(unittest.TestCase):
    setUp=segment_fixture.SegmentTests.setUp
    tearDown=segment_fixture.SegmentTests.tearDown
    def test_model_delivery_checks_live_actor_segment_scope_and_version(self):
        version=self.store.get_dataset(self.viewer)['version'];scope=model_scope(self.store.identity(self.viewer),version)
        event={'action':'workspace_model_tables','version':version,'modelScope':scope}
        with patch('streamlit.session_state',{}):
            result=handle_request(self.store,self.viewer,event)
            assert 'BLUE-PRIVATE' not in json.dumps(result) and 'Blue product' not in json.dumps(result)
            assert next(t for t in result['tables'] if t['name']=='BOM')['rows'][0][0]=='A'
            with self.assertRaises(ValueError):handle_request(self.store,self.viewer,{**event,'modelScope':'forged'})
            changed=master();changed['sheets'][0]['rows'][0][2]=101
            self.store.save_dataset(self.admin,'Updated.xlsx',changed)
            with self.assertRaises(ValueError):handle_request(self.store,self.viewer,event)
            self.store.update_viewer(self.admin,'viewer',active=False)
            with self.assertRaises(PermissionError):handle_request(self.store,self.viewer,event)

class DeferredFinanceTests(unittest.TestCase):
    setUp=sales_fixture.StorageAndRights.setUp
    tearDown=sales_fixture.StorageAndRights.tearDown
    upload=sales_fixture.StorageAndRights.upload
    store_planning=sales_fixture.StorageAndRights.store_planning
    def test_finance_warms_later_and_fresh_iframe_recovers_once_after_ack(self):
        self.upload();state={}
        first=preload.load_after_paint(self.s,self.a,state)
        assert first['preload']['sales']['primary']['available']
        preload.acknowledge(self.s,self.a,{'preloadId':first['preload']['id']},state)
        second=preload.load_after_paint(self.s,self.a,state)
        assert second['preload']['id']!=first['preload']['id']
        assert second['preload']['sales']['primary']['rows']==first['preload']['sales']['primary']['rows']
    def test_source_change_while_warming_discards_mixed_preload(self):
        state={}
        with patch('stock_accounts.preload.versions',side_effect=[{'primary':'v1'},{'primary':'v1'},{'primary':'v2'}]):
            with self.assertRaisesRegex(ValueError,'sources changed'):preload.load_after_paint(self.s,self.a,state)
        assert '_workspace_preload' not in state
