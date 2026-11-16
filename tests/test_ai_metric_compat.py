import copy
from unittest.mock import patch
import pytest
from grounded_ai import execute_query,QueryPlanError
from stock_accounts import table_columns as cols
from stock_accounts.cross_sheet import calculate
from test_stock_assistant import accounts
from test_latest_101_column import BASE,TABLES,proposed

@pytest.mark.parametrize('metric',[
 {'field':'Posting Date','function':'latest_date','alias':'Latest 101 Date'},
 {'column':'Posting Date','aggregation':'MAX_DATE','name':'Latest 101 Date'},
 {'column':'Posting Date','operator':'LATEST','alias':'Latest 101 Date'},
 {'column':'Posting Date','op':'latest','alias':'Latest 101 Date'},
 {'field':'Posting Date','aggregation_function':'latest_date','as':'Latest 101 Date'},
 {'column':'Posting Date','operation':'latest','alias':'Latest 101 Date'},
])
def test_metric_spellings_and_aliases_work_through_join_restore_and_drill(accounts,metric):
 s,a,v=accounts;version=s.get_dataset(a)['version'];p=proposed()
 p['plan']['sources'][1]['metrics']=[metric];p['plan']['columns']=['s1.Latest 101 Date']
 before=copy.deepcopy(p)
 event={'action':'table_column_plan',**BASE,'question':'add latest 101 date','version':version,'consent':True}
 with patch.object(cols,'source_tables',return_value=(TABLES,version)),patch.object(cols,'settings',return_value=('key','model')),patch.object(cols,'generate',return_value=p) as ai:
  result=cols.handle(s,a,event);assert ai.call_count==1
 assert result['columns'][0]['values']==['2026-02-02','2026-12-10','2026-03-04',None] and p==before
 with patch.object(cols,'source_tables',return_value=(TABLES,version)),patch.object(cols,'generate') as ai:
  saved=[result['definition']]
  assert cols.handle(s,a,{**event,'action':'table_columns_resolve','definitions':saved})['columns']==result['columns']
  detail=cols.handle(s,a,{**event,'action':'table_column_records','definitions':saved,'column':'Latest 101 Date','row_index':0})
  assert next(t for t in detail['tables'] if t['name'].startswith('Matching records'))['total']==2
  assert detail['tables'][-1]['rows'][0][-1]=='2026-02-02'
  ai.assert_not_called()

def test_metric_alias_is_resolved_in_sort_projection_and_arithmetic_without_mutation():
 table={'id':'T','name':'Prices','headers':['Material','Price'],'rows':[['A',5],['A',15],['B',3]]}
 q={'table':'T','group_by':['Material'],'metrics':[{'column':'Price','function':'average','name':'Average Price'}],'columns':['Average Price'],'sort_by':'Average Price','descending':True}
 result=execute_query([table],q,all_rows=True)
 assert result['records']==[{'Material':'A','mean(Price)':10.0},{'Material':'B','mean(Price)':3.0}]
 base={'id':'BASE','name':'Current','headers':['Material','Qty'],'rows':[['A',2],['B',4]]}
 plan={'sources':[{'alias':'s0','table':'BASE'},{'alias':'s1',**q}],'joins':[{'left_on':['s0.Material'],'right_on':['s1.Material']}],'calculations':[{'name':'Value','op':'multiply','operands':['s0.Qty','s1.Average Price']}],'columns':['calc.Value']}
 before=copy.deepcopy(plan)
 assert calculate([base,table],plan)['tables'][-1]['rows']==[[20.0],[12.0]]
 assert plan==before

@pytest.mark.parametrize('metric',[
 {'column':'Price','op':'sum','expression':'arbitrary code'},
 {'column':'Price','op':'eval'},
 {'column':'Price','op':'sum','function':'sum'},
 {'column':'Price','op':'sum','alias':{'code':'anything'}},
 {'column':'Price','op':'sum','name':'A','alias':'A'},
])
def test_metric_expressions_unknown_fields_and_conflicting_aliases_are_rejected(metric):
 table={'id':'T','name':'Prices','headers':['Price'],'rows':[[5]]}
 with pytest.raises(QueryPlanError):execute_query([table],{'table':'T','metrics':[metric]},all_rows=True)

def test_unsupported_metric_has_only_one_repair(accounts):
 s,a,v=accounts;version=s.get_dataset(a)['version'];bad=proposed();bad['plan']['sources'][1]['metrics'][0]['unexpected']=True
 event={'action':'table_column_plan',**BASE,'question':'add latest 101 date','version':version,'consent':True}
 with patch.object(cols,'source_tables',return_value=(TABLES,version)),patch.object(cols,'settings',return_value=('key','model')),patch.object(cols,'generate',side_effect=[bad,proposed()]) as ai:
  result=cols.handle(s,a,event);assert ai.call_count==2
  assert 'AI calculation was unsupported' in ai.call_args.args[3]['validation_error']
  assert result['columns'][0]['values'][0]=='2026-02-02'


def test_conflicting_metric_output_names_are_not_guessed():
 table={'id':'T','name':'Prices','headers':['Price'],'rows':[[5],[10]]}
 with pytest.raises(QueryPlanError,match='ambiguous'):
  execute_query([table],{'table':'T','metrics':[{'column':'Price','op':'sum','alias':'Value'},{'column':'Price','op':'max','alias':'Value'}]})

def test_metric_alias_references_allow_normalized_case_and_punctuation():
 table={'id':'T','name':'Dates','headers':['Date'],'rows':[['31/01/2026'],['02/02/2026']]}
 base={'id':'BASE','name':'Current','headers':['Key'],'rows':[['A']]}
 plan={'sources':[{'alias':'s0','table':'BASE'},{'alias':'s1','table':'T','metrics':[{'field':'Date','function':'MAX_DATE','alias':'Latest date'}]}],'joins':[{'left_on':['s0.Key'],'right_on':['s1.latest date']}],'columns':['s1.max_date(Date)']}
 # No matching date is a blank lookup, but alias resolution must still succeed.
 assert calculate([base,table],plan)['tables'][-1]['rows']==[[None]]
