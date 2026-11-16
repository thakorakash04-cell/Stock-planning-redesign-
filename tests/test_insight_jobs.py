from unittest.mock import patch
import copy
import pytest
import streamlit as st
from test_stock_assistant import accounts
from stock_accounts.workspace_insights import handle_request
from stock_accounts.insight_jobs import compact_context

TABLE={'id':'T1','name':'Stock','headers':['Material','Qty'],'rows':[['A',3],['B',9]]}
VIEW={'view':0,'title':'Stock overview','table':'Stock'}
PLAN={'sections':[{'view':0,'kpis':[{'title':'Total quantity','value':'sum(Qty)','query':{'table':'T1','metrics':[{'column':'Qty','op':'sum'}],'limit':1}}],'charts':[{'title':'Quantity','label':'Material','value':'Qty','query':{'table':'T1','columns':['Material','Qty'],'limit':10}}]}]}

def start(store,actor):
 version=handle_request(store,actor,{'action':'ai_status'})['version']
 event={'action':'generate_insights','progressive':True,'request_id':'test-request','version':version,'consent':True}
 def prepare(store,actor,tables,views,current,data):
  from stock_accounts.planning_assistant import knowledge
  return [copy.deepcopy(TABLE)],[copy.deepcopy(VIEW)],{'knowledge':knowledge(),'limitations':[]}
 with patch('stock_accounts.insight_attention.prepare',side_effect=prepare),patch('stock_accounts.insight_dashboard.extend_sources',side_effect=lambda store,actor,t,v,c,current:(t,v,c)),patch('stock_accounts.insights.generate') as provider:
  result=handle_request(store,actor,event)
  assert provider.call_count==0
 assert result['pending'] and result['step']==0 and result['report'] is None
 return event,result

def advance(store,actor,event,response):
 return handle_request(store,actor,{**event,'job_id':response['job_id'],'step':response['step']})

def test_each_phase_is_bounded_resumable_and_replays_without_provider_calls(accounts):
 store,admin,_=accounts;event,initial=start(store,admin)
 with patch('stock_accounts.insight_dashboard.connected_views',side_effect=lambda t,v,c,**kw:(t,v,c)) as connect:
  connected=advance(store,admin,event,initial)
  replay=advance(store,admin,event,initial)
  assert connected==replay and connect.call_count==1
 with patch('stock_accounts.insights.settings',return_value=('key','model')),patch('stock_accounts.insights.generate',return_value=copy.deepcopy(PLAN)) as provider:
  partial=advance(store,admin,event,connected)
  assert provider.call_count==1,'Chart phase must never also request narrative generation'
 assert partial['pending'] and partial['report']['sections'][0]['kpis'][0]['value']==12
 source=partial['report']['sections'][0]['charts'][0]['evidence']['source_id']
 assert handle_request(store,admin,{'action':'insight_records','version':event['version'],'source_id':source})['total']==2
 narrative={'overview':'Business brief','sections':[{'view':0,'findings':['Qty is recorded.'],'actions':['Verify demand.']}]}
 with patch('stock_accounts.insights.settings',return_value=('key','model')),patch('stock_accounts.insights.generate',return_value=narrative) as provider:
  completed=advance(store,admin,event,partial)
  replay=advance(store,admin,event,partial)
  assert provider.call_count==1 and replay==completed
 assert not completed['pending'] and completed['progress']['percent']==100
 assert completed['report']['sections'][0]['review_mode']=='ai'
 assert completed['report']['sections'][0]['charts'][0]['evidence']['source_id']==source
 assert len(completed['report']['sections'])==1


def test_failed_phase_can_resume_without_restarting_or_losing_prior_progress(accounts):
 store,admin,_=accounts;event,initial=start(store,admin)
 with patch('stock_accounts.insight_dashboard.connected_views',side_effect=ValueError('Transient failure')):
  with pytest.raises(ValueError,match='Transient'):advance(store,admin,event,initial)
 with patch('stock_accounts.insight_dashboard.connected_views',side_effect=lambda t,v,c,**kw:(t,v,c)):
  resumed=advance(store,admin,event,initial)
 assert resumed['step']==1 and resumed['job_id']==initial['job_id']
 # Replaying initial creation returns the same job instead of preparing again.
 with patch('stock_accounts.insight_attention.prepare') as prepare:
  again=handle_request(store,admin,event)
  assert again['job_id']==initial['job_id'] and again['step']==1
  prepare.assert_not_called()


def test_resume_rechecks_live_permissions_consent_and_data_versions(accounts):
 store,admin,viewer=accounts;event,initial=start(store,viewer)
 with pytest.raises(ValueError,match='sharing'):advance(store,viewer,{**event,'consent':False},initial)
 with pytest.raises(ValueError,match='changed'):advance(store,viewer,{**event,'version':'old'},initial)
 with pytest.raises(PermissionError):advance(store,admin,event,initial)
 store.update_permissions(admin,'viewer_user',{'menu_8':False})
 viewer=store.login('viewer_user','Test-viewer-password!123')
 with pytest.raises(PermissionError):advance(store,viewer,event,initial)


def test_compact_context_retains_rules_and_drops_implementation_payloads():
 context={'knowledge':{'revision':'r','rules':'Keep source units','release_notes':'x'*20000,'deployed_features':[{'implementation':'x'*100000}]},'attention':[{'view':0},{'view':1}],'priority_charts':{0:['a'],1:['b']}}
 compact=compact_context(context,[VIEW])
 assert compact['knowledge']['rules']=='Keep source units'
 assert 'deployed_features' not in compact['knowledge'] and len(compact['knowledge']['release_notes'])==6000
 assert compact['attention']==[{'view':0}] and compact['priority_charts']=={0:['a']}


def test_completion_save_failure_resumes_without_repeating_ai(accounts):
 store,admin,_=accounts;event,initial=start(store,admin)
 with patch('stock_accounts.insight_dashboard.connected_views',side_effect=lambda t,v,c,**kw:(t,v,c)):
  connected=advance(store,admin,event,initial)
 with patch('stock_accounts.insights.settings',return_value=('key','model')),patch('stock_accounts.insights.generate',return_value=copy.deepcopy(PLAN)):
  partial=advance(store,admin,event,connected)
 with patch('stock_accounts.insights.review_sections',return_value={}) as review,patch('stock_accounts.insight_memory.save',side_effect=ValueError('Temporary save failure')):
  with pytest.raises(ValueError,match='Temporary'):advance(store,admin,event,partial)
  assert review.call_count==1
 with patch('stock_accounts.insights.generate') as provider:
  completed=advance(store,admin,event,partial)
  assert not completed['pending'] and completed['step']==3
  provider.assert_not_called()


def test_partial_sections_and_continuation_restore_after_a_new_login_without_ai(accounts):
 from stock_accounts.store import Store
 store,admin,_=accounts;event,initial=start(store,admin)
 with patch('stock_accounts.insight_dashboard.connected_views',side_effect=lambda t,v,c,**kw:(t,v,c)):
  connected=advance(store,admin,event,initial)
 with patch('stock_accounts.insights.settings',return_value=('key','model')),patch('stock_accounts.insights.generate',return_value=copy.deepcopy(PLAN)):
  partial=advance(store,admin,event,connected)
 original_source=partial['report']['sections'][0]['charts'][0]['evidence']['source_id']
 st.session_state.clear();store=Store(store.url);admin=store.login('admin_user','Test-admin-password!123')
 with patch('stock_accounts.insights.generate') as provider:
  status=handle_request(store,admin,{'action':'ai_status','load_saved_insights':True})
  provider.assert_not_called()
 restored=status['active_analysis']
 assert status['saved_report'] is None and restored['pending'] and restored['step']==partial['step']
 assert restored['report']['sections'][0]['kpis'][0]['value']==12
 source=restored['report']['sections'][0]['charts'][0]['evidence']['source_id']
 assert source!=original_source
 assert handle_request(store,admin,{'action':'insight_records','version':event['version'],'source_id':source,'mark':1})['records'][0]['Material']=='B'
 with patch('stock_accounts.insights.review_sections',return_value={'overview':'Finished after login'}) as review:
  completed=advance(store,admin,event,restored)
  assert review.call_count==1
 assert not completed['pending']
 st.session_state.clear()
 status=handle_request(store,admin,{'action':'ai_status','load_saved_insights':True})
 assert status['active_analysis'] is None and status['saved_report']['sections'][0]['charts']


def test_checkpoint_failure_retries_publication_without_repeating_chart_ai(accounts):
 store,admin,_=accounts;event,initial=start(store,admin)
 with patch('stock_accounts.insight_dashboard.connected_views',side_effect=lambda t,v,c,**kw:(t,v,c)):
  connected=advance(store,admin,event,initial)
 with patch('stock_accounts.insights.settings',return_value=('key','model')),patch('stock_accounts.insights.generate',return_value=copy.deepcopy(PLAN)) as provider,patch('stock_accounts.insight_memory.checkpoint',side_effect=ValueError('Temporary checkpoint failure')):
  with pytest.raises(ValueError,match='checkpoint'):advance(store,admin,event,connected)
  assert provider.call_count==1
 with patch('stock_accounts.insights.generate') as provider:
  resumed=advance(store,admin,event,connected)
  provider.assert_not_called()
 assert resumed['step']==2 and len(resumed['report']['sections'])==1


def test_checkpoint_never_restores_into_a_different_access_scope_or_new_workbook(accounts):
 store,admin,viewer=accounts;event,initial=start(store,admin)
 with patch('stock_accounts.insight_dashboard.connected_views',side_effect=lambda t,v,c,**kw:(t,v,c)):
  connected=advance(store,admin,event,initial)
 with patch('stock_accounts.insights.settings',return_value=('key','model')),patch('stock_accounts.insights.generate',return_value=copy.deepcopy(PLAN)):
  advance(store,admin,event,connected)
 st.session_state.clear()
 assert handle_request(store,viewer,{'action':'ai_status','load_saved_insights':True})['active_analysis'] is None
 store.save_dataset(admin,'new.xlsx',{'sheets':[{'name':'Stock','headers':['Material','Qty'],'rows':[['C',10]]}],'tables':[]})
 assert handle_request(store,admin,{'action':'ai_status','load_saved_insights':True})['active_analysis'] is None


def test_reviewed_batch_restores_before_next_batch_without_displacing_completed_report(accounts):
 from test_insight_memory import generate as completed_report
 store,admin,_=accounts;previous=completed_report(store,admin)
 event,initial=start(store,admin)
 job=st.session_state['_stock_insight_jobs'][initial['job_id']]
 job['views']=[{**copy.deepcopy(VIEW),'view':i} for i in range(3)]
 with patch('stock_accounts.insight_dashboard.connected_views',side_effect=lambda t,v,c,**kw:(t,v,c)):
  connected=advance(store,admin,event,initial)
 first={'sections':[{**copy.deepcopy(PLAN['sections'][0]),'view':i} for i in (0,1)]}
 with patch('stock_accounts.insights.settings',return_value=('key','model')),patch('stock_accounts.insights.generate',return_value=first):
  partial=advance(store,admin,event,connected)
 with patch('stock_accounts.insights.review_sections',return_value={'overview':'First saved batch'}):
  reviewed=advance(store,admin,event,partial)
 assert reviewed['pending'] and len(reviewed['report']['sections'])==2
 st.session_state.clear()
 status=handle_request(store,admin,{'action':'ai_status','load_saved_insights':True})
 assert status['saved_report']['cache_generation']==previous['cache_generation']
 restored=status['active_analysis']
 assert len(restored['report']['sections'])==2 and restored['report']['overview']=='First saved batch'
 second={'sections':[{**copy.deepcopy(PLAN['sections'][0]),'view':2}]}
 with patch('stock_accounts.insights.settings',return_value=('key','model')),patch('stock_accounts.insights.generate',return_value=second) as provider:
  next_batch=advance(store,admin,event,restored)
  assert provider.call_count==1
 with patch('stock_accounts.insights.review_sections',return_value={'overview':'Second saved batch'}):
  finished=advance(store,admin,event,next_batch)
 assert not finished['pending'] and {s['view'] for s in finished['report']['sections']}=={0,1,2}
