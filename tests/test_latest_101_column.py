from unittest.mock import patch
import pytest
from grounded_ai import execute_query,QueryPlanError
from stock_accounts import table_columns as cols
from test_stock_assistant import accounts

BASE={'headers':['Material','Batch','Order'],'rows':[['001','B1','100'],['002','B1','200'],['001','B2','300'],['003','B3','400']]}
TABLES=[{'id':'MOV','name':'MB51','source_key':'model:mb51','headers':['Material','Batch','Order','Movement Type','Posting Date'],'rows':[
 ['001','B1','100',101,'31/01/2026'],['001','B1','100',101,'02/02/2026'],['001','B1','100',102,'28/02/2026'],
 ['002','B1','200',101,'10/12/2026'],['001','B2','300',101,'04/03/2026']]}]
def proposed(grouped=True):
 source={'alias':'s1','table':'MOV','filters':[{'column':'Movement Type','op':'eq','value':101}]}
 if grouped:source.update(group_by=['Material','Batch','Order'],metrics=[{'column':'Posting Date','op':'latest'}])
 else:source['columns']=['Material','Batch','Order','Posting Date']
 return {'name':'Latest 101 Date','plan':{'sources':[{'alias':'s0','table':'USER_VIEW'},source],'joins':[{'left_on':['s0.Material','s0.Batch','s0.Order'],'right_on':['s1.Material','s1.Batch','s1.Order']}],'calculations':[],'columns':['s1.latest(Posting Date)' if grouped else 's1.Posting Date']}}

def test_latest_101_repair_save_restore_and_matching_records(accounts):
 from stock_accounts.preferences import read
 s,a,v=accounts;version=s.get_dataset(a)['version'];event={'action':'table_column_plan','scope':'production:qc',**BASE,'question':'add latest 101 date in this production table','version':version,'consent':True}
 with patch.object(cols,'source_tables',return_value=(TABLES,version)),patch.object(cols,'settings',return_value=('key','model')),patch.object(cols,'generate',side_effect=[proposed(False),proposed(True)]) as ai:
  result=cols.handle(s,a,event)
  assert ai.call_count==2 and 'Right-side keys are not unique' in ai.call_args.args[3]['validation_error']
 assert result['columns'][0]['values']==['2026-02-02','2026-12-10','2026-03-04',None]
 saved=read(s,a)['columns:production:qc']['definitions']
 fresh=s.login('admin_user','Test-admin-password!123')
 with patch.object(cols,'source_tables',return_value=(TABLES,version)),patch.object(cols,'generate') as ai:
  restored=cols.handle(s,fresh,{**event,'action':'table_columns_resolve','definitions':saved,'consent':False})
  assert restored['columns']==result['columns']
  detail=cols.handle(s,fresh,{**event,'action':'table_column_records','definitions':saved,'column':'Latest 101 Date','row_index':0})
  matches=next(t for t in detail['tables'] if t['name'].startswith('Matching records'))
  assert matches['total']==2 and [r[-1] for r in matches['rows']]==['31/01/2026','02/02/2026']
  assert detail['tables'][-1]['rows'][0][-1]=='2026-02-02'
  ai.assert_not_called()

def test_date_metrics_are_chronological_and_keep_missing_and_numeric_rules():
 table={'id':'T','name':'Dates','headers':['Code','Date'],'rows':[['A','31/01/2026'],['A','02/02/2026'],['A',None],['B',None]]}
 def query(op):return execute_query([table],{'table':'T','group_by':['Code'],'metrics':[{'column':'Date','op':op}]},all_rows=True)['records']
 assert query('latest')==[{'Code':'A','latest(Date)':'2026-02-02'},{'Code':'B','latest(Date)':None}]
 assert query('earliest')[0]['earliest(Date)']=='2026-01-31'
 with pytest.raises(ValueError,match='non-numeric'):query('max')
 table['rows'].append(['A','30/02/2026'])
 with pytest.raises(QueryPlanError,match='invalid date'):query('latest')


def test_invalid_repair_is_bounded_and_ambiguous_duplicates_are_not_silently_deduplicated(accounts):
 s,a,v=accounts;version=s.get_dataset(a)['version'];event={'action':'table_column_plan',**BASE,'question':'add a transaction date','version':version,'consent':True}
 with patch.object(cols,'source_tables',return_value=(TABLES,version)),patch.object(cols,'settings',return_value=('key','model')),patch.object(cols,'generate',side_effect=[proposed(False),{'clarification':'Latest or earliest date, and which keys?'}]) as ai:
  result=cols.handle(s,a,event);assert 'clarification' in result and ai.call_count==2
 with patch.object(cols,'source_tables',return_value=(TABLES,version)),patch.object(cols,'settings',return_value=('key','model')),patch.object(cols,'generate',return_value=proposed(False)) as ai:
  with pytest.raises(ValueError,match='Right-side keys are not unique'):cols.handle(s,a,event)
  assert ai.call_count==2


def test_date_metrics_support_excel_serials_and_reject_boolean_dates():
 from datetime import datetime
 from openpyxl.utils.datetime import to_excel
 table={'id':'T','name':'Dates','headers':['Date'],'rows':[[to_excel(datetime(2026,1,31))],[to_excel(datetime(2026,2,2))]]}
 q={'table':'T','metrics':[{'column':'Date','op':'latest'}]}
 assert execute_query([table],q,all_rows=True)['records'][0]['latest(Date)']=='2026-02-02'
 table['rows']=[[True]]
 with pytest.raises(QueryPlanError,match='invalid date'):execute_query([table],q,all_rows=True)
