"""Evaluate configured rules against persisted, server-read worksheet rows."""
import hashlib,json,re,time,uuid
EMAIL_FORMAT_REVISION=1

def formatted_sections(sections,context,use_ai=False):
    from notification_format import compose
    writer=None
    if use_ai:
        try:
            import grounded_ai
            key,model=grounded_ai.settings()
            if key:writer=lambda instruction,payload:grounded_ai.generate(key,model,instruction,payload,True,max_output_tokens=1600)
        except Exception:pass
    message=compose('Stock & Planning · Combined notification report',context,sections,writer)
    message.sections=sections
    return message

def report_points(rules,sheets,include_disabled=False,store=None):
    from .console_rules import points
    if store is None:return points(rules,sheets,include_disabled)
    from .recipient_scope import record
    from .segment_access import scope_data
    reports=[]
    for email in sorted({r.get('recipient','') for r in rules}):
        user=record(store,email)
        segments=json.loads(user['allowed_segments']) if user and user['role']!='admin' and user.get('allowed_segments') is not None else None
        visible=scope_data({'sheets':sheets,'tables':sheets},segments)['sheets']
        reports.extend(points([r for r in rules if r.get('recipient')==email],visible,include_disabled))
    return reports

def grouped(rules,sheets,store=None):
    result={}
    for report in report_points(rules,sheets,store=store):
        if not report['matched']:continue
        sections=[{'title':p['title'],'count':p['count'],'bullets':[str(p['count'])+' matching records for this notification rule.'],'tables':[{**p['table'],'title':p['table']['name'],'count':p['count']}]} for p in report['points'] if p['count']]
        result[report['recipient']]=formatted_sections(sections,'Saved workbook values · timestamps in IST')
    return result

def preview(store,actor):
    with store.transaction() as db:store.require(db,actor,admin=True)
    current=store.get_dataset(actor)
    if not current:raise ValueError('Upload or save a shared dataset before previewing alerts.')
    from .recipient_scope import allowed
    return grouped(allowed(store,store.portal_read(actor).get('email_rules',[])),__import__(__package__+'.portal_console',fromlist=['source_tables']).source_tables(current),store=store)

def dispatch(store,actor,send):
    messages=preview(store,actor);count=0
    for recipient,body in messages.items():
        digest=hashlib.sha256((recipient+body).encode()).hexdigest();now=time.time();claim=uuid.uuid4().hex
        with store.transaction() as db:
            store.require(db,actor,admin=True)
            store.run(db,'CREATE TABLE IF NOT EXISTS portal_deliveries (digest TEXT PRIMARY KEY,claim TEXT NOT NULL,sent_at DOUBLE PRECISION NOT NULL)')
            if not store.sqlite:store.run(db,'SELECT pg_advisory_xact_lock(hashtext(?))',('portal-email:'+digest,))
            old=store.run(db,'SELECT sent_at FROM portal_deliveries WHERE digest=?',(digest,)).fetchone()
            if old and now-old['sent_at']<86400:continue
            store.run(db,'INSERT INTO portal_deliveries VALUES(?,?,?) ON CONFLICT(digest) DO UPDATE SET claim=excluded.claim,sent_at=excluded.sent_at',(digest,claim,now))
        try:send(recipient,'Workspace alert report',formatted_sections(body.sections,'Saved workbook values · timestamps in IST',True))
        except Exception:
            with store.transaction() as db:store.run(db,'DELETE FROM portal_deliveries WHERE digest=? AND claim=?',(digest,claim))
            raise
        with store.transaction() as db:store.history_write(db,actor,'Email report',None,{'recipient':recipient,'status':'sent','digest':digest})
        count+=1
    return count

