import copy
from unittest.mock import patch
import pytest
from grounded_ai import execute_query,QueryPlanError
from stock_accounts import table_columns as cols
from test_stock_assistant import accounts
from test_latest_101_column import BASE,TABLES,proposed

T=[{'id':'T','name':'Records','headers':['Movement Type','Note'],'rows':[[101,'A'],['101',''],[102,None],[103,'B']]}]
def query(filters):return execute_query(T,{'table':'T','filters':filters},all_rows=True)

@pytest.mark.parametrize('f',[
 {'field':'movement type','operator':'=','values':[101]},
 {'column':'Movement Type','op':'equals','value':101},
 {'column':'Movement Type','op':'EQ','value':101},
 {'column':'Movement Type','op':'in','values':[101]},
])
def test_unambiguous_literal_filter_spellings(f):
 result=query([f]);assert result['matched_records']==2
 assert result['query']['filters'][0]['column']=='Movement Type'

def test_blank_null_membership_and_conditions_are_distinct():
 assert query([{'column':'Note','op':'is_null'}])['matched_records']==1
 assert query([{'column':'Note','op':'is_not_null'}])['matched_records']==3
 assert query([{'column':'Note','op':'is_blank'}])['matched_records']==2
 assert query([{'column':'Note','op':'not_blank'}])['matched_records']==2
 assert query([{'column':'Movement Type','op':'in','value':[101,102]}])['matched_records']==3
 assert query([{'column':'Movement Type','op':'not_in','value':[101,102]}])['matched_records']==1
 assert query([{'column':'Movement Type','op':'in','value':[101,102]},{'column':'Note','op':'not_blank'}])['matched_records']==1

@pytest.mark.parametrize('f',[
 {'column':'Movement Type','op':'eq','value':101,'sql':'SELECT *'},
 {'column':'Movement Type','field':'Movement Type','op':'eq','value':101},
 {'column':'Movement Type','op':'eq','value':[101,102]},
 {'column':'Movement Type','op':'in','value':[{'sql':'anything'}]},
 {'column':'Movement Type','op':'in','value':[]},
 {'column':'Movement Type','op':'eq'},
 {'column':'Movement Type','op':'execute','value':101},
 {'column':'Note','op':'not_null','value':'A'},
 {'column':'Movement Type','op':'in','value':list(range(101))},
 {'column':'Movement Type','op':'eq','value':float('inf')},
])
def test_unknown_extra_conflicting_or_executable_filters_remain_rejected(f):
 with pytest.raises(QueryPlanError):query([f])

def test_latest_101_alias_filters_restore_and_drill_without_ai(accounts):
 s,a,v=accounts;version=s.get_dataset(a)['version'];p=proposed()
 p['plan']['sources'][1]['filters']=[{'field':'Movement Type','operator':'=','values':[101]},{'field':'Posting Date','operator':'is_not_null'}]
 event={'action':'table_column_plan',**BASE,'question':'add latest 101 date','version':version,'consent':True}
 with patch.object(cols,'source_tables',return_value=(TABLES,version)),patch.object(cols,'settings',return_value=('key','model')),patch.object(cols,'generate',return_value=p) as ai:
  result=cols.handle(s,a,event);assert ai.call_count==1
 assert result['columns'][0]['values']==['2026-02-02','2026-12-10','2026-03-04',None]
 with patch.object(cols,'source_tables',return_value=(TABLES,version)),patch.object(cols,'generate') as ai:
  saved=[result['definition']]
  assert cols.handle(s,a,{**event,'action':'table_columns_resolve','definitions':saved})['columns']==result['columns']
  detail=cols.handle(s,a,{**event,'action':'table_column_records','definitions':saved,'column':'Latest 101 Date','row_index':0})
  assert next(t for t in detail['tables'] if t['name'].startswith('Matching records'))['total']==2
  ai.assert_not_called()

def test_malformed_filter_uses_one_repair_not_silent_condition_removal(accounts):
 s,a,v=accounts;version=s.get_dataset(a)['version'];bad=proposed();bad['plan']['sources'][1]['filters'][0]['extra']=True
 event={'action':'table_column_plan',**BASE,'question':'add latest 101 date','version':version,'consent':True}
 with patch.object(cols,'source_tables',return_value=(TABLES,version)),patch.object(cols,'settings',return_value=('key','model')),patch.object(cols,'generate',side_effect=[bad,proposed()]) as ai:
  result=cols.handle(s,a,event);assert ai.call_count==2
  assert 'AI filter was unsupported' in ai.call_args.args[3]['validation_error']
  assert result['columns'][0]['values'][0]=='2026-02-02'
