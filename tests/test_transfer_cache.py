import copy,hashlib,json,unittest
from types import SimpleNamespace
from unittest.mock import patch
from stock_accounts.transfer_cache import read_rows
class Cursor:
 def __init__(self,value):self.value=value
 def fetchone(self):return self.value
 def fetchall(self):return self.value
class Database:
 sqlite=False
 def __init__(self):self.rows=[{'id':'a','payload':'x'*1000000}];self.bytes=0;self.full_reads=0;self.fail=False;self.race=False
 def run(self,db,sql,args=()):
  if self.fail:raise ConnectionError('offline')
  if sql.startswith('SELECT md5('):
   sig=hashlib.md5(json.dumps(self.rows,sort_keys=True).encode()).hexdigest();self.bytes+=32;return Cursor({'signature':sig})
  self.full_reads+=1;self.bytes+=len(json.dumps(self.rows));result=copy.deepcopy(self.rows)
  if self.race:self.rows[0]['payload']='new concurrent data';self.race=False
  return Cursor({'cached_rows':result,'signature':hashlib.md5(json.dumps(result,sort_keys=True).encode()).hexdigest()})
class TransferTests(unittest.TestCase):
 def test_warm_reads_transfer_only_fingerprint_and_cannot_mutate_cache(self):
  db=Database();sql='SELECT id,payload FROM example ORDER BY id';read_rows(db,None,sql);cold=db.bytes;self.assertGreater(cold,1000000)
  value=read_rows(db,None,sql);value[0]['payload']='client mutation'
  for _ in range(99):self.assertEqual(read_rows(db,None,sql)[0]['payload'],'x'*1000000)
  self.assertEqual(db.full_reads,1);self.assertEqual(db.bytes-cold,3200)
 def test_changed_content_reloads_and_failures_never_serve_stale_data(self):
  db=Database();sql='SELECT * FROM example';read_rows(db,None,sql);db.rows[0]['payload']='updated';self.assertEqual(read_rows(db,None,sql)[0]['payload'],'updated');self.assertEqual(db.full_reads,2)
  db.fail=True
  with self.assertRaises(ConnectionError):read_rows(db,None,sql)
 def test_concurrent_change_does_not_poison_cache(self):
  db=Database();db.race=True;sql='SELECT * FROM example';read_rows(db,None,sql)
  self.assertEqual(read_rows(db,None,sql)[0]['payload'],'new concurrent data');self.assertEqual(db.full_reads,2)
 def test_store_isolation_and_entry_bound(self):
  a=Database();b=Database();b.rows[0]['payload']='other database';read_rows(a,None,'SELECT * FROM example');self.assertEqual(read_rows(b,None,'SELECT * FROM example')[0]['payload'],'other database')
  for i in range(20):read_rows(a,None,'SELECT * FROM example WHERE id=?',(i,))
  self.assertLessEqual(len(a._transfer_rows_cache),16)
