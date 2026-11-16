"""Regress the notification advisory/DDL lock inversion seen in live logs."""
from contextlib import contextmanager
from unittest.mock import patch
from stock_accounts import notification_rules as rules,scheduled_delivery as schedule

class Database:
    sqlite=False
    account_table='accounts'
    url='test-only'
    def __init__(self,acquired=True):self.sql=[];self.acquired=acquired
    @contextmanager
    def transaction(self):yield self
    def run(self,db,sql,args=()):self.sql.append(sql);return self
    def fetchone(self):return {'acquired':self.acquired}

def test_notification_schema_locks_before_any_ddl():
    db=Database();rules.schema(db,db)
    assert 'pg_advisory_xact_lock' in db.sql[0]
    assert any(sql.startswith('CREATE TABLE') for sql in db.sql[1:])

def test_custom_schedule_schema_uses_same_lock_order():
    db=Database();schedule.schema(db,db)
    assert 'pg_advisory_xact_lock' in db.sql[0]
    assert db.sql[1].startswith('CREATE TABLE')

def test_busy_notification_worker_does_not_wait_or_consume_due_batch():
    db=Database(acquired=False);sent=[]
    result=rules._dispatch(db,None,{'RESET_FROM_EMAIL':'test@example.invalid','RESEND_API_KEY':'mock'},lambda *a:sent.append(a))
    assert result=={'sent':0,'state':'busy'}
    assert db.sql[:2]==["SET LOCAL lock_timeout = '2s'","SET LOCAL statement_timeout = '8s'"]
    assert 'pg_try_advisory_xact_lock' in db.sql[2]
    assert len(db.sql)==3 and not sent

def test_repeated_visits_share_one_notification_scan():
    import streamlit as st
    from stock_accounts import portal_ui
    schedule._scan_times.clear()
    with patch.object(st,'session_state',{'actor':object()}),patch.object(portal_ui,'config',return_value={}),patch.object(rules,'tick',return_value={'state':'checked'}) as tick:
        schedule.mount(Database());schedule.mount(Database())
        tick.assert_called_once()
    schedule._scan_times.clear()
