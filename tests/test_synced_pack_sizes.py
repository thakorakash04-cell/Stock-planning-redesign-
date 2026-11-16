import copy
from test_stock_assistant import accounts
from stock_accounts.product_catalog import publish,read,sku_metadata,enrich_display

def products(pack=10):
 return [{'id':'p1','name':'Product','division':'A','sections':[{'kind':'variants','rows':[{'code':'FG1','pack':pack,'uom':'EA'}],'hasSfg':True,'sfgRows':[{'code':'SFG1','pack':5,'uom':'KG'}]}]}]

def test_publish_sync_metadata_and_history_change_only(accounts):
 s,a,v=accounts
 publish(s,a,products(),'https://product.test')
 first=read(s,a);assert sku_metadata(first)['fg1']=={'packSize':10,'unit':'EA'}
 assert sku_metadata(first)['sfg1']['packSize']==5
 with s.transaction() as db:
  before=s.run(db,'SELECT count(*) AS n FROM portal_history').fetchone()['n']
 publish(s,a,products(),'https://product.test')
 with s.transaction() as db:assert s.run(db,'SELECT count(*) AS n FROM portal_history').fetchone()['n']==before
 publish(s,a,products(20),'https://product.test')
 second=read(s,a);assert first['version']!=second['version']
 assert sku_metadata(second)['fg1']['packSize']==20
 with s.transaction() as db:assert s.run(db,'SELECT count(*) AS n FROM portal_history').fetchone()['n']==before+1

def test_synced_values_override_cached_workbook_without_mutation():
 payload={'sheets':[{'name':'BOM Cost','headers':['Material','Base unit of measure','Pack Size','Std DP'],'rows':[['FG1','BOX',99,7],['FG2','EA',30,8]]}]}
 pending={'result':{'visibleStock':['fg1','fg2'],'productDetails':{'fg1':{'unit':'BOX','packSize':99},'fg2':{'unit':'EA','packSize':30}}}}
 original=copy.deepcopy((payload,pending))
 catalog={'products':[{'skuMetadata':[{'code':'FG1','pack':10,'uom':'EA'}]}]}
 result,demand=enrich_display(payload,pending,catalog)
 assert result['sheets'][0]['rows']==[['FG1','EA',10,7],['FG2','EA',30,8]]
 assert demand['result']['productDetails']['fg1']=={'unit':'EA','packSize':10}
 assert (payload,pending)==original
 assert sku_metadata({'products':[{'skuMetadata':[{'code':'FG1','pack':10},{'code':'FG1','pack':20}]}]})['fg1']['packSize'] is None


def test_unchanged_publish_uses_only_version_not_catalog_payload(accounts):
 s,a,v=accounts;publish(s,a,products(),'https://product.test')
 from unittest.mock import patch
 original=s.run;queries=[]
 def tracked(db,sql,args=()):
  queries.append(sql)
  return original(db,sql,args)
 with patch.object(s,'run',side_effect=tracked):publish(s,a,products(),'https://product.test')
 assert any(sql.startswith('SELECT version FROM stock_product_catalog') for sql in queries)
 assert not any('payload FROM stock_product_catalog' in sql for sql in queries)
 assert not any('FROM stock_product_snapshots' in sql for sql in queries)
 assert not any(sql.startswith(('INSERT','UPDATE','DELETE')) for sql in queries)
