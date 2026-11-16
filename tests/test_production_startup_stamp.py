from unittest.mock import patch
from test_stock_assistant import accounts
from test_production import fixture
from stock_accounts.production import read,shared
from stock_accounts.view_cache import metadata
from stock_accounts.availability_cache import revision
from stock_accounts.workspace import decorate_workspace

def test_startup_stamp_matches_conditional_batch_metadata(accounts):
 store,admin,_=accounts;store.save_dataset(admin,'Master.xlsx',fixture())
 report=read(store,admin);current=store.get_dataset(admin);identity=store.identity(admin)
 master=(current['version'],current['updated_at']);plans=str([(r['kind'],r['id'],r['revision'],r['updated_at']) for r in shared(store,admin)])
 key=(admin.username,admin.session_id,master,str(identity['permissions']),27,(),plans,str(identity.get('allowedSegments')),revision(store,admin,master,identity))
 with patch('streamlit.session_state',{'_workspace_payload':(key,None)}),patch('stock_accounts.product_catalog.read',return_value={'version':'catalog','products':[]}):
  decorated=decorate_workspace(store,admin,{'accessibleTabs':[3],'production':report},catalog_version='catalog',identity=identity)
 assert decorated['production']['displayStamp']==metadata(store,admin,{'action':'production_status'})
 assert 'displayStamp' not in report,'Stamp decoration does not mutate the retained report'
