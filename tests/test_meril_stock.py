from test_stock_assistant import accounts
from stock_accounts.meril_stock import apply

def report(rows,stamp=0):
 return {'available':True,'headers':['FG Code','Billed Qty','Segment'],'segmentIndex':2,'rows':rows,'source':{'updated_at':stamp}}

def test_fg_aggregation_signed_values_energy_exclusion_and_ist_date():
 table={'headers':['Material','Stock'],'rows':[['001',8],['FG2',1],['ED',2]]}
 p=report([['001',10,'Care'],['001',-2,'Care'],['FG2',1,'Care'],['ED',40,'Energy Device']])
 s=report([['001',3,'Care'],['FG2',5,'Care'],['ED',4,'Energy Device']],1767205800)
 r=apply(table,p,s,{'ED':['Energy Device']})
 assert r['rows'][0][-2:]==[5,'2026-01-01']
 assert r['rows'][1][-2]==-4
 assert r['rows'][2][-2:]==[None,None]
 assert table['rows'][0]==['001',8]

def test_missing_sources_columns_and_invalid_values_stay_unknown():
 t={'headers':['Material'],'rows':[['A'],['B']]}
 assert apply(t,{},report([]),{})['rows'][0][-2] is None
 p=report([['A',None,'Care']]);s=report([])
 assert apply(t,p,s,{})['rows'][0][-2] is None
 assert apply(t,p,s,{})['rows'][1][-2]==0
 p['headers'][1]='Billed Value'
 assert apply(t,p,s,{})['rows'][1][-2] is None


def test_matching_exact_code_excludes_other_skus_and_energy():
 from stock_accounts.meril_stock import matching
 source=report([['001',10,'Care'],['1',20,'Care'],['001',4,'Energy Device'],[' 001 ',2,'Care']])
 assert matching(source,'001')==[source['rows'][0],source['rows'][3]]


def test_evidence_totals_include_all_pages_and_deny_disabled_access(accounts):
 from unittest.mock import patch
 from stock_accounts.meril_stock import records
 from stock_accounts.store import AccessDenied
 import pytest
 store,admin,viewer=accounts
 p=report([['FG',1,'Care'] for _ in range(205)]+[['OTHER',900,'Care']]);s=report([['FG',20,'Care']])
 with patch('stock_accounts.meril_stock.read',side_effect=lambda store,actor,event:p if event['kind']=='primary' else s),patch('stock_accounts.sales.bom_source_index',return_value=(set(),{},'v')):
  result=records(store,admin,{'material':'FG','pages':{'primary':1}})
  assert result['primary']['total']==205 and len(result['primary']['rows'])==5
  assert result['primary']['billedQuantity']==205 and result['secondary']['billedQuantity']==20
  assert result['expectedStock']==185
  with pytest.raises(ValueError):records(store,admin,{'material':'FG','pages':{'primary':-1}})
 store.update_permissions(admin,'viewer_user',{'menu_0':False})
 viewer=store.login('viewer_user','Test-viewer-password!123')
 with pytest.raises(AccessDenied):records(store,viewer,{'material':'FG'})


def test_verification_requires_sales_access(accounts):
 import pytest
 from stock_accounts.meril_stock import records
 from stock_accounts.store import AccessDenied
 store,admin,viewer=accounts
 with pytest.raises(AccessDenied):records(store,viewer,{'material':'FG'})
