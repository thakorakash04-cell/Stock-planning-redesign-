import pytest
from grounded_ai import context_for

def test_table_context_is_metadata_not_records_or_access():
 tables=[{'id':'T1','name':'Stock','headers':['Material','Qty'],'rows':[['A',5]]}]
 context={'kind':'table','table':'Stock','view':'main:Stock','headers':['Material','Qty']}
 selected=context_for(tables,context)
 assert selected['matching_sources']==[{'id':'T1','name':'Stock'}]
 assert 'record' not in selected and 'rows' not in selected
 assert 'not authoritative' in selected['basis']
 assert context_for([],context)['matching_sources']==[]
 assert context_for(tables,{'table':'Stock','row':['A',5],'column':'Qty'})['record']['Qty']==5
 with pytest.raises(ValueError):context_for(tables,{**context,'rows':[['B',99]]})
 with pytest.raises(ValueError):context_for(tables,{**context,'headers':['x']*251})
 with pytest.raises(ValueError):context_for(tables,{**context,'table':'x'*201})
