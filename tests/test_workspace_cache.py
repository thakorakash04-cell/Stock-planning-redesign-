from unittest.mock import Mock,patch,MagicMock
import pytest
from stock_accounts.workspace import workspace_payload
from stock_accounts.store import AccessDenied

def test_payload_reuses_same_revision_and_refreshes_on_shared_update():
    store=Mock();store.identity.return_value={'role':'viewer','permissions':{}};actor=Mock(username='viewer',session_id='session')
    store.transaction=MagicMock();store.get_dataset.return_value=None;store.portal_read.return_value={}
    store.run.return_value.fetchone.return_value={'version':'v1','updated_at':1}
    del store.dataset_revision
    with patch('stock_accounts.product_catalog.metadata',return_value='empty'),patch('stock_accounts.product_catalog.read',return_value={'version':'empty','products':[]}),patch('stock_accounts.production.shared',return_value=[]),patch('stock_accounts.availability_cache.revision',return_value=''),patch('stock_accounts.workspace.st.session_state',{}),patch('stock_accounts.workspace.ui_payload',side_effect=[({'marker':'first'},[], 'v1'),({'marker':'next'},[],'v2')]) as payload:
        assert workspace_payload(store,actor)[0]['marker']=='first'
        assert workspace_payload(store,actor)[0]['marker']=='first'
        assert store.get_dataset.call_count==1
        store.run.return_value.fetchone.return_value={'version':'v2','updated_at':2}
        assert workspace_payload(store,actor)[0]['marker']=='next'
        assert payload.call_count==2
        store.require.side_effect=AccessDenied('Revoked')
        with pytest.raises(AccessDenied):workspace_payload(store,actor)

def test_ongoing_override_refreshes_payload_without_workbook_change():
    store=Mock();store.identity.return_value={'role':'viewer','permissions':{}};actor=Mock(username='viewer',session_id='session')
    store.transaction=MagicMock();store.get_dataset.return_value=None;store.portal_read.return_value={};store.run.return_value.fetchone.return_value={'version':'v1','updated_at':1}
    with patch('stock_accounts.availability_cache.revision',return_value=''),patch('stock_accounts.product_catalog.metadata',return_value='empty'),patch('stock_accounts.product_catalog.read',return_value={'version':'empty','products':[]}),patch('stock_accounts.production.shared',return_value=[]) as shared,patch('stock_accounts.workspace.st.session_state',{}),patch('stock_accounts.workspace.ui_payload',side_effect=[({'marker':'before'},[],'v1'),({'marker':'after'},[],'v1')]) as payload:
        assert workspace_payload(store,actor)[0]['marker']=='before'
        shared.return_value=[{'kind':'ongoing','id':'order','revision':1,'updated_at':2}]
        assert workspace_payload(store,actor)[0]['marker']=='after'
        assert payload.call_count==2



def test_product_name_update_reuses_master_payload():
    store=Mock();store.identity.return_value={'role':'viewer','permissions':{}};actor=Mock(username='viewer',session_id='session')
    store.transaction=MagicMock();store.get_dataset.return_value=None;store.portal_read.return_value={};store.run.return_value.fetchone.return_value={'version':'v1','updated_at':1}
    with patch('stock_accounts.availability_cache.revision',return_value=''),patch('stock_accounts.product_catalog.metadata',side_effect=['c1','c2']),patch('stock_accounts.product_catalog.read',side_effect=[{'version':'c1','products':[]},{'version':'c2','products':[{'name':'Renamed'}]}]),patch('stock_accounts.production.shared',return_value=[]),patch('stock_accounts.workspace.st.session_state',{}),patch('stock_accounts.workspace.ui_payload',return_value=({'marker':'master'},[],'v1')) as payload:
        first=workspace_payload(store,actor)[0];second=workspace_payload(store,actor)[0]
        assert first['productCatalogue']['version']=='c1'
        assert second['productCatalogue']['products'][0]['name']=='Renamed'
        assert store.get_dataset.call_count==1
        assert payload.call_count==1
