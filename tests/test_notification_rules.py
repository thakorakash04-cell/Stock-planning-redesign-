import copy,json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from unittest.mock import patch
import pytest
from stock_accounts import notification_rules as n
from stock_accounts.production import save as save_plan,read as production
from test_stock_assistant import accounts
from test_production import fixture as production_data

CFG={'RESET_FROM_EMAIL':'sender@example.invalid','RESEND_API_KEY':'mock'}
def test_description_terms_override_type_and_threshold():
 cfg={**n.DEFAULT,'packagingTypes':['ZPAC'],'threshold':1200}
 assert not n.packaging_match(cfg,'BOX','Carton box','ZPAC')
 assert n.packaging_match(cfg,'LBL','QA Labels','ZPAC')
 assert n.packaging_match(cfg,'BAG','Poly bags','ZPAC')
 assert n.packaging_match({**cfg,'includeMaterials':['BOX']},'BOX','Carton box','ZPAC')
 assert not n.packaging_match({**cfg,'includeMaterials':['BOX'],'excludeMaterials':['BOX']},'BOX','Label box','ZPAC')
 assert n.packaging_match({**cfg,'packagingWords':[]},'BOX','Carton box','ZPAC')
 assert not n.matches_saved_policy(cfg,'packaging',{'values':{'Material':'LBL','Description':'Label','Current Stock':1200}})
 assert n.matches_saved_policy(cfg,'packaging',{'values':{'Material':'LBL','Description':'Label','Current Stock':1199}})
 assert not n.matches_saved_policy(cfg,'qc',{'daysPending':6})
 assert n.matches_saved_policy(cfg,'qc',{'daysPending':7})

def test_legacy_qc_migration_once_and_pending_box_recheck(accounts):
 s,a,v=accounts;setup(s,a)
 legacy={k:v for k,v in n.DEFAULT.items() if k!='policyRevision'}
 legacy.update(qcDays=14,packagingTypes=['ZPAC'])
 with s.transaction() as db:
  s.run(db,"INSERT INTO stock_notice_config VALUES('current',?)",(n.dumps(legacy),))
  n.emit(s,db,'master:old','packaging','BOX',['Red'],n.record_payload('Packaging',{'Material':'BOX','Description':'Carton box','Material Type':'ZPAC','Current Stock':10}),at(22))
 assert n.info(s,a)['config']['qcDays']==7
 assert not any(row['values'].get('Material')=='BOX' for report in pending(s,a) for point in report['points'] if point['rule']=='packaging' for row in point['rows'])
 info=n.info(s,a);n.save_config(s,a,{'version':info['version'],'config':{**info['config'],'qcDays':14}})
 assert n.info(s,a)['config']['qcDays']==14

def test_background_and_login_share_batch_markers(accounts):
 s,a,v=accounts;setup(s,a);enable(s,a);sent=[]
 with patch.object(s,'get_dataset',side_effect=AssertionError('background workbook read')):
  n._dispatch(s,None,CFG,lambda *args:sent.append(args),now=at(23,9))
  assert sent
  count=len(sent)
  n.tick(s,v,CFG,lambda *args:sent.append(args),now=at(23,10))
  assert len(sent)==count

def at(day,hour=8,minute=0):return datetime(2026,10,day,hour,minute,tzinfo=n.IST).timestamp()
def dataset():
 d=production_data();d['productionSnapshotDate']='2026-10-20'
 d['tables']+=[{'name':'BOM','headers':['Material','Component','Component(text)','Material Type','Component unit','Source.Name'],
  'rows':[['A','LABEL','QA Label','ZPAC','EA','Red.xlsx'],['B','LABEL','QA Label','ZPAC','EA','Blue.xlsx'],['A','BOX','Carton box','ZPAC','EA','Red.xlsx']]},
  {'name':'Stock Data','headers':['Material','Unrestricted','In Quality Insp.'],'rows':[['LABEL',2000,500],['BOX',3000,0]]}]
 d['sheets']=[{'name':'Production Data','headers':['Year','Month','Batch','Material','Order','Quantity'],'rows':[[2026,'October','DONE','A',123,99]]},
  {'name':'Forecast Planning','headers':['Material','Name','Year','Month','Forecast','Transfer','Stock','Pending'],'rows':[['A','FG A',2026,'October',1000,200,100,700],['B','FG B',2026,'October',500,0,50,450]]},
  {'name':'Forecast Need to Order List','headers':['Component','Need to Order Quantity'],'rows':[['LABEL',500],['BOX',0]]}]
 return d
def setup(s,a):
 s.profile_email(a,'admin_user','admin@example.invalid');s.profile_email(a,'viewer_user','red@example.invalid')
 s.save_dataset(a,'master.xlsx',dataset())
 with s.transaction() as db:s.run(db,"UPDATE accounts SET allowed_segments=? WHERE username='viewer_user'",(json.dumps(['Red']),))
def enable(s,a):
 info=n.info(s,a);n.save_config(s,a,{'version':info['version'],'config':{**info['config'],'enabled':True}})
def pending(s,a,day=23):return n.info(s,a,preview=True,now=at(day))['reports']
def test_preview_packaging_threshold_shared_forecast_and_no_delivery(accounts):
 s,a,v=accounts;setup(s,a);p=pending(s,a)
 red=[r for r in p if r['recipient']=='red@example.invalid'];admin=[r for r in p if r['recipient']=='admin@example.invalid']
 assert any(x['rule']=='packaging' for r in red for x in r['points'])
 assert not any(x['rule']=='forecast' for r in red for x in r['points'])
 assert any(x['rule']=='forecast' for r in admin for x in r['points'])
 assert 'BOX' not in '\n'.join(r['body'] for r in p)
 assert n.tick(s,v,CFG,lambda *args:pytest.fail('preview sent'),now=at(23))['state']=='preview_only'
 assert pending(s,a)==p
def test_upload_delta_same_version_reorder_and_quantities(accounts):
 s,a,v=accounts;setup(s,a);d=dataset();d['sheets'][0]['rows'][0][-1]=100
 s.save_dataset(a,'changed.xlsx',d)
 assert not any(x['rule']=='production' for r in pending(s,a) for x in r['points'])
 d['sheets'][0]['rows'].append([2026,'October','NEW','A',124,50]);s.save_dataset(a,'new.xlsx',d)
 assert any(x['rule']=='production' for r in pending(s,a) for x in r['points'])
 with s.transaction() as db:before=s.run(db,'SELECT count(*) AS n FROM stock_notice_events').fetchone()['n']
 s.save_dataset(a,'same-content.xlsx',d)
 with s.transaction() as db:assert s.run(db,'SELECT count(*) AS n FROM stock_notice_events').fetchone()['n']==before
def test_daily_once_concurrent_cold_restart_without_workbook_reads(accounts):
 s,a,v=accounts;setup(s,a);enable(s,a);sent=[]
 with patch.object(s,'get_dataset',side_effect=AssertionError('daily workbook download')):
  with ThreadPoolExecutor(2) as pool:list(pool.map(lambda _:n.tick(s,v,CFG,lambda *args:sent.append(args),now=at(23)),range(2)))
  assert sent
  before=len(sent);n.tick(s,v,CFG,lambda *args:sent.append(args),now=at(23,18));assert len(sent)==before
  from stock_accounts.store import Store
  other=Store(s.url)
  with patch.object(other,'get_dataset',side_effect=AssertionError('restart download')):n.tick(other,v,CFG,lambda *args:sent.append(args),now=at(23,20))
  assert len(sent)==before
  n.tick(s,v,CFG,lambda *args:sent.append(args),now=at(24));assert len(sent)>before
 assert len({x[3] for x in sent})==len(sent)
def test_plan_history_previous_day_due_override_and_edit_details(accounts):
 s,a,v=accounts;setup(s,a);report=production(s,a);i=next(i for i in report['ongoing'] if i['row'][2]=='A')
 with patch('stock_accounts.production.time.time',return_value=at(22)):
  save_plan(s,a,{'kind':'ongoing','plan_id':i['id'],'revision':0,'version':report['version'],'value':{'quantity':42,'endDate':'2026-10-23'}})
  save_plan(s,a,{'kind':'upcoming','revision':0,'version':report['version'],'value':{'product':'A','description':'FG A','batch':'PLAN','quantity':10,'startDate':'2026-10-24','endDate':'2026-10-25','segment':'Red'}})
 assert not any(x['rule'] in ('plan','edit') for r in pending(s,a,22) for x in r['points'])
 p=pending(s,a,23);assert any(x['rule']=='edit' for r in p for x in r['points']);assert any(x['rule']=='plan' for r in p for x in r['points'])
 due=[x for r in p for x in r['points'] if x['rule']=='due'];assert any(row['values'].get('Expected FG Quantity')==42 for x in due for row in x['rows'])
def test_qc_14_day_reference_and_history(accounts):
 s,a,v=accounts;setup(s,a)
 qc=[x for r in pending(s,a) for x in r['points'] if x['rule']=='qc']
 assert qc and any(row['daysPending']>=14 and row['history'] for x in qc for row in x['rows'])
def test_sales_multiset_primary_bom_matching_and_secondary_independent(accounts):
 s,a,v=accounts;setup(s,a)
 value={'headers':['Material Code','Value','Segment'],'rows':[['A',100,'Red'],['BAD',200,'Red']],'segmentIndex':2}
 with s.transaction() as db:n.sales(s,db,'primary','v1',value,at(21),{'a'})
 value['rows']+=[['A',100,'Red'],['B',100,'Blue'],['BAD2',300,'Red']]
 with s.transaction() as db:n.sales(s,db,'primary','v2',value,at(22),{'a','b'})
 p=pending(s,a);texts='\n'.join(r['body'] for r in p if r['batch'].startswith('sales:'))
 assert 'BAD' not in texts and 'Primary Sales' in texts
 with s.transaction() as db:n.sales(s,db,'primary','v3',{**value,'rows':list(reversed(value['rows']))},at(22),{'a','b'})
 assert not any(r['batch']=='sales:primary:v3' for r in pending(s,a))
 with s.transaction() as db:
  n.sales(s,db,'secondary','s1',{'headers':value['headers'],'rows':[],'segmentIndex':2},at(21))
  n.sales(s,db,'secondary','s2',value,at(22))
 assert 'BAD2' in '\n'.join(r['body'] for r in pending(s,a) if r['batch']=='sales:secondary:s2')
def test_permissions_rechecked_and_transport_failure_not_retried(accounts):
 s,a,v=accounts;setup(s,a);enable(s,a);sent=[]
 def send(*args):
  sent.append(args)
  with s.transaction() as db:s.run(db,"UPDATE accounts SET active=0 WHERE username='viewer_user'")
  raise RuntimeError('unknown SMTP result')
 n.tick(s,a,CFG,send,now=at(23));before=len(sent)
 n.tick(s,a,CFG,send,now=at(23,12));assert len(sent)==before
 assert all(x[0]!='red@example.invalid' for x in sent)
 assert any(j['status']=='uncertain' for j in n.info(s,a)['jobs'])
def test_menu_denial_and_nonadmin_configuration(accounts):
 s,a,v=accounts;setup(s,a)
 with pytest.raises(PermissionError):n.info(s,v)
 with s.transaction() as db:s.run(db,"UPDATE accounts SET permissions=? WHERE username='viewer_user'",(json.dumps({'menu_0':False,'menu_3':False,'menu_5':False,'menu_11':False}),))
 assert not any(r['recipient']=='red@example.invalid' for r in pending(s,a))

def test_custom_worksheet_rules_share_daily_email(accounts):
 s,a,v=accounts;setup(s,a)
 s.portal_save(a,{'email_rules':[{'enabled':True,'recipient':'admin@example.invalid','section':'Forecast Need to Order List','column':'Need to Order Quantity','operator':'>','value':'0','message':'Existing shortage rule'}]})
 enable(s,a);p=pending(s,a)
 day=next(r for r in p if r['batch']=='daily:2026-10-23' and r['recipient']=='admin@example.invalid')
 assert any(x['rule']=='custom' for x in day['points']) and any(x['rule']=='due' for x in day['points'])
 sent=[];n.tick(s,a,CFG,lambda *args:sent.append(args),now=at(23))
 assert len([x for x in sent if x[0]=='admin@example.invalid' and 'Daily report' in x[1]])==1
 assert s.get_dataset(a)['filename']=='master.xlsx'

def test_cross_segment_edit_does_not_reveal_previous_product(accounts):
 s,a,v=accounts;setup(s,a);current=s.get_dataset(a)
 with s.transaction() as db:n.plan(s,db,current,'test','upcoming',{'materialCode':'B','segment':'Blue','batch':'private blue'},{'materialCode':'A','segment':'Red','batch':'new red'},'admin',at(22))
 assert not any(x['rule']=='edit' for r in pending(s,a) if r['recipient']=='red@example.invalid' for x in r['points'])

def test_early_login_does_not_consume_daily_batch_and_worker_login_share_claim(accounts):
 s,a,v=accounts;setup(s,a);enable(s,a);sent=[]
 with patch.object(s,'get_dataset',side_effect=AssertionError('daily workbook download')):
  early=n.tick(s,v,CFG,lambda *args:sent.append(args),now=at(23,2,29))
  assert early['state']=='waiting_for_schedule'
  assert not any('Daily report' in item[1] for item in sent)
  with s.transaction() as db:
   assert not s.run(db,"SELECT id FROM stock_notice_batches WHERE id='daily:2026-10-23'").fetchone()
   assert not s.run(db,"SELECT value FROM stock_notice_cursor WHERE id='history'").fetchone()
  with ThreadPoolExecutor(2) as pool:
   list(pool.map(lambda system:n._dispatch(s,None if system else v,CFG,lambda *args:sent.append(args),now=at(23,2,30)),[True,False]))
  count=len(sent)
  n.tick(s,v,CFG,lambda *args:sent.append(args),now=at(23,9))
  assert len(sent)==count
  reports=[item for item in sent if 'Daily report' in item[1]]
  assert reports and len({item[0] for item in reports})==len(reports)

def test_dispatch_queue_query_is_postgres_parameter_safe(accounts):
 from psycopg._queries import PostgresQuery
 from psycopg.adapt import Transformer
 s,a,v=accounts;setup(s,a);enable(s,a)
 original=s.run
 checked=[]
 def run(db,sql,args=()):
  if "SELECT id,batch,recipient FROM stock_notice_jobs" in sql:
   query=PostgresQuery(Transformer())
   query.convert(sql.replace('?', '%s'),args)
   assert args==('daily:%',1)
   assert b"daily:%" not in query.query
   checked.append(True)
  return original(db,sql,args)
 with patch.object(s,'run',side_effect=run):
  n._dispatch(s,None,CFG,lambda *args:None,now=at(23,9))
 assert checked
