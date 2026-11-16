import copy
from unittest.mock import patch
import pytest
from test_stock_assistant import accounts
from stock_accounts import table_columns as cols
from stock_accounts.store import AccessDenied

BASE={'id':'USER_VIEW','name':'Current table','headers':['Material','Qty'],'rows':[['001',2],['002',0],['X',4]]}
TABLES=[{'id':'PRICE','name':'Price list','headers':['Material','Std DP'],'rows':[['001',10],['002',20]]}]
def plan():return {'sources':[{'alias':'s0','table':'USER_VIEW'},{'alias':'s1','table':'PRICE','columns':['Material','Std DP']}],'joins':[{'left_on':['s0.Material'],'right_on':['s1.Material']}],'calculations':[{'name':'Amount','op':'multiply','operands':['s0.Qty','s1.Std DP']}],'columns':['calc.Amount']}
def definition():return {'name':'Amount','request':'Quantity times standard price','plan':cols.saved_plan(plan(),TABLES)}
def test_join_restore_without_provider_and_preserve_rows(accounts):
 s,a,v=accounts;before=copy.deepcopy(BASE)
 with patch.object(cols,'generate') as ai:
  working,columns,warnings=cols.resolve(s,a,BASE,[definition()],TABLES,s.get_dataset(a))
  assert columns[0]['values']==[20,0,None] and warnings
  assert working['rows'][0]==['001',2,20] and BASE==before
  ai.assert_not_called()
def test_same_table_chained_arithmetic_zero_and_invalid_code(accounts):
 s,a,v=accounts
 d={'name':'Twice','plan':{'sources':[{'alias':'s0','table':'USER_VIEW'}],'joins':[],'calculations':[{'name':'Twice','op':'multiply','operands':['s0.Qty',2]}],'columns':['calc.Twice']}}
 assert cols.calculate(s,a,BASE,d,[],s.get_dataset(a))[0]==[4,0,8]
 d['plan']['calculations'][0]['op']='eval'
 with pytest.raises(ValueError):cols.calculate(s,a,BASE,d,[],s.get_dataset(a))
def test_duplicate_keys_do_not_multiply_and_missing_source_is_blank(accounts):
 s,a,v=accounts;t=copy.deepcopy(TABLES);t[0]['rows'].append(['001',99])
 with pytest.raises(ValueError,match='unique'):cols.calculate(s,a,BASE,definition(),t,s.get_dataset(a))
 assert cols.resolve(s,a,BASE,[definition()],[],s.get_dataset(a))[1][0]['values']==[None]*3
 p=plan();p['sources'][0]['filters']=[{'column':'Qty','op':'gt','value':0}]
 with pytest.raises(ValueError,match='unchanged'):cols.saved_plan(p,TABLES)
def test_handle_consent_revision_and_source_menu_boundary(accounts):
 s,a,v=accounts;version=s.get_dataset(a)['version'];e={'action':'table_column_plan','headers':BASE['headers'],'rows':BASE['rows'],'question':'Amount','version':version}
 with patch.object(cols,'source_tables',return_value=(TABLES,version)),patch.object(cols,'generate',return_value={'name':'Amount','plan':plan()}),patch.object(cols,'settings',return_value=('key','model')):
  with pytest.raises(ValueError,match='sharing'):cols.handle(s,a,e)
  result=cols.handle(s,a,{**e,'consent':True});assert result['columns'][0]['values']==[20,0,None]
  with pytest.raises(ValueError,match='changed'):cols.handle(s,a,{**e,'version':'old'})
 s.update_permissions(a,v.username,{'menu_1':False});v=s.login(v.username,'Test-viewer-password!123')
 with pytest.raises(AccessDenied):cols.calculate(s,v,BASE,definition(),TABLES,s.get_dataset(v))

@pytest.mark.parametrize('metadata',[
 {'columns':['Material']},
 {'columns':['Material','Qty'],'filters':[],'group_by':[],'metrics':[],'sort':[],'limit':20},
 {'columns':[],'filters':None,'group_by':[],'metrics':[],'sort':{}},
])
def test_plain_std_dp_lookup_accepts_harmless_current_source_metadata(accounts,metadata):
 s,a,v=accounts;version=s.get_dataset(a)['version'];before=copy.deepcopy(BASE)
 proposal=plan();proposal['sources'][0].update(metadata);proposal['calculations']=[];proposal['columns']=['s1.Std DP']
 question='add std dp value coloumn based on material from std dp table'
 event={'action':'table_column_plan','headers':BASE['headers'],'rows':BASE['rows'],'question':question,'version':version,'consent':True}
 with patch.object(cols,'source_tables',return_value=(TABLES,version)),patch.object(cols,'generate',return_value={'name':'Std DP','plan':proposal}),patch.object(cols,'settings',return_value=('key','model')):
  result=cols.handle(s,a,event)
 assert result['columns'][0]['values']==[10,20,None]
 assert result['definition']['plan']['sources'][0]=={'alias':'s0','table':'USER_VIEW'}
 assert result['definition']['request']==question and BASE==before
 with patch.object(cols,'generate') as ai:
  restored=cols.resolve(s,a,BASE,[result['definition']],TABLES,s.get_dataset(a))
  assert restored[1][0]['values']==[10,20,None]
  ai.assert_not_called()

@pytest.mark.parametrize('metadata',[
 {'filters':[{'column':'Qty','op':'gt','value':0}]},
 {'group_by':['Material']},
 {'metrics':[{'column':'Qty','op':'sum'}]},
 {'sort':[{'column':'Material','direction':'asc'}]},
 {'table':'PRICE'}, {'alias':'s1'}, {'unexpected':True},
 {'columns':['Unknown']}, {'limit':False},
])
def test_current_source_normalization_does_not_accept_transforms(metadata):
 p=plan();p['sources'][0].update(metadata)
 with pytest.raises(ValueError):cols.saved_plan(p,TABLES,BASE)


def test_saved_projection_and_empty_metadata_restore_without_losing_row_identity(accounts):
 s,a,v=accounts;d=definition();d['plan']['sources'][0].update(columns=['Material'],filters=[],group_by=[],metrics=[],limit=1)
 assert cols.calculate(s,a,BASE,d,TABLES,s.get_dataset(a))[0]==[20,0,None]
 assert d['plan']['sources'][0]['columns']==['Material'],'Normalization must not mutate saved definitions'


def test_direct_std_dp_lookup_keeps_zero_and_code_identity_and_rejects_conflicts(accounts):
 s,a,v=accounts;p=plan();p['calculations']=[];p['columns']=['s1.Std DP']
 tables=copy.deepcopy(TABLES);tables[0]['rows']=[['001',10],['001',10],['002',0],['1',99]]
 d={'name':'Std DP','plan':cols.saved_plan(p,tables,BASE)}
 assert cols.calculate(s,a,BASE,d,tables,s.get_dataset(a))[0]==[10,0,None]
 tables[0]['rows'].append(['001',25])
 with pytest.raises(ValueError,match='unique'):cols.calculate(s,a,BASE,d,tables,s.get_dataset(a))


def test_duplicate_display_names_keep_selected_worksheet_or_model_across_id_changes(accounts):
 from stock_accounts.assistant_insights import stock_tables
 s,a,v=accounts;current=s.get_dataset(a);version=current['version']
 sheet={'name':'Std DP','headers':['Material','Std DP'],'rows':[['001',10],['002',20]]}
 model={**copy.deepcopy(sheet),'rows':[['001',99],['002',0]]}
 data={'sheets':[sheet],'filename':'stock.xlsx','planningRevision':36}
 with patch('stock_accounts.workspace_insights.workspace_payload',return_value=(data,[model],version)):
  tables,_,_=stock_tables(s,a)
 assert [t['name'] for t in tables]==['Std DP','Std DP']
 assert [t['source_kind'] for t in tables]==['worksheet','model']
 assert tables[0]['source_key']!=tables[1]['source_key']
 p=plan();p['sources'][1]['table']=tables[1]['id'];p['calculations']=[];p['columns']=['s1.Std DP']
 event={'action':'table_column_plan','headers':BASE['headers'],'rows':BASE['rows'],'question':'add std dp value column based on material from std dp table','version':version,'consent':True}
 with patch.object(cols,'source_tables',return_value=(tables,version)),patch.object(cols,'generate',return_value={'name':'Std DP','plan':p}) as ai,patch.object(cols,'settings',return_value=('key','model')):
  result=cols.handle(s,a,event)
 assert result['columns'][0]['values']==[99,0,None]
 assert result['definition']['plan']['sources'][1]['source_key']==tables[1]['source_key']
 assert ai.call_args.args[3]['tables'][2]['source_kind']=='model'
 # Add another worksheet and update prices: positional IDs shift, provenance does not.
 updated={**copy.deepcopy(data),'sheets':[{'name':'Other','headers':['Code'],'rows':[['A']]},sheet],'planningRevision':37}
 updated_model={**model,'rows':[['001',88],['002',5]]}
 with patch('stock_accounts.workspace_insights.workspace_payload',return_value=(updated,[updated_model],version)):
  next_tables,_,_=stock_tables(s,a)
 assert next_tables[-1]['id']!=tables[1]['id']
 with patch.object(cols,'generate') as ai:
  assert cols.calculate(s,a,BASE,result['definition'],next_tables,current)[0]==[88,5,None]
  ai.assert_not_called()
 # Removal/revocation of that origin must not silently switch to the namesake.
 with pytest.raises(ValueError,match='missing|permitted'):
  cols.calculate(s,a,BASE,result['definition'],next_tables[:-1],current)


def test_legacy_name_only_definition_still_restores_and_true_identity_collisions_fail(accounts):
 s,a,v=accounts;d=definition();d['plan']['sources'][1].pop('source_key')
 assert cols.calculate(s,a,BASE,d,TABLES,s.get_dataset(a))[0]==[20,0,None]
 duplicated=copy.deepcopy(TABLES)+[{**copy.deepcopy(TABLES[0]),'id':'OTHER'}]
 with pytest.raises(ValueError,match='duplicate identities'):cols.saved_plan(plan(),duplicated,BASE)
 with pytest.raises(ValueError,match='ambiguous'):cols.calculate(s,a,BASE,d,duplicated,s.get_dataset(a))


def test_namesake_sources_with_distinct_schema_can_use_legacy_catalogue_identity(accounts):
 s,a,v=accounts;t=copy.deepcopy(TABLES)+[{'id':'OTHER','name':'Price list','headers':['Material','MRP'],'rows':[['001',500]]}]
 d={'name':'Std DP','plan':cols.saved_plan({**plan(),'calculations':[],'columns':['s1.Std DP']},t,BASE)}
 assert cols.calculate(s,a,BASE,d,list(reversed(t)),s.get_dataset(a))[0]==[10,20,None]


def test_lookup_discovery_finds_std_dp_without_requiring_sheet_name(accounts):
 s,a,v=accounts;version=s.get_dataset(a)['version']
 base={**BASE,'headers':['Material Code','Qty']}
 tables=[{'id':'UNKNOWN_SHEET_ID','name':'Commercial reference','source_kind':'worksheet','source_key':'worksheet:commercial-reference','headers':['Material Number','Std. DP'],'rows':[['001',15],['002',0]]},
         {'id':'COST','name':'Costing','headers':['Material','Standard Price'],'rows':[['001',123]]},
         {'id':'OTHER','name':'Something else','headers':['Description','Std DP'],'rows':[['Item',999]]}]
 question='add std dp against material code column'
 def generated(key,model,instruction,payload,*args,**kwargs):
  candidates=payload['lookup_hints']['candidates']
  assert [c['table'] for c in candidates]==['UNKNOWN_SHEET_ID']
  assert candidates[0]['value_columns']==['Std. DP']
  assert {'current_column':'Material Code','source_column':'Material Number','role':'material_code'} in candidates[0]['matching_keys']
  return {'name':'Std DP','plan':{'sources':[{'alias':'s0','table':'USER_VIEW'},{'alias':'s1','table':'UNKNOWN_SHEET_ID','columns':['Material Number','Std. DP']}],
    'joins':[{'left_on':['s0.Material Code'],'right_on':['s1.Material Number']}],'calculations':[],'columns':['s1.Std. DP']}}
 event={'action':'table_column_plan','headers':base['headers'],'rows':base['rows'],'question':question,'version':version,'consent':True}
 with patch.object(cols,'source_tables',return_value=(tables,version)),patch.object(cols,'generate',side_effect=generated),patch.object(cols,'settings',return_value=('key','model')):
  result=cols.handle(s,a,event)
 assert result['columns'][0]['values']==[15,0,None]
 assert result['definition']['plan']['sources'][1]['table_name']=='Commercial reference'


def test_lookup_hints_include_all_matching_permitted_origins_without_choosing_one():
 tables=[{**TABLES[0],'id':'SHEET','source_kind':'worksheet'}, {**TABLES[0],'id':'MODEL','source_kind':'model'}]
 hints=cols.lookup_hints(BASE,tables,'add standard dp against material code')
 assert [c['table'] for c in hints['candidates']]==['SHEET','MODEL']
 assert [c['source_kind'] for c in hints['candidates']]==['worksheet','model']

def test_add_commits_definition_before_browser_save_and_fresh_login_restores(accounts):
 from stock_accounts.preferences import read
 s,a,v=accounts;version=s.get_dataset(a)['version'];scope='main:Stock [FG], 100%'
 event={'action':'table_column_plan','scope':scope,'headers':BASE['headers'],'rows':BASE['rows'],'question':'Quantity times standard price','version':version,'consent':True}
 with patch.object(cols,'source_tables',return_value=(TABLES,version)),patch.object(cols,'generate',return_value={'name':'Amount','plan':plan()}),patch.object(cols,'settings',return_value=('key','model')):
  added=cols.handle(s,a,event)
 assert added['saved'] is True
 # No browser preferences_save request occurs before logout/new session.
 actor=s.login('admin_user','Test-admin-password!123')
 saved=read(s,actor)['columns:'+scope]['definitions']
 assert saved==[added['definition']] and 'columns:'+scope not in read(s,v)
 with patch.object(cols,'source_tables',return_value=(TABLES,version)),patch.object(cols,'generate') as ai:
  restored=cols.handle(s,actor,{**event,'action':'table_columns_resolve','definitions':saved,'consent':False})
 assert restored['columns'][0]['values']==[20,0,None]
 ai.assert_not_called()

def test_failed_server_save_does_not_acknowledge_success(accounts):
 s,a,v=accounts;version=s.get_dataset(a)['version']
 event={'action':'table_column_plan','scope':'main:Stock','headers':BASE['headers'],'rows':BASE['rows'],'question':'Amount','version':version,'consent':True}
 with patch.object(cols,'source_tables',return_value=(TABLES,version)),patch.object(cols,'generate',return_value={'name':'Amount','plan':plan()}),patch.object(cols,'settings',return_value=('key','model')),patch('stock_accounts.preferences.save',side_effect=ValueError('Database unavailable')):
  with pytest.raises(ValueError,match='Database unavailable'):cols.handle(s,a,event)

def test_added_value_drill_uses_matching_source_records_without_ai(accounts):
 s,a,v=accounts;version=s.get_dataset(a)['version']
 event={'action':'table_column_records','scope':'main:Stock','headers':BASE['headers'],'rows':BASE['rows'],'definitions':[definition()],'column':'Amount','row_index':0,'version':version}
 with patch.object(cols,'source_tables',return_value=(TABLES,version)),patch.object(cols,'generate') as ai:
  details=cols.handle(s,a,event)
  assert details['tables'][0]['rows']==[['001',2]]
  source=next(t for t in details['tables'] if t['name'].startswith('Matching records'))
  assert source['total']==1 and source['rows'][0][1:]==['001',10]
  assert details['tables'][-1]['rows'][0][-1]==20
  missing=cols.handle(s,a,{**event,'row_index':2})
  assert next(t for t in missing['tables'] if t['name'].startswith('Matching records'))['total']==0
  zero=cols.handle(s,a,{**event,'row_index':1})
  assert zero['tables'][-1]['rows'][0][-1]==0
  with pytest.raises(ValueError):cols.handle(s,a,{**event,'row_index':99})
  ai.assert_not_called()

def test_added_value_grouped_lookup_drills_original_filtered_contributors(accounts):
 s,a,v=accounts;version=s.get_dataset(a)['version']
 tables=[{'id':'PRICE','name':'Price list','headers':['Material','Std DP'],'rows':[['001',10],['001',15],['001',-5],['002',99]]}]
 p=plan();p['sources'][1].update(group_by=['Material'],metrics=[{'column':'Std DP','op':'sum'}],filters=[{'column':'Std DP','op':'gt','value':0}]);p['calculations'][0]['operands'][1]='s1.sum(Std DP)'
 d={'name':'Amount','plan':cols.saved_plan(p,tables)}
 with patch.object(cols,'source_tables',return_value=(tables,version)):
  details=cols.handle(s,a,{'action':'table_column_records','headers':BASE['headers'],'rows':BASE['rows'],'definitions':[d],'column':'Amount','row_index':0,'version':version})
 source=next(t for t in details['tables'] if t['name'].startswith('Matching records'))
 assert source['total']==2 and [r[-1] for r in source['rows']]==[10,15]
 assert details['tables'][-1]['rows'][0][-1]==50

def test_added_value_drill_pages_contributors_and_rechecks_source_access(accounts):
 s,a,v=accounts;version=s.get_dataset(a)['version']
 tables=[{'id':'PRICE','name':'Price list','headers':['Material','Std DP'],'rows':[['001',10] for _ in range(51)]}]
 p=plan();p['sources'][1].update(group_by=['Material'],metrics=[{'column':'Std DP','op':'sum'}]);p['calculations'][0]['operands'][1]='s1.sum(Std DP)'
 d={'name':'Amount','plan':cols.saved_plan(p,tables)}
 event={'action':'table_column_records','headers':BASE['headers'],'rows':BASE['rows'],'definitions':[d],'column':'Amount','row_index':0,'version':version}
 with patch.object(cols,'source_tables',return_value=(tables,version)),patch.object(cols,'generate') as ai:
  detail=cols.handle(s,a,{**event,'page':1})
  source=next(t for t in detail['tables'] if t['name'].startswith('Matching records'))
  assert source['total']==51 and len(source['rows'])==1
  assert detail['tables'][-1]['rows'][0][-1]==1020
  s.update_permissions(a,v.username,{'menu_1':False});v=s.login(v.username,'Test-viewer-password!123')
  with pytest.raises(AccessDenied):cols.handle(s,v,event)
  ai.assert_not_called()
