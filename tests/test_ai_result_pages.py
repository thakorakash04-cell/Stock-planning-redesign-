import base64,io
from unittest.mock import patch
import pytest
import streamlit as st
from openpyxl import load_workbook
from test_stock_assistant import accounts
from stock_accounts.assistant_insights import evidence_records,export_evidence,report_scope
from stock_accounts.store import AccessDenied

def test_complete_result_pages_and_full_query_download(accounts):
 s,a,v=accounts
 table={'id':'T1','name':'Results','headers':['SKU','Quantity'],'rows':[['SKU'+str(i),i] for i in range(151)]}
 query={'table':'T1','columns':['SKU','Quantity'],'limit':20}
 entry={'version':'test','scope':report_scope(s,v),'query':query}
 st.session_state['_stock_ai_exports']={'viewer':entry,'admin':{**entry,'scope':report_scope(s,a)}}
 records=[]
 for page in range(4):
  result=evidence_records(s,v,{'source_id':'viewer','version':'test','page':page},[table],'test')
  assert result['total']==151
  records.extend(result['records'])
 assert len(records)==151 and records[-1]['SKU']=='SKU150'
 with pytest.raises(AccessDenied):export_evidence(s,v,{'export_id':'viewer','version':'test'},[table],'test')
 file=export_evidence(s,a,{'export_id':'admin','version':'test'},[table],'test')
 wb=load_workbook(io.BytesIO(base64.b64decode(file['content'])),read_only=True)
 rows=list(wb['Result table'].values)
 assert len(rows)==152 and rows[-1][-1]==150
 with pytest.raises(ValueError):evidence_records(s,v,{'source_id':'viewer','version':'old'},[table],'test')
 with patch('stock_accounts.assistant_insights.report_scope',return_value='changed'):
  with pytest.raises(AccessDenied):evidence_records(s,v,{'source_id':'viewer','version':'test'},[table],'test')

def test_calculated_table_pages_include_last_record(accounts):
 s,a,v=accounts
 table={'name':'Calculated','headers':['SKU','Value'],'rows':[[str(i),i*10] for i in range(5001)]}
 st.session_state['_stock_ai_exports']={'calc':{'version':'v','scope':report_scope(s,v),'table':table}}
 result=evidence_records(s,v,{'source_id':'calc','version':'v','page':100},[],'v')
 assert result['total']==5001 and result['records']==[{'SKU':'5000','Value':50000}]

def test_aggregate_result_can_open_every_underlying_source_record(accounts):
 s,a,v=accounts
 table={'id':'T1','name':'Rows','headers':['Segment','Qty'],'rows':[['Red',i] for i in range(151)]}
 query={'table':'T1','group_by':['Segment'],'metrics':[{'column':'Qty','op':'sum'}],'limit':20}
 st.session_state['_stock_ai_exports']={'q':{'version':'v','scope':report_scope(s,v),'query':query}}
 summary=evidence_records(s,v,{'source_id':'q','version':'v'},[table],'v')
 source=evidence_records(s,v,{'source_id':'q','version':'v','view':'source','page':3},[table],'v')
 assert summary['total']==1 and source['total']==151 and source['records'][0]['Qty']==150
