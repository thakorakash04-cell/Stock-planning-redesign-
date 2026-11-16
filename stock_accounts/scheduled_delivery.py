"""Durable daily mail with IST catch-up; invoked by active Streamlit fragments only.

No background keep-alive is used. Each tick groups the latest due slot, skips old
backlogs, and atomically claims recipient jobs across sessions/replicas. SMTP
outcomes that may already have been accepted are not retried automatically.
"""
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from importlib import import_module
import hashlib,json,logging,re,time,uuid,threading
_scan_lock=threading.Lock()
_scan_times={}

ACTIVITY_REVISION=8
IST=ZoneInfo('Asia/Kolkata')
DEFAULT_SCHEDULE={'enabled':True,'time':'09:00'}

class DeliveryDeferred(Exception):
    """Transport definitively did not submit the message; a retry is safe."""
class DeliveryUncertain(Exception):
    """The provider may already have accepted the message; do not resend."""

def configured(cfg):
    return bool((cfg.get('RESET_FROM_EMAIL') or cfg.get('ALERT_FROM_EMAIL')) and (cfg.get('RESEND_API_KEY') or all(cfg.get(k) for k in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD'))))

def latest_slot(now,at):
    if not isinstance(at,str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',at):raise ValueError('Use a daily time in HH:MM format (IST).')
    clock=datetime.fromtimestamp(now,IST);hour,minute=map(int,at.split(':'));due=clock.replace(hour=hour,minute=minute,second=0,microsecond=0)
    if due>clock:due-=timedelta(days=1)
    return due.isoformat(),due.timestamp()

def tables(store):
    prefix=store.account_table
    if prefix not in ('accounts','meddevice_accounts'):raise ValueError('Unsupported portal account table.')
    return prefix+'_mail_state',prefix+'_mail_outbox'

def schema(store,db):
    lock(store,db)
    state,jobs=tables(store)
    store.run(db,f'CREATE TABLE IF NOT EXISTS {state} (id TEXT PRIMARY KEY,last_slot TEXT NOT NULL,last_scan DOUBLE PRECISION NOT NULL,error TEXT NOT NULL)')
    store.run(db,f'CREATE TABLE IF NOT EXISTS {jobs} (id TEXT PRIMARY KEY,slot TEXT NOT NULL,recipient TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,claim TEXT NOT NULL,created_at DOUBLE PRECISION NOT NULL,lease_until DOUBLE PRECISION NOT NULL,attempts INTEGER NOT NULL,next_attempt DOUBLE PRECISION NOT NULL,error TEXT NOT NULL)')
    return state,jobs

def lock(store,db):
    if not store.sqlite:store.run(db,'SELECT pg_advisory_xact_lock(hashtext(?))',('schedule-mail:'+store.account_table,))

def internal_actor(store):
    # Server-only identity; never returned to the browser or exposed as an RPC.
    # Every subsequent store operation revalidates its current admin role/version.
    with store.transaction() as db:
        row=store.run(db,f"SELECT username,session_version FROM {store.account_table} WHERE role='admin' AND active=1 ORDER BY username LIMIT 1").fetchone()
    if not row:return None
    from daily_sessions import make_store_actor
    return make_store_actor(store,row['username'],row['session_version'],'scheduled-email')

def rules_key(settings):
    return hashlib.sha256(json.dumps({'rules':settings.get('email_rules',[]),'schedule':{**DEFAULT_SCHEDULE,**settings.get('email_schedule',{})}},sort_keys=True,separators=(',',':')).encode()).hexdigest()

def tick(store,configuration,send,now=None):
    """Check one active tick. send(to, subject, body, idempotency_key) is injectable."""
    now=time.time() if now is None else now
    if not configured(configuration):return {'sent':0,'state':'not_configured'}
    actor=internal_actor(store)
    if not actor:return {'sent':0,'state':'no_administrator'}
    settings=store.portal_read(actor);schedule={**DEFAULT_SCHEDULE,**settings.get('email_schedule',{})}
    if schedule['enabled'] is not True:return {'sent':0,'state':'paused'}
    slot,due_at=latest_slot(now,schedule['time']);key=rules_key(settings)
    with store.transaction() as db:
        state,jobs=schema(store,db)
        row=store.run(db,f"SELECT * FROM {state} WHERE id='daily'").fetchone()
        if row and now-row['last_scan']<60:return {'sent':0,'state':'throttled'}
        last_slot=row['last_slot'] if row else ''
        store.run(db,f"INSERT INTO {state} VALUES('daily',?,?,?) ON CONFLICT(id) DO UPDATE SET last_scan=excluded.last_scan",(last_slot,now,''))
        # A crashed SMTP submission can already have delivered. Never blindly retry it.
        store.run(db,f"UPDATE {jobs} SET status='uncertain',error='Previous delivery outcome is uncertain; inspect provider logs before resending.' WHERE status='sending' AND lease_until<?",(now,))
    if last_slot<slot and any(r.get('enabled') for r in settings.get('email_rules',[])):
        current=store.get_dataset(actor)
        if not current:return {'sent':0,'state':'no_saved_dataset'}
        from . import portal_alerts
        if getattr(portal_alerts,'EMAIL_FORMAT_REVISION',0)!=1:
            import importlib
            portal_alerts=importlib.reload(portal_alerts)
        grouped=portal_alerts.grouped
        from .recipient_scope import allowed,version as recipient_scope
        try:messages=grouped(allowed(store,settings.get('email_rules',[])),__import__(__package__+'.portal_console',fromlist=['source_tables']).source_tables(current),store=store)
        except ValueError:
            with store.transaction() as db:store.run(db,f"UPDATE {state} SET error=? WHERE id='daily'",('An email rule no longer matches the saved section/column. Review Email management.',))
            return {'sent':0,'state':'invalid_rules'}
        scopes={email:recipient_scope(store,email) for email in messages}
        with store.transaction() as db:
            store.require(db,actor,admin=True);lock(store,db)
            current_slot=store.run(db,f"SELECT last_slot FROM {state} WHERE id='daily'").fetchone()['last_slot']
            # A slow peer may have finished this slot while we built the report.
            if current_slot<slot:
                store.run(db,f"UPDATE {jobs} SET status='superseded',error='Replaced by the newest due report.' WHERE status IN ('queued','retry') AND slot<?",(slot,))
                for recipient,body in messages.items():
                    if store.run(db,f"SELECT id FROM {jobs} WHERE slot=? AND recipient=? AND status IN ('sent','uncertain','sending')",(slot,recipient)).fetchone():continue
                    identifier=hashlib.sha256((store.account_table+'|'+slot+'|'+recipient+'|'+key+'|'+current['version']+'|'+scopes[recipient]).encode()).hexdigest()
                    text=f"Scheduled report · {slot} (IST)\nSource: {current['filename']}\nThe latest saved data is used; missed days are consolidated.\n\n{body}"
                    sections=getattr(body,'sections',None)
                    payload=json.dumps({'body':('Scheduled report · '+slot+' (IST) · Source: '+current['filename']) if sections else text,'sections':sections,'rules_key':key,'version':current['version'],'scope':scopes[recipient]})
                    store.run(db,f"INSERT INTO {jobs} VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING",(identifier,slot,recipient,payload,'queued','',now,0,0,now,''))
                store.run(db,f"UPDATE {state} SET last_slot=?,error='' WHERE id='daily'",(slot,))
                store.history_write(db,actor,'Scheduled email batch',None,{'slot':slot,'recipients':len(messages),'source':current['filename']})
    with store.transaction() as db:
        pending=[dict(r) for r in store.run(db,f"SELECT * FROM {jobs} WHERE status IN ('queued','retry') AND next_attempt<=? ORDER BY created_at,id LIMIT 20",(now,)).fetchall()]
    sent=0
    for job in pending:
        payload=json.loads(job['payload']);claim=uuid.uuid4().hex
        from .recipient_scope import version as recipient_scope
        fresh=store.portal_read(actor);current=store.get_dataset(actor)
        if recipient_scope(store,job['recipient'])!=payload.get('scope') or rules_key(fresh)!=payload['rules_key'] or not current or current['version']!=payload['version']:
            with store.transaction() as db:
                store.run(db,f"UPDATE {jobs} SET status='cancelled',error='Rules or saved data changed before delivery.' WHERE id=? AND status IN ('queued','retry')",(job['id'],))
                # Rebuild the latest slot on the next active tick, rather than email stale data.
                store.run(db,f"UPDATE {state} SET last_slot='' WHERE id='daily'")
            continue
        with store.transaction() as db:
            store.require(db,actor,admin=True)
            result=store.run(db,f"UPDATE {jobs} SET status='sending',claim=?,lease_until=?,attempts=attempts+1 WHERE id=? AND status IN ('queued','retry')",(claim,now+300,job['id']))
            if result.rowcount!=1:continue
        status='sent';error='';retry_at=now
        try:
            message=payload['body']
            if payload.get('sections'):
                from .portal_alerts import formatted_sections
                message=formatted_sections(payload['sections'],payload['body'],True)
            send(job['recipient'],'Workspace scheduled alert report',message,job['id']);sent+=1
        except DeliveryDeferred:
            status='retry' if job['attempts']<4 and now-job['created_at']<23*3600 else 'failed'
            retry_at=now+min(3600,60*(2**job['attempts']));error='Delivery could not be submitted. Will retry while active.' if status=='retry' else 'Delivery retries exhausted. Check sender settings.'
        except Exception:
            status='uncertain';error='Delivery failed or may already be accepted. Inspect provider logs before resending.'
        with store.transaction() as db:
            store.run(db,f'UPDATE {jobs} SET status=?,error=?,next_attempt=?,lease_until=0 WHERE id=? AND claim=?',(status,error,retry_at,job['id'],claim))
            store.history_write(db,actor,'Scheduled email delivery',None,{'slot':job['slot'],'recipient':job['recipient'],'status':status})
    return {'sent':sent,'state':'checked','slot':slot}

def status(store,actor):
    with store.transaction() as db:
        store.require(db,actor,admin=True);state,jobs=schema(store,db)
        record=store.run(db,f"SELECT * FROM {state} WHERE id='daily'").fetchone()
        history=[dict(r) for r in store.run(db,f'SELECT slot,recipient,status,attempts,error FROM {jobs} ORDER BY created_at DESC LIMIT 30').fetchall()]
    return {'last_slot':record['last_slot'] if record else '', 'error':record['error'] if record else '', 'jobs':history}

def mount(store):
    """Mount after authentication. Built-in Stock checks have no recurring timer."""
    import streamlit as st
    from .portal_ui import config,send_email
    if store.account_table=='accounts':
        actor=st.session_state.get('actor')
        if not actor:return
        from . import notification_rules as rules
        if getattr(rules,'REVISION',0)!=8:
            import importlib
            rules=importlib.reload(rules)
        # Throttle concurrent visits and RPC reruns before checking SQL.
        key=(store.url,store.account_table,'stock-policies')
        now=time.monotonic()
        with _scan_lock:
            if now-_scan_times.get(key,float('-inf'))<55:return
            _scan_times[key]=now
        check_stock=rules.tick
        try:
            result=check_stock(store,actor,config(),send_email)
            if result['state']!='preview_only':return
        except Exception:
            logging.getLogger(__name__).exception('Stock notification check failed; review Email management.')
            return
        # Preserve any previously enabled custom worksheet schedule while the
        # new automatic policies are paused. Once enabled, they join its daily
        # first-visit message instead of running a second scheduler.
        else:
            from .notification_rules import custom_settings
            with store.transaction() as db:
                store.require(db,actor);settings=custom_settings(store,db)
            if not any(r.get('enabled') for r in settings['rules']):return
    @st.fragment(run_every=60)
    def check_due():
        if not st.session_state.get('actor'):return
        from daily_sessions import background_active
        if not background_active(st.session_state):return
        # Full app reruns also execute fragments. Do not scan the database or
        # submit mail again on every navigation and component acknowledgement.
        key=(store.url,store.account_table)
        now=time.monotonic()
        with _scan_lock:
            if now-_scan_times.get(key,float('-inf'))<55:return
            _scan_times[key]=now
        try:tick(store,config(),send_email)
        except Exception:logging.getLogger(__name__).warning('Scheduled email check failed; review Email management and sender configuration.')
    check_due()



