from unittest.mock import patch
from pathlib import Path
import pytest
from stock_accounts.store import Store,AccessDenied
from stock_accounts.assistant_insights import handle_ai
from stock_accounts import planning_assistant as planner

def test_lightweight_status_never_prepares_source_records(tmp_path):
 store=Store('sqlite:///'+str(tmp_path/'db'));store.bootstrap_admin('admin_user','Test-admin-password!123');actor=store.login('admin_user','Test-admin-password!123')
 with patch('stock_accounts.assistant_insights.stock_tables',side_effect=AssertionError('Source tables prepared')),patch('grounded_ai.settings',return_value=('private-key','model')):
  empty=handle_ai(store,actor,{'action':'ai_status','lightweight':True})
  assert empty['workbook_ready'] is False and empty['version']=='empty'
  store.save_dataset(actor,'book.xlsx',{'sheets':[{'name':'Stock','headers':['Material'],'rows':[['A']]}],'tables':[]})
  status=handle_ai(store,actor,{'action':'ai_status','lightweight':True})
  assert status['workbook_ready'] is True and status['version']!='empty'
  assert status['filename']=='book.xlsx' and 'private-key' not in str(status)
  store.create_viewer(actor,'viewer_user','Test-viewer-password!123');store.update_permissions(actor,'viewer_user',{'use_tools':False});viewer=store.login('viewer_user','Test-viewer-password!123')
  with pytest.raises(AccessDenied):handle_ai(store,viewer,{'action':'ai_status','lightweight':True})

def test_knowledge_reuses_parse_but_refreshes_and_does_not_share_mutations(tmp_path):
 path=tmp_path/'rules.py';path.write_text('def calculate():\n return 1\n')
 with patch.object(planner,'ROOT',tmp_path),patch.object(planner,'SOURCES',['rules.py']),patch.object(planner.ast,'parse',wraps=planner.ast.parse) as parse:
  first=planner.knowledge();second=planner.knowledge()
  assert parse.call_count==1
  first['deployed_features'].clear()
  assert planner.knowledge()['deployed_features']
  path.write_text('def calculate():\n return 2\n')
  changed=planner.knowledge()
  assert changed['revision']!=second['revision'] and parse.call_count==2
