import json
from unittest.mock import patch
from test_stock_assistant import accounts
from test_notification_rules import setup,enable,at,CFG
from stock_accounts import notification_rules as n
from stock_accounts.pending_sales import pack

def seed(s):
 with s.transaction() as db:
  n.schema(s,db)
  s.run(db,"INSERT INTO stock_open_orders VALUES('current','orders.xlsx','o1',1,'admin_user',?)",(pack({'headers':[],'rows':[]}),))

def test_complete_scoped_daily_digest_once_and_live_rights(accounts):
 s,a,v=accounts;setup(s,a);seed(s);enable(s,a)
 def build(data,orders,identity):
  code='RED' if identity['allowedSegments']==['Red'] else 'ALL'
  return {'headers':['Product Code','Quantity','Suggestions'],'rows':[[code+str(i),i,'Forecast demand'] for i in range(75)],'notes':[],'warnings':[]}
 sent=[]
 with patch('stock_accounts.pending_sales.build',side_effect=build) as calculate:
  previews=n.info(s,a,preview=True,now=at(23,2,30))['reports']
  red=next(p for p in previews if p['recipient']=='red@example.invalid' and p['batch'].startswith('daily:'))
  assert 'RED74' in red['body'] and 'ALL74' not in red['body']
  point=next(p for p in red['points'] if p['rule']=='batch_required')
  formatted=n.format_report([point],'daily:test')
  assert 'RED74' in formatted and 'RED74' in formatted.html
  assert 'Showing 50' not in formatted
  n._dispatch(s,None,CFG,lambda *args:sent.append(args),now=at(23,2,29))
  assert not any("New Production Batch Required" in str(m[2]) for m in sent)
  sent.clear()
  n._dispatch(s,None,CFG,lambda *args:sent.append(args),now=at(23,2,30))
  assert len(sent)==2 and all('74' in str(m[2]) for m in sent)
  n._dispatch(s,None,CFG,lambda *args:sent.append(args),now=at(23,4))
  assert len(sent)==2 and calculate.call_count==2
  with s.transaction() as db:s.run(db,"UPDATE accounts SET permissions=? WHERE username='viewer_user'",(json.dumps({'menu_13':False}),))
  next_day=n.info(s,a,preview=True,now=at(24))['reports']
  assert not any(p['rule']=='batch_required' for r in next_day if r['recipient']=='red@example.invalid' for p in r['points'])

def test_unselected_rule_does_not_read_sources(accounts):
 s,a,v=accounts;setup(s,a);seed(s)
 info=n.info(s,a);n.save_config(s,a,{'version':info['version'],'config':{**info['config'],'rules':['due']}})
 with patch('stock_accounts.pending_sales.build',side_effect=AssertionError('disabled rule calculated')):
  assert not any(p['rule']=='batch_required' for r in n.info(s,a,preview=True)['reports'] for p in r['points'])
