from datetime import date
from unittest.mock import patch
from stock_accounts.source_freshness import table_summary,workbook_summary,pnl_summary,cached,uploaded
from test_stock_assistant import accounts

def table(name,headers,rows):return {'name':name,'headers':headers,'rows':rows}

def test_observed_dates_and_no_forecast_calendar_or_planned_date_inflation():
 d={'tables':[table('Material Document List',['Posting Date'],[['2026-11-04'],['2026-11-15'],['bad']]),table('Order List',['Document Date'],[['2026-11-12']]),table('Production Order Details',['Basic finish date'],[['2027-01-01']]),table('Calendar',['Date'],[['2100-01-01']])], 'sheets':[table('Forecast Planning',['Date'],[['2029-12-01']])]}
 assert workbook_summary(d)=={'dataUpTo':'2026-11-15','dataDateBasis':'Material Document List · Posting Date'}
 assert table_summary(table('Primary Sales',['Billing Date','Delivery Date'],[['2026-11-10','2027-01-01'],['15/11/2026',None]]))['dataUpTo']=='2026-11-15'
 assert table_summary(table('Orders',['Document Date'],[[date(2026,11,1)]]))['dataUpTo']=='2026-11-01'
 assert table_summary(table('Stock',['Current Stock'],[[45000]]))['dataUpTo'] is None
 assert table_summary(table('Pivot',['Attribute'],[['Total Forecast'],[50000]]))['dataUpTo'] is None


def test_pnl_uses_months_present_in_file_and_salary_does_not_use_employment_dates():
 assert pnl_summary({'end':'2027-03-31','production':[{'month':'2026-04-01'},{'month':'2026-11-01'}]},'master')['dataUpTo']=='2026-11'
 assert pnl_summary({'employees':[{'join':'2020-01-01','leave':'2030-01-01'}]},'salary')['dataUpTo'] is None


def test_metadata_cache_restores_without_reading_payload_and_refreshes_by_version(accounts):
 store,admin,viewer=accounts
 def load():return {'dataUpTo':'2026-11-15','dataDateBasis':'Posting Date'}
 assert cached(store,admin,'master','v1',load)['dataUpTo']=='2026-11-15'
 with patch('stock_accounts.source_freshness.workbook_summary',side_effect=AssertionError('No rescans')):
  assert cached(store,admin,'master','v1',lambda:(_ for _ in ()).throw(AssertionError('Must restore')))['dataUpTo']=='2026-11-15'
 assert cached(store,admin,'master','v2',lambda:{'dataUpTo':'2026-11-16'})['dataUpTo']=='2026-11-16'


def test_file_upload_time_stays_distinct_from_content_date(accounts):
 store,admin,_=accounts
 store.save_dataset(admin,'master.xlsx',{'sheets':[],'tables':[table('Material Document List',['Posting Date'],[['2026-11-04']])]})
 current=store.get_dataset(admin);meta={'filename':current['filename'],'version':current['version'],'updated_at':current['updated_at']}
 result=uploaded(store,admin,'master',meta)
 assert result['dataUpTo']=='2026-11-04' and result['updated_at']==current['updated_at']


def test_same_content_reupload_refreshes_sales_timestamp_without_inventing_content_date(accounts):
 from stock_accounts import sales
 store,admin,_=accounts
 value={'headers':['Material','Billing Date','Segment'],'rows':[['A','2026-11-04','Care']],'segmentIndex':2,'unmapped':0}
 with patch.object(sales,'parse',return_value=value):sales.save(store,admin,{'kind':'secondary','filename':'Sales.xlsx','content':'ZmlsZQ==','sheet':'Sales','expected':None})
 first=sales.read(store,admin,{'kind':'secondary'})
 assert first['source']['dataUpTo']=='2026-11-04'
 with store.transaction() as db:store.run(db,"UPDATE stock_sales_documents SET updated_at=updated_at+100,filename='Reuploaded.xlsx' WHERE kind='secondary'")
 second=sales.read(store,admin,{'kind':'secondary','knownVersion':first['version']})
 assert not second.get('notModified') and second['source']['filename']=='Reuploaded.xlsx'
 assert second['source']['updated_at']>first['source']['updated_at'] and second['source']['dataUpTo']=='2026-11-04'
