"""Upload workspace exposes metadata through the admin-only website API."""
from stock_accounts.store import AccessDenied
from stock_accounts.upload_center import metadata
from test_stock_assistant import accounts
import pytest

def test_admin_metadata_has_all_sources_and_no_payloads(accounts):
 store,admin,viewer=accounts
 result=metadata(store,admin)
 assert set(result)=={'master','orders','sales','pnl'}
 assert result['master']['filename']=='stock.xlsx'
 assert result['master']['updated_at']>0
 from stock_accounts.workspace_insights import handle_request
 assert handle_request(store,admin,{'action':'uploads_status'})['master']['version']==result['master']['version']
 with pytest.raises(AccessDenied):handle_request(store,viewer,{'action':'uploads_status'})
 assert result['orders'] is None and result['sales']==[] and result['pnl']==[]
 assert not any(k in result['master'] for k in ('data','payload','rows'))
 with pytest.raises(AccessDenied):metadata(store,viewer)
