import copy
from unittest.mock import patch
from datetime import date
import pytest
import streamlit as st
from test_stock_assistant import accounts
from stock_accounts.insight_dashboard import filter_table,filter_values,facets
from stock_accounts.pnl import lead_observations,material_selection


def test_membership_is_or_within_field_and_and_between_fields_without_duplicate_rows():
 table={'id':'T','name':'Stock','headers':['Segment','SKU','Qty'],'rows':[['A','01',2],['B','02',3],['C','03',4],['A','02',5]]}
 filters=[{'column':'Segment','op':'in','value':['A','B','A']},{'column':'SKU','op':'in','value':['02']},{'column':'Qty','op':'gte','value':3}]
 assert filter_table(table,filters)['rows']==[['B','02',3],['A','02',5]]
 assert filter_table(table,[{'column':'Segment','op':'in','value':[]}])['rows']==[]
 assert filter_table(table,[])['rows']==table['rows']


def test_typed_checkbox_values_preserve_blanks_codes_numbers_and_case():
 table={'id':'T','name':'Typed','headers':['Value'],'rows':[[None],[''],[1],[1.0],['1'],['01'],[True],['A'],['a']]}
 assert filter_table(table,[{'column':'Value','op':'in','value':[1,None,'01']}])['rows']==[[None],[1],[1.0],['01']]
 assert filter_table(table,[{'column':'Value','op':'in','value':['A']}])['rows']==[['A']]
 for value in ['A',{'execute':'bad'},[{}],[float('nan')],list(range(501))]:
  with pytest.raises(ValueError):filter_table(table,[{'column':'Value','op':'in','value':value}])


def test_numeric_and_blank_columns_have_filter_choices_and_large_lists_are_lazy():
 table={'id':'T','name':'Large','headers':['SKU','Qty','Blank'],'rows':[[str(i),i,None] for i in range(301)]}
 result=facets(table)
 assert [f['column'] for f in result]==table['headers']
 assert result[0]['search_only'] and result[1]['search_only']
 assert result[2]['values']==[None]


def test_searchable_choices_use_all_saved_rows_and_recheck_access(accounts):
 from stock_accounts.assistant_insights import data_revision,report_scope
 from stock_accounts.planning_assistant import knowledge
 store,admin,viewer=accounts;version=store.get_dataset(viewer)['version']
 table={'id':'T','name':'Large','headers':['SKU'],'rows':[[str(i).zfill(4)] for i in range(301)]}
 st.session_state['_stock_dashboard_reports']={'r':{'version':version,'scope':report_scope(store,viewer),'planning_revision':str(data_revision(store,viewer)),'knowledge_revision':knowledge()['revision'],'tables':[table],'views':{0:{'table':'Large'}}}}
 event={'report_id':'r','version':version,'view':0,'column':'SKU','query':'','offset':0}
 first=filter_values(store,viewer,event,version)
 assert first['total']==301 and len(first['values'])==100 and first['nextOffset']==100
 assert filter_values(store,viewer,{**event,'query':'0300'},version)['values']==['0300']
 assert len(filter_values(store,viewer,{**event,'offset':300},version)['values'])==1
 with pytest.raises(PermissionError):filter_values(store,admin,event,version)
 with pytest.raises(ValueError):filter_values(store,viewer,{**event,'column':'forged'},version)
 store.update_permissions(admin,'viewer_user',{'menu_0':False});viewer=store.login('viewer_user','Test-viewer-password!123')
 with pytest.raises(PermissionError):filter_values(store,viewer,event,version)


def test_pnl_multi_types_reuse_same_observations_without_double_counting():
 headers=['Code','Name','Batch','PO','PO date','Inward','QC','Use','Lead','QC days','Use days','Type','Segment']
 rows=[['A','Raw','1','PO','2026-01-01','2026-01-11',None,None,10,None,5,'RM','Care'],['B','Pack','2','PO','2026-01-01','2026-01-11',None,None,20,None,7,'PM','Care'],['C','Other','3','PO','2026-01-01','2026-01-11',None,None,30,None,9,'FG','Care']]
 with patch('stock_accounts.lead_time.build',return_value=({'headers':headers,'rows':rows},{})):
  result=lead_observations({},date(2026,1,1),date(2026,1,31),{'Care'},['RM','PM','RM'])
  single=lead_observations({},date(2026,1,1),date(2026,1,31),{'Care'},'RM')
  empty=lead_observations({},date(2026,1,1),date(2026,1,31),{'Care'},[])
 assert len(result[1])==2 and result[0]['Care']==[6,15]
 assert len(single[1])==1 and single[0]['Care']==[5,10]
 assert not empty[1] and material_selection(['PM','RM','PM'])==['PM','RM']
 with pytest.raises(ValueError):material_selection([{}])


def test_admin_access_log_multi_users_filters_before_pagination(accounts):
 from stock_accounts.portal_console import handle
 store,admin,viewer=accounts
 store.log_event(admin,'tool_use','admin-event');store.log_event(viewer,'tool_use','viewer-event')
 response=handle(store,admin,{'operation':'accessLog','usernames':[admin.username,viewer.username],'offset':0},{})
 assert {r['username'] for r in response['rows']}=={admin.username,viewer.username}
 assert handle(store,admin,{'operation':'accessLog','usernames':[]},{})['rows']==[]
 assert handle(store,admin,{'operation':'accessLog','usernames':["x' OR 1=1 --"]},{})['rows']==[]
 with pytest.raises(PermissionError):handle(store,viewer,{'operation':'accessLog','usernames':[admin.username]},{})
 with pytest.raises(ValueError):handle(store,admin,{'operation':'accessLog','usernames':'all'},{})
